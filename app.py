import os
import json
import time
import uuid
import tempfile
from datetime import datetime
from typing import List, Union, Any, Optional

# Flask & Extensions
from flask import Flask, request, jsonify, g, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Pydantic for Data Validation
from pydantic import BaseModel, Field, model_validator
from enum import Enum

# Logging
import structlog
from structlog import get_logger

# AI Client
from groq import Groq

# PDF Generation
from pylatex import Document, Section, Command, NoEscape, Package
from pylatex.utils import bold

# ====================== إعداد التطبيق ======================
app = Flask(__name__)

# --- إعداد قاعدة البيانات ---
db_uri = os.getenv('DATABASE_URL', 'sqlite:///exams.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- إعداد عميل Groq ---
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("❌ GROQ_API_KEY is required but not set in environment variables.")
groq_client = Groq(api_key=api_key)

# ====================== Pydantic Models ======================

class QuestionType(str, Enum):
    MCQ = "mcq"
TRUEFALSE = "truefalse"
ESSAY = "essay"
    APPLICATION = "application"
    PROBLEM = "problem"

class BaseQuestion(BaseModel):
    type: QuestionType
    difficulty: int = Field(..., ge=1, le=3)
    text: str = Field(..., min_length=15)
    points: float = Field(..., gt=0)
    competence: Optional[str] = None

class MCQQuestion(BaseQuestion):
    type: QuestionType = QuestionType.MCQ
    options: List[str]
    answer: str

    @model_validator(mode='after')
    def answer_in_options(self):
        if self.answer not in self.options:
            raise ValueError("الإجابة يجب أن تكون موجودة ضمن الخيارات")
        return self

class TrueFalseQuestion(BaseQuestion):
    type: QuestionType = QuestionType.TRUEFALSE
    answer: bool

class EssayQuestion(BaseQuestion):
    type: QuestionType = QuestionType.ESSAY

class ApplicationQuestion(BaseQuestion):
    type: QuestionType = QuestionType.APPLICATION

class ProblemQuestion(BaseQuestion):
    type: QuestionType = QuestionType.PROBLEM

Question = Union[MCQQuestion, TrueFalseQuestion, EssayQuestion, ApplicationQuestion, ProblemQuestion]

class ModelAnswer(BaseModel):
    question_index: int
    question_text: str
    correct_answer: Any
    detailed_solution: str
    justification: Optional[str] = None
    competence: Optional[str] = None
    common_mistakes: List[str] = Field(default_factory=list)
    points_breakdown: Optional[dict] = None

class FullGeneratedExam(BaseModel):
    questions: List[Question]
    model_answers: List[ModelAnswer]    total_points: float
    metadata: dict

    @model_validator(mode='after')
    def calculate_total(self):
        self.total_points = round(sum(q.points for q in self.questions), 2)
        return self

# ====================== نموذج قاعدة البيانات ======================

class GeneratedExam(db.Model):
    __tablename__ = 'generated_exams'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    grade = db.Column(db.String(50), nullable=False, index=True)
    semester = db.Column(db.String(50))
    topic = db.Column(db.String(200), nullable=False, index=True)
    exam_type = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))
    total_points = db.Column(db.Float)
    questions = db.Column(db.Text)
    model_answers = db.Column(db.Text)
    metadata_info = db.Column(db.Text)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))

# ====================== إعداد Structlog ======================

def setup_structlog(app: Flask):
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if app.debug:
        processors = shared_processors + [
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True)
        ]    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False)
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = get_logger("app")
    app.logger = logger

    @app.before_request
    def before_request_logging():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        structlog.contextvars.bind_contextvars(
            request_id=g.request_id,
            ip=request.remote_addr,
            method=request.method,
            path=request.path
        )
        logger.info(event="request_started")  # ← تم التصحيح هنا

    @app.after_request
    def after_request_logging(response):
        if hasattr(g, 'start_time'):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            logger.info(
                event="request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms
            )  # ← تم التصحيح هنا
        return response

    logger.info(event="structured_logging_initialized")
    return app

# ====================== Rate Limiting ======================

