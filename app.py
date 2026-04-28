import os
import json
import time
import uuid
from datetime import datetime
from typing import List, Union, Any, Optional

from flask import Flask, request, jsonify, g, send_file,
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, Field, model_validator
from enum import Enum

import structlog
from structlog import get_logger

from groq import Groq  # pip install groq

from pylatex import Document, Section, Command, NoEscape, Package
from pylatex.utils import bold
import tempfile


# ====================== إعداد التطبيق ======================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exams.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ====================== Groq Client ======================
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL  = "llama-3.3-70b-versatile"

# ====================== Rate Limiter (module-level) ======================
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri=os.getenv('RATE_LIMIT_STORAGE', 'memory://'),
    strategy="fixed-window"
)


# ====================== إعداد structlog ======================
def setup_structlog(app: Flask):
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

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

    processors = (
        shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
        if app.debug
        else shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False)
        ]
    )

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
        g.start_time  = time.time()
        structlog.contextvars.bind_contextvars(
            request_id=g.request_id,
            ip=request.remote_addr,
            method=request.method,
            path=request.path
        )
        logger.info("Request started", event="request_started")

    @app.after_request
    def after_request_logging(response):
        if hasattr(g, 'start_time'):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            logger.info("Request completed",
                        event="request_completed",
                        status_code=response.status_code,
                        duration_ms=duration_ms)
        return response

    logger.info("✅ structlog initialized successfully")
    return app


# ====================== Rate Limit Handlers ======================
def setup_rate_limit_handlers(app: Flask, limiter: Limiter):
    @limiter.request_filter
    def exempt_health_check():
        return request.path.startswith('/health')

    @app.errorhandler(429)
    def ratelimit_handler(e):
        logger = get_logger("app")
        logger.warning("Rate limit exceeded",
                       ip=get_remote_address(), path=request.path)
        return jsonify({
            "error": "تم تجاوز الحد المسموح به من الطلبات",
            "message": "يرجى الانتظار قليلاً قبل المحاولة مرة أخرى",
            "retry_after": e.description
        }), 429

    get_logger("app").info("✅ Rate Limiting handlers configured")

# ====================== index.html ======================
@app.route("/")
def index():
    try:
    return render_template("index.html")
except Exception as e:
 return f"حطأ في تحميل الواجهة:
 {str(e)}", 500
# ====================== Pydantic Models ======================
class QuestionType(str, Enum):
    MCQ         = "mcq"
    TRUEFALSE   = "truefalse"
    ESSAY       = "essay"
    APPLICATION = "application"
    PROBLEM     = "problem"

class BaseQuestion(BaseModel):
    type:       QuestionType
    difficulty: int   = Field(..., ge=1, le=3)
    text:       str   = Field(..., min_length=15)
    points:     float = Field(..., gt=0)
    competence: Optional[str] = None

class MCQQuestion(BaseQuestion):
    type:    QuestionType = QuestionType.MCQ
    options: List[str]
    answer:  str

    @model_validator(mode='after')
    def answer_in_options(self):
        if self.answer not in self.options:
            raise ValueError("الإجابة يجب أن تكون موجودة ضمن الخيارات")
        return self

class TrueFalseQuestion(BaseQuestion):
    type:   QuestionType = QuestionType.TRUEFALSE
    answer: bool

class EssayQuestion(BaseQuestion):
    type: QuestionType = QuestionType.ESSAY

class ApplicationOrProblem(BaseQuestion):
    type: QuestionType

Question = Union[MCQQuestion, TrueFalseQuestion, EssayQuestion, ApplicationOrProblem]

class ModelAnswer(BaseModel):
    question_index:    int
    question_text:     str
    correct_answer:    Any
    detailed_solution: str
    justification:     Optional[str]  = None
    competence:        Optional[str]  = None
    common_mistakes:   List[str]      = Field(default_factory=list)
    points_breakdown:  Optional[dict] = None

class FullGeneratedExam(BaseModel):
    questions:     List[Question]
    model_answers: List[ModelAnswer]
    total_points:  float = 0.0
    metadata:      dict

    @model_validator(mode='after')
    def calculate_total(self):
        self.total_points = round(sum(q.points for q in self.questions), 2)
        return self