def setup_rate_limiting(app):
    storage_uri = os.getenv('RATE_LIMIT_STORAGE', 'memory://')
    
    limiter = Limiter(
        key_func=get_remote_address,        app=app,
        default_limits=["60 per minute"],
        storage_uri=storage_uri,
        strategy="fixed-window"
    )

    @limiter.request_filter
    def exempt_health_check():
        return request.path.startswith('/health')

    @app.errorhandler(429)
    def ratelimit_handler(e):
        logger = get_logger("app")
        logger.warning(
            event="rate_limit_exceeded",
            ip=get_remote_address(),
            path=request.path
        )
        
        return jsonify({
            "error": "تم تجاوز الحد المسموح به من الطلبات",
            "message": "يرجى الانتظار قليلاً قبل المحاولة مرة أخرى",
            "retry_after": str(e.description)
        }), 429

    app.logger.info(event="rate_limiting_activated")
    return limiter

limiter = setup_rate_limiting(app)

# ====================== Health Check ======================

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "exam_generator",
        "timestamp": datetime.now().isoformat()
    })

# ====================== الدالة الرئيسية (مع Retry) ======================

@app.route("/generate_full_exam", methods=["POST"])
@limiter.limit("5 per minute")
def generate_full_exam():
    logger = get_logger("app")
    start_time = time.time()
    client_ip = request.remote_addr

    data = request.get_json() or {}    
    subject = data.get("subject", "").strip()
    grade = data.get("grade", "").strip()
    semester = data.get("semester", "").strip()
    exam_type = data.get("examType", "اختبار فصلي")
    topic = data.get("topic", "").strip()
    difficulty = data.get("difficulty", "متوسط")
    num_questions = int(data.get("num_questions", 6))

    if not all([subject, grade, topic]):
        logger.warning(event="incomplete_request", missing_fields=["subject", "grade", "topic"])
        return jsonify({"error": "الحقول subject, grade, topic مطلوبة"}), 400

    model_name = "llama-3.3-70b-versatile"
    max_retries = 2

    logger.info(
        event="exam_generation_started",
        subject=subject,
        grade=grade,
        topic=topic,
        num_questions=num_questions,
        difficulty=difficulty
    )

    system_prompt = """أنت أستاذ جزائري خبير في تطوير الاختبارات التعليمية وفق المنهاج الجزائري. 
مهمتك إنشاء اختبارات متكاملة عالية الجودة مع الإجابات النموذجية والحلول التفصيلية.

قواعد صارمة:
1. الأسئلة يجب أن تكون واضحة ومباشرة وخالية من الغموض
2. خيارات MCQ يجب أن تكون متقاربة المنطقياً (plausible distractors)
3. الإجابة النموذجية يجب أن تكون دقيقة ومفصلة
4. اذكر الأخطاء الشائعة التي يرتكبها التلاميذ
5. حدد الكفاءة (competence) المستهدفة لكل سؤال
6. اجعل النقاط منطقية (سؤال MCQ: 1-2 نقطة، مقالي: 3-5 نقاط، تطبيقي: 4-6 نقاط)
7. نوع الأسئلة يجب أن يكون أحد: mcq, truefalse, essay, application, problem"""

    user_prompt = f"""أنشئ اختباراً كاملاً في مادة {subject} للسنة {grade}، الفصل {semester or 'غير محدد'}.

الموضوع: {topic}
نوع الاختبار: {exam_type}
المستوى: {difficulty}
عدد الأسئلة: {num_questions}

يجب أن يحتوي الاختبار على تنوع في أنواع الأسئلة (MCQ، صح/خطأ، مقالي، تطبيقي/مسألة).

أعد الرد بتنسيق JSON صارم يتبع هذا الهيكل:
{{
  "questions": [
    {{      "type": "mcq",
      "difficulty": 1,
      "text": "نص السؤال بالعربية",
      "points": 1.5,
      "competence": "اسم الكفاءة",
      "options": ["خيار أ", "خيار ب", "خيار ج", "خيار د"],
      "answer": "خيار أ"
    }}
  ],
  "model_answers": [
    {{
      "question_index": 0,
      "question_text": "نص السؤال",
      "correct_answer": "الإجابة الصحيحة",
      "detailed_solution": "شرح مفصل للحل",
      "justification": "لماذا هذه الإجابة صحيحة",
      "competence": "اسم الكفاءة",
      "common_mistakes": ["خطأ شائع 1", "خطأ شائع 2"],
      "points_breakdown": {{"فهم المفهوم": 0.5, "التطبيق": 1.0}}
    }}
  ],
  "total_points": 0.0,
  "metadata": {{
    "subject": "{subject}",
    "grade": "{grade}",
    "topic": "{topic}",
    "difficulty": "{difficulty}",
    "generated_for": "المنهاج الجزائري",
    "notes": "أي ملاحظات إضافية"
  }}
}}

ملاحظات:
- total_points يتم حسابه تلقائياً من مجموع points
- اجعل الأسئلة متدرجة الصعوبة
- لا تضف أي نص خارج JSON"""

    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
                        raw_content = response.choices[0].message.content
            
            # تنظيف JSON إذا لزم الأمر
            raw_content = raw_content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()
            
            raw_data = json.loads(raw_content)
            
            # التحقق من صحة البيانات
            full_exam = FullGeneratedExam.model_validate(raw_data)

            # حفظ في قاعدة البيانات
            new_exam = GeneratedExam(
                subject=subject,
                grade=grade,
                semester=semester,
                topic=topic,
                exam_type=exam_type,
                difficulty=difficulty,
                total_points=full_exam.total_points,
                questions=json.dumps([q.model_dump() for q in full_exam.questions], ensure_ascii=False),
                model_answers=json.dumps([a.model_dump() for a in full_exam.model_answers], ensure_ascii=False),
                metadata_info=json.dumps(full_exam.metadata, ensure_ascii=False),
                ip_address=client_ip
            )
            db.session.add(new_exam)
            db.session.commit()

            duration = round(time.time() - start_time, 2)

            logger.info(
                event="exam_generated_successfully",
                db_id=new_exam.id,
                total_questions=len(full_exam.questions),
                total_points=full_exam.total_points,
                duration_seconds=duration,
                attempt=attempt + 1
            )

            response_data = full_exam.model_dump(mode='json')
            response_data["validation"] = {
                "status": "success",
                "attempt": attempt + 1,
                "db_id": new_exam.id,                "duration_seconds": duration
            }
            response_data["links"] = {
                "view_exam": f"/exam/{new_exam.id}",
                "my_exams": "/my_exams",
                "export_aiken": f"/export/aiken/{new_exam.id}",
                "export_gift": f"/export/gift/{new_exam.id}",
                "export_pdf": f"/export/pdf/{new_exam.id}"
            }

            return jsonify(response_data)

        except Exception as e:
            logger.error(
                event="exam_generation_failed",
                attempt=attempt + 1,
                error=str(e),
                exc_info=True
            )
            
            if attempt == max_retries - 1:
                return jsonify({"error": "فشل بعد محاولتين", "details": str(e)}), 500
            
            time.sleep(1.5)

    return jsonify({"error": "خطأ غير متوقع"}), 500

# ====================== عرض الاختبارات ======================

@app.route("/my_exams", methods=["GET"])
@limiter.limit("30 per minute")
def get_my_exams():
    logger = get_logger("app")
    
    try:
        subject = request.args.get("subject")
        grade = request.args.get("grade")
        limit = int(request.args.get("limit", 20))
        
        query = GeneratedExam.query.order_by(GeneratedExam.generated_at.desc())
        
        if subject:
            query = query.filter(GeneratedExam.subject.ilike(f"%{subject}%"))
        if grade:
            query = query.filter(GeneratedExam.grade.ilike(f"%{grade}%"))
        
        exams = query.limit(limit).all()
        
        exams_list = []
        for exam in exams:            exams_list.append({
                "id": exam.id,
                "subject": exam.subject,
                "grade": exam.grade,
                "semester": exam.semester,
                "topic": exam.topic,
                "exam_type": exam.exam_type,
                "difficulty": exam.difficulty,
                "total_points": exam.total_points,
                "generated_at": exam.generated_at.isoformat(),
                "ip_address": exam.ip_address,
                "links": {
                    "view": f"/exam/{exam.id}",
                    "download_json": f"/exam/{exam.id}",
                    "download_pdf": f"/export/pdf/{exam.id}",
                    "export_aiken": f"/export/aiken/{exam.id}",
                    "export_gift": f"/export/gift/{exam.id}"
                }
            })
        
        logger.info(
            event="exams_list_retrieved",
            count=len(exams_list),
            subject_filter=subject,
            grade_filter=grade
        )
        
        return jsonify({
            "success": True,
            "total": len(exams_list),
            "exams": exams_list
        })
        
    except Exception as e:
        logger.error(event="failed_to_retrieve_exams", error=str(e), exc_info=True)
        return jsonify({"error": "حدث خطأ أثناء جلب الاختبارات"}), 500