# ====================== نموذج قاعدة البيانات ======================
class GeneratedExam(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    subject       = db.Column(db.String(100), nullable=False)
    grade         = db.Column(db.String(50),  nullable=False)
    semester      = db.Column(db.String(50))
    topic         = db.Column(db.String(200), nullable=False)
    exam_type     = db.Column(db.String(100))
    difficulty    = db.Column(db.String(20))
    total_points  = db.Column(db.Float)
    questions     = db.Column(db.Text)
    model_answers = db.Column(db.Text)
    metadata_info = db.Column(db.Text)
    generated_at  = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address    = db.Column(db.String(50))


# ====================== Groq API: بناء الـ Prompt ======================
def build_exam_prompt(
    subject: str,
    grade: str,
    semester: str,
    topic: str,
    difficulty: str,
    exam_type: str,
    num_questions: int
) -> str:
    """
    يبني Prompt احترافياً يطلب من النموذج إنتاج اختبار
    بصيغة JSON صارمة قابلة للتحقق عبر Pydantic.
    """
    difficulty_map = {"سهل": 1, "متوسط": 2, "صعب": 3}
    diff_num = difficulty_map.get(difficulty, 2)

    return f"""أنت مساعد تربوي متخصص في إعداد الاختبارات المدرسية الجزائرية.

مهمتك: توليد اختبار كامل من {num_questions} أسئلة متنوعة مع إجاباتها النموذجية التفصيلية.

**المعطيات:**
- المادة: {subject}
- المستوى الدراسي: {grade}
- الفصل الدراسي: {semester or 'غير محدد'}
- الموضوع/الوحدة: {topic}
- نوع الاختبار: {exam_type}
- مستوى الصعوبة: {difficulty} (رقم: {diff_num} من 3)
- عدد الأسئلة: {num_questions}

**قواعد صارمة للأسئلة:**
1. يجب أن يحتوي الاختبار على أنواع متنوعة: mcq, truefalse, essay (أو application/problem)
2. كل سؤال نصه لا يقل عن 15 حرفاً
3. أسئلة MCQ تحتوي على 4 خيارات والإجابة موجودة ضمن الخيارات حرفياً
4. النقاط موزعة بشكل منطقي والمجموع الكلي بين 15 و20 نقطة
5. مستوى الصعوبة من 1 إلى 3

**صيغة الإخراج (JSON فقط، بدون أي نص إضافي):**
{{
  "questions": [
    {{
      "type": "mcq",
      "difficulty": {diff_num},
      "text": "نص السؤال هنا؟",
      "points": 2.0,
      "competence": "اسم الكفاءة المستهدفة",
      "options": ["الخيار أ", "الخيار ب", "الخيار ج", "الخيار د"],
      "answer": "الخيار الصحيح حرفياً"
    }},
    {{
      "type": "truefalse",
      "difficulty": 1,
      "text": "عبارة للحكم عليها بصح أو خطأ",
      "points": 1.0,
      "competence": "الكفاءة",
      "answer": true
    }},
    {{
      "type": "essay",
      "difficulty": 3,
      "text": "سؤال مقالي يتطلب شرحاً مفصلاً...",
      "points": 4.0,
      "competence": "الكفاءة"
    }}
  ],
  "model_answers": [
    {{
      "question_index": 0,
      "question_text": "نص السؤال كما ورد",
      "correct_answer": "الإجابة الصحيحة",
      "detailed_solution": "شرح تفصيلي للإجابة مع المبرر العلمي",
      "justification": "لماذا هذه الإجابة صحيحة",
      "competence": "الكفاءة المستهدفة",
      "common_mistakes": ["خطأ شائع 1", "خطأ شائع 2"],
      "points_breakdown": {{"الجزء الأول": 1.0, "الجزء الثاني": 1.0}}
    }}
  ],
  "metadata": {{
    "subject": "{subject}",
    "grade": "{grade}",
    "topic": "{topic}",
    "difficulty": "{difficulty}",
    "generated_by": "groq/{GROQ_MODEL}",
    "timestamp": "{datetime.now().isoformat()}"
  }}
}}

أنتج JSON فقط، بدون مقدمة أو تعليق أو backticks."""


# ====================== استدعاء Groq API ======================
def call_groq_api(prompt: str, logger) -> dict:
    """
    يستدعي Groq API ويعيد dict جاهز للتحقق عبر Pydantic.
    يرمي Exception في حالة الفشل.
    """
    logger.info("إرسال الطلب إلى Groq API", model=GROQ_MODEL)

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "أنت مساعد تربوي متخصص. تُجيب دائماً بـ JSON صحيح فقط "
                    "بدون أي نص إضافي أو backticks أو مقدمة."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,        # توازن بين الإبداع والدقة
        max_tokens=4096,        # كافٍ لـ 10 أسئلة مع إجاباتها
        top_p=0.9,
        stream=False,
    )

    raw_text = response.choices[0].message.content.strip()

    logger.info("استُلم رد من Groq",
                tokens_used=response.usage.total_tokens,
                finish_reason=response.choices[0].finish_reason)

    # تنظيف في حال أضاف النموذج backticks رغم التعليمات
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("فشل تحليل JSON من Groq",
                     error=str(e),
                     raw_text_preview=raw_text[:300])
        raise ValueError(f"الرد من Groq ليس JSON صحيحاً: {e}") from e


# ====================== Routes ======================

@app.route("/generate_full_exam", methods=["POST"])
@limiter.limit("5 per minute")
def generate_full_exam():
    logger    = get_logger("app")
    start_time = time.time()
    client_ip  = request.remote_addr

    data          = request.get_json() or {}
    subject       = data.get("subject",       "").strip()
    grade         = data.get("grade",         "").strip()
    semester      = data.get("semester",      "").strip()
    exam_type     = data.get("examType",      "اختبار فصلي")
    topic         = data.get("topic",         "").strip()
    difficulty    = data.get("difficulty",    "متوسط")
    num_questions = int(data.get("num_questions", 6))

    if not all([subject, grade, topic]):
        logger.warning("طلب غير مكتمل - حقول مفقودة")
        return jsonify({"error": "الحقول subject, grade, topic مطلوبة"}), 400

    # التحقق من صحة المدخلات
    if num_questions < 2 or num_questions > 15:
        return jsonify({"error": "عدد الأسئلة يجب أن يكون بين 2 و15"}), 400
    if difficulty not in ("سهل", "متوسط", "صعب"):
        return jsonify({"error": "مستوى الصعوبة: سهل، متوسط، صعب"}), 400

    logger.info("بدء توليد اختبار جديد",
                subject=subject, grade=grade, topic=topic,
                num_questions=num_questions, difficulty=difficulty)

    max_retries = 2
    prompt = build_exam_prompt(
        subject, grade, semester, topic, difficulty, exam_type, num_questions
    )

    for attempt in range(max_retries):
        try:
            # ====================== استدعاء Groq ======================
            raw_data  = call_groq_api(prompt, logger)
            full_exam = FullGeneratedExam.model_validate(raw_data)
            # =========================================================

            new_exam = GeneratedExam(
                subject=subject,
                grade=grade,
                semester=semester,
                topic=topic,
                exam_type=exam_type,
                difficulty=difficulty,
                total_points=full_exam.total_points,
                questions=json.dumps(
                    [q.model_dump() for q in full_exam.questions],
                    ensure_ascii=False
                ),
                model_answers=json.dumps(
                    [a.model_dump() for a in full_exam.model_answers],
                    ensure_ascii=False
                ),
                metadata_info=json.dumps(full_exam.metadata, ensure_ascii=False),
                ip_address=client_ip
            )
            db.session.add(new_exam)
            db.session.commit()

            duration = round(time.time() - start_time, 2)
            logger.info("تم توليد الاختبار بنجاح",
                        db_id=new_exam.id,
                        total_questions=len(full_exam.questions),
                        total_points=full_exam.total_points,
                        duration_seconds=duration,
                        attempt=attempt + 1)

            response_data = full_exam.model_dump(mode='json')
            response_data["validation"] = {
                "status":           "success",
                "attempt":          attempt + 1,
                "db_id":            new_exam.id,
                "duration_seconds": duration
            }
            response_data["links"] = {
                "view_exam": f"/exam/{new_exam.id}",
                "my_exams":  "/my_exams"
            }
            response_data["export_links"] = {
                "aiken":       f"/export/aiken/{new_exam.id}",
                "gift":        f"/export/gift/{new_exam.id}",
                "pdf_student": f"/export/pdf/{new_exam.id}?teacher=false",
                "pdf_teacher": f"/export/pdf/{new_exam.id}?teacher=true"
            }
            return jsonify(response_data)

        except Exception as e:
            logger.error("فشل في توليد الاختبار",
                         attempt=attempt + 1, error=str(e), exc_info=True)
            if attempt == max_retries - 1:
                return jsonify({
                    "error":   "فشل بعد محاولتين",
                    "details": str(e)
                }), 500
            time.sleep(2)  # انتظار قبل إعادة المحاولة

    return jsonify({"error": "خطأ غير متوقع"}), 500