# ====================== جلب اختبار واحد ======================

@app.route("/exam/<int:exam_id>", methods=["GET"])
@limiter.limit("30 per minute")
def get_exam_by_id(exam_id: int):
    logger = get_logger("app")
    
    try:
        exam = GeneratedExam.query.get_or_404(exam_id)
        
        response = {
            "id": exam.id,
            "subject": exam.subject,            "grade": exam.grade,
            "semester": exam.semester,
            "topic": exam.topic,
            "exam_type": exam.exam_type,
            "difficulty": exam.difficulty,
            "total_points": exam.total_points,
            "generated_at": exam.generated_at.isoformat(),
            "questions": json.loads(exam.questions),
            "model_answers": json.loads(exam.model_answers),
            "metadata": json.loads(exam.metadata_info) if exam.metadata_info else {},
            "links": {
                "export_aiken": f"/export/aiken/{exam.id}",
                "export_gift": f"/export/gift/{exam.id}",
                "export_pdf": f"/export/pdf/{exam.id}"
            }
        }
        
        logger.info(event="exam_retrieved", exam_id=exam_id, subject=exam.subject)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(event="failed_to_retrieve_exam", exam_id=exam_id, error=str(e))
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404

# ====================== تصدير Aiken ======================

@app.route("/export/aiken/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_aiken(exam_id: int):
    logger = get_logger("app")
    
    try:
        exam = GeneratedExam.query.get_or_404(exam_id)
        questions = json.loads(exam.questions)
        
        aiken_content = []
        
        for i, q in enumerate(questions):
            if q.get("type") == "mcq":
                aiken_content.append(q["text"])
                for option in q.get("options", []):
                    aiken_content.append(option)
                aiken_content.append(f"ANSWER: {q.get('answer', '')}")
                aiken_content.append("")
                
            elif q.get("type") == "truefalse":
                aiken_content.append(q["text"])
                answer = "TRUE" if q.get("answer") else "FALSE"
                aiken_content.append(f"ANSWER: {answer}")                aiken_content.append("")
        
        aiken_text = "\n".join(aiken_content)
        filename = f"exam_{exam_id}_aiken.txt"
        
        logger.info(
            event="aiken_exported",
            exam_id=exam_id,
            mcq_count=len([q for q in questions if q.get("type") == "mcq"])
        )
        
        return jsonify({
            "success": True,
            "format": "Aiken",
            "filename": filename,
            "content": aiken_text,
            "instructions": "في Moodle: Question Bank → Import → اختر صيغة Aiken Format ثم الصق المحتوى"
        })
        
    except Exception as e:
        logger.error(event="aiken_export_failed", exam_id=exam_id, error=str(e))
        return jsonify({"error": "فشل في تصدير Aiken"}), 500

# ====================== تصدير GIFT ======================

@app.route("/export/gift/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_gift(exam_id: int):
    logger = get_logger("app")
    
    try:
        exam = GeneratedExam.query.get_or_404(exam_id)
        questions = json.loads(exam.questions)
        
        gift_content = []
        
        for i, q in enumerate(questions):
            if q.get("type") == "mcq":
                gift_content.append(f"::Q{i+1}:: {q['text']} {{")
                for opt in q.get("options", []):
                    if opt == q.get("answer"):
                        gift_content.append(f"={opt}")
                    else:
                        gift_content.append(f"~{opt}")
                gift_content.append("}")
                gift_content.append("")
                
            elif q.get("type") == "truefalse":
                answer = "TRUE" if q.get("answer") else "FALSE"
                gift_content.append(f"::Q{i+1}:: {q['text']} {{ {answer} }}")                gift_content.append("")
        
        gift_text = "\n".join(gift_content)
        filename = f"exam_{exam_id}_gift.txt"
        
        logger.info(event="gift_exported", exam_id=exam_id)
        
        return jsonify({
            "success": True,
            "format": "GIFT",
            "filename": filename,
            "content": gift_text,
            "instructions": "في Moodle: Question Bank → Import → اختر صيغة GIFT ثم ارفع الملف أو الصق المحتوى"
        })
        
    except Exception as e:
        logger.error(event="gift_export_failed", exam_id=exam_id, error=str(e))
        return jsonify({"error": "فشل في تصدير GIFT"}), 500

# ====================== تصدير PDF ======================

@app.route("/export/pdf/<int:exam_id>", methods=["GET"])
@limiter.limit("20 per minute")
def export_pdf(exam_id: int):
    logger = get_logger("app")
    teacher_version = request.args.get("teacher", "false").lower() == "true"
    
    try:
        exam = GeneratedExam.query.get_or_404(exam_id)
        questions = json.loads(exam.questions)
        model_answers = json.loads(exam.model_answers) if teacher_version and exam.model_answers else None

        doc = Document(
            documentclass='article',
            geometry_options={'margin': '1.8cm', 'a4paper': True}
        )

        doc.packages.append(Package('arabtex'))
        doc.packages.append(Package('utf8', 'inputenc'))
        doc.packages.append(Package('fontenc'))
        doc.packages.append(Package('fancyhdr'))
        doc.packages.append(Package('lastpage'))

        doc.preamble.append(Command('pagestyle', 'fancy'))
        doc.preamble.append(Command('fancyhf', ''))
        doc.preamble.append(Command('rhead', 'وزارة التربية الوطنية'))
        doc.preamble.append(Command('lhead', f'{exam.subject} - {exam.grade}'))
        doc.preamble.append(Command('chead', exam.topic))
        doc.preamble.append(Command('rfoot', 'صفحة \\thepage / \\pageref{LastPage}'))
        doc.append(NoEscape(r'\begin{center}'))
        doc.append(NoEscape(r'\Large\textbf{' + f'{exam.exam_type} - {exam.subject}' + r'}'))
        doc.append(NoEscape(r'\\'))
        doc.append(NoEscape(r'\large{' + f'{exam.grade} | {exam.semester or ""}' + r'}'))
        doc.append(NoEscape(r'\\'))
        doc.append(NoEscape(r'\normalsize{' + f'الموضوع: {exam.topic}' + r'}'))
        doc.append(NoEscape(r'\end{center}'))
        doc.append(NoEscape(r'\vspace{1.2cm}'))

        for i, q in enumerate(questions):
            with doc.create(Section(f"السؤال {i+1} \quad ({q.get('points', 1)} نقطة)", numbering=True)):
                doc.append(NoEscape(q["text"]))
                doc.append(NoEscape(r'\\'))
                
                if q.get("type") == "mcq" and q.get("options"):
                    doc.append(NoEscape(r'\begin{enumerate}[label=\arabic*.]'))
                    for opt in q.get("options", []):
                        doc.append(NoEscape(f'\item {opt}'))
                    doc.append(NoEscape(r'\end{enumerate}'))
                
                if teacher_version and model_answers and i < len(model_answers):
                    ans = model_answers[i]
                    doc.append(NoEscape(r'\vspace{0.8cm}'))
                    with doc.create(Section("التصحيح النموذجي \quad (للمعلم فقط)", numbering=False)):
                        doc.append(bold("الإجابة: "))
                        doc.append(str(ans.get("correct_answer", "")))
                        doc.append(NoEscape(r'\\'))
                        
                        doc.append(bold("الحل التفصيلي:"))
                        doc.append(NoEscape(ans.get("detailed_solution", "لا يوجد حل مفصل")))
                        
                        if ans.get("common_mistakes"):
                            doc.append(NoEscape(r'\\'))
                            doc.append(bold("الأخطاء الشائعة:"))
                            for mistake in ans["common_mistakes"]:
                                doc.append(f"• {mistake}\n")
        
        with tempfile.TemporaryDirectory() as tmpdirname:
            version = "مع_التصحيح" if teacher_version else "للتلميذ"
            filename = f"{exam.subject}_{exam.grade}_{exam.topic}_{version}.pdf".replace(" ", "_")
            filepath = os.path.join(tmpdirname, filename)
            
            try:
                doc.generate_pdf(filepath, clean_tex=True)
            except Exception as latex_error:
                logger.warning(event="pdflatex_error", error=str(latex_error))
                doc.generate_pdf(filepath, clean_tex=False)

            logger.info(
                event="pdf_exported_successfully",                exam_id=exam_id,
                teacher_version=teacher_version,
                filename=filename
            )

            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )

    except Exception as e:
        logger.error(event="pdf_export_failed", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "فشل في إنشاء ملف PDF. تأكد من تثبيت LaTeX على السيرفر"}), 500

# ====================== تشغيل التطبيق ======================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    app = setup_structlog(app)
    
    is_debug = os.getenv('FLASK_DEBUG', '0').lower() == '1'
    app.run(debug=is_debug)