@app.route("/my_exams", methods=["GET"])
@limiter.limit("30 per minute")
def get_my_exams():
    logger = get_logger("app")
    try:
        subject = request.args.get("subject")
        grade   = request.args.get("grade")
        limit   = int(request.args.get("limit", 20))

        query = GeneratedExam.query.order_by(GeneratedExam.generated_at.desc())
        if subject:
            query = query.filter(GeneratedExam.subject.ilike(f"%{subject}%"))
        if grade:
            query = query.filter(GeneratedExam.grade.ilike(f"%{grade}%"))

        exams = query.limit(limit).all()
        exams_list = [
            {
                "id":            e.id,
                "subject":       e.subject,
                "grade":         e.grade,
                "semester":      e.semester,
                "topic":         e.topic,
                "exam_type":     e.exam_type,
                "difficulty":    e.difficulty,
                "total_points":  e.total_points,
                "generated_at":  e.generated_at.isoformat(),
                "ip_address":    e.ip_address,
                "download_json": f"/exam/{e.id}",
                "download_pdf":  f"/export/pdf/{e.id}"
            }
            for e in exams
        ]

        logger.info("تم جلب قائمة الاختبارات",
                    count=len(exams_list),
                    subject_filter=subject,
                    grade_filter=grade)

        return jsonify({"success": True, "total": len(exams_list), "exams": exams_list})

    except Exception as e:
        logger.error("خطأ في جلب الاختبارات", error=str(e), exc_info=True)
        return jsonify({"error": "حدث خطأ أثناء جلب الاختبارات"}), 500


@app.route("/exam/<int:exam_id>", methods=["GET"])
def get_exam_by_id(exam_id: int):
    logger = get_logger("app")
    try:
        exam = GeneratedExam.query.get_or_404(exam_id)
        response = {
            "id":            exam.id,
            "subject":       exam.subject,
            "grade":         exam.grade,
            "semester":      exam.semester,
            "topic":         exam.topic,
            "exam_type":     exam.exam_type,
            "difficulty":    exam.difficulty,
            "total_points":  exam.total_points,
            "generated_at":  exam.generated_at.isoformat(),
            "questions":     json.loads(exam.questions),
            "model_answers": json.loads(exam.model_answers),
            "metadata":      json.loads(exam.metadata_info) if exam.metadata_info else {}
        }
        logger.info("تم جلب اختبار كامل", exam_id=exam_id, subject=exam.subject)
        return jsonify(response)

    except Exception as e:
        logger.error("خطأ في جلب الاختبار", exam_id=exam_id, error=str(e))
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404


@app.route("/export/aiken/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_aiken(exam_id: int):
    logger = get_logger("app")
    try:
        exam      = GeneratedExam.query.get_or_404(exam_id)
        questions = json.loads(exam.questions)

        aiken_lines = []
        for q in questions:
            if q.get("type") == "mcq":
                aiken_lines.append(q["text"])
                for opt in q.get("options", []):
                    aiken_lines.append(opt)
                aiken_lines.append(f"ANSWER: {q.get('answer', '')}")
                aiken_lines.append("")
            elif q.get("type") == "truefalse":
                aiken_lines.append(q["text"])
                aiken_lines.append("ANSWER: " + ("TRUE" if q.get("answer") else "FALSE"))
                aiken_lines.append("")

        logger.info("تم تصدير Aiken", exam_id=exam_id)
        return jsonify({
            "success":      True,
            "format":       "Aiken",
            "filename":     f"exam_{exam_id}_aiken.txt",
            "content":      "\n".join(aiken_lines),
            "instructions": "في Moodle: Question Bank → Import → Aiken Format"
        })

    except Exception as e:
        logger.error("خطأ في تصدير Aiken", exam_id=exam_id, error=str(e))
        return jsonify({"error": "فشل في تصدير Aiken"}), 500


@app.route("/export/gift/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_gift(exam_id: int):
    logger = get_logger("app")
    try:
        exam      = GeneratedExam.query.get_or_404(exam_id)
        questions = json.loads(exam.questions)

        gift_lines = []
        for i, q in enumerate(questions):
            if q.get("type") == "mcq":
                gift_lines.append(f"::Q{i+1}:: {q['text']} {{")
                for opt in q.get("options", []):
                    prefix = "=" if opt == q.get("answer") else "~"
                    gift_lines.append(f"{prefix}{opt}")
                gift_lines.append("}")
                gift_lines.append("")
            elif q.get("type") == "truefalse":
                answer = "TRUE" if q.get("answer") else "FALSE"
                gift_lines.append(f"::Q{i+1}:: {q['text']} {{ {answer} }}")
                gift_lines.append("")

        logger.info("تم تصدير GIFT", exam_id=exam_id)
        return jsonify({
            "success":      True,
            "format":       "GIFT",
            "filename":     f"exam_{exam_id}_gift.txt",
            "content":      "\n".join(gift_lines),
            "instructions": "في Moodle: Question Bank → Import → GIFT format"
        })

    except Exception as e:
        logger.error("خطأ في تصدير GIFT", exam_id=exam_id, error=str(e))
        return jsonify({"error": "فشل في تصدير GIFT"}), 500


@app.route("/export/pdf/<int:exam_id>", methods=["GET"])
@limiter.limit("20 per minute")
def export_pdf(exam_id: int):
    logger = get_logger("app")
    teacher_version = request.args.get("teacher", "false").lower() == "true"
    try:
        exam          = GeneratedExam.query.get_or_404(exam_id)
        questions     = json.loads(exam.questions)
        model_answers = (
            json.loads(exam.model_answers)
            if teacher_version and exam.model_answers else None
        )

        doc = Document(
            documentclass='article',
            geometry_options={'margin': '1.8cm', 'a4paper': True}
        )
        doc.packages.append(Package('utf8',    'inputenc'))
        doc.packages.append(Package('fontenc'))
        doc.packages.append(Package('fancyhdr'))
        doc.packages.append(Package('lastpage'))

        doc.preamble.append(Command('pagestyle', 'fancy'))
        doc.preamble.append(Command('fancyhf',   ''))
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
            with doc.create(Section(
                f"السؤال {i+1} \\quad ({q.get('points', 1)} نقطة)", numbering=True
            )):
                doc.append(NoEscape(q["text"]))
                doc.append(NoEscape(r'\\'))

                if q.get("type") == "mcq" and q.get("options"):
                    doc.append(NoEscape(r'\begin{enumerate}[label=\arabic*.]'))
                    for opt in q.get("options", []):
                        doc.append(NoEscape(f'\\item {opt}'))
                    doc.append(NoEscape(r'\end{enumerate}'))

                if teacher_version and model_answers and i < len(model_answers):
                    ans = model_answers[i]
                    doc.append(NoEscape(r'\vspace{0.8cm}'))
                    with doc.create(Section(
                        "التصحيح النموذجي \\quad (للمعلم فقط)", numbering=False
                    )):
                        doc.append(bold("الإجابة: "))
                        doc.append(str(ans.get("correct_answer", "")))
                        doc.append(NoEscape(r'\\'))
                        doc.append(bold("الحل التفصيلي: "))
                        doc.append(NoEscape(ans.get("detailed_solution", "لا يوجد")))
                        if ans.get("common_mistakes"):
                            doc.append(NoEscape(r'\\'))
                            doc.append(bold("الأخطاء الشائعة:"))
                            for mistake in ans["common_mistakes"]:
                                doc.append(f"• {mistake}\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            version  = "مع_التصحيح" if teacher_version else "للتلميذ"
            filename = (
                f"{exam.subject}_{exam.grade}_{exam.topic}_{version}.pdf"
                .replace(" ", "_")
            )
            filepath = os.path.join(tmpdir, filename)

            try:
                doc.generate_pdf(filepath, clean_tex=True)
            except Exception as latex_err:
                logger.warning("إعادة محاولة PDF", error=str(latex_err))
                doc.generate_pdf(filepath, clean_tex=False)

            logger.info("تم تصدير PDF",
                        exam_id=exam_id, teacher_version=teacher_version)
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )

    except Exception as e:
        logger.error("خطأ في تصدير PDF", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "فشل في إنشاء PDF. تأكد من تثبيت LaTeX"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status":    "healthy",
        "service":   "exam_generator",
        "model":     GROQ_MODEL,
        "timestamp": datetime.now().isoformat()
    })


# ====================== تشغيل التطبيق ======================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app    = setup_structlog(app)
    setup_rate_limit_handlers(app, limiter)

    app.run(debug=True, host="0.0.0.0", port=5000)
