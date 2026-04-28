import os
import json
import time
import uuid
import tempfile
import re
from datetime import datetime
from typing import List, Union, Any, Optional

# Flask & Extensions
from flask import Flask, request, jsonify, g, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

# Pydantic for Data Validation
from pydantic import BaseModel, Field, model_validator
from enum import Enum

# Logging
import structlog
from structlog import get_logger

# AI Client
from groq import Groq

# PDF Generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib import colors

# ====================== إعداد التطبيق ======================
app = Flask(__name__)

# --- إعداد قاعدة البيانات ---
db_uri = os.getenv('DATABASE_URL', 'sqlite:///exams.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- إعداد عميل Groq ---
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("❌ GROQ_API_KEY مطلوب.")
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
            raise ValueError("الإجابة يجب أن تكون ضمن الخيارات")
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

class ExamMetadata(BaseModel):
    subject: str
    grade: str
    semester: Optional[str] = None
    topic: str
    exam_type: str
    difficulty: str
    generated_at: Optional[str] = None

class FullGeneratedExam(BaseModel):
    questions: List[Question]
    model_answers: List[ModelAnswer]
    metadata: Optional[ExamMetadata] = None
    total_points: float = 0.0

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

# ====================== إعداد الخط العربي ======================
def register_arabic_font():
    font_paths = [
        'NotoSansArabic-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        'static/fonts/NotoSansArabic-Regular.ttf',
        'Amiri-Regular.ttf',
        '/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf'
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('ArabicFont', fp))
                return 'ArabicFont'
            except:
                continue
    return 'Helvetica'

ARABIC_FONT = register_arabic_font()

def reshape_arabic(text: str) -> str:
    """محاولة بسيطة لتحسين عرض النص العربي"""
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except ImportError:
        return str(text)

# ====================== إعداد Structlog ======================
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

    if app.debug:
        processors = shared_processors + [
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
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
        logger.info(event="request_started")

    @app.after_request
    def after_request_logging(response):
        if hasattr(g, 'start_time'):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            logger.info(
                event="request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms
            )
        return response

    logger.info(event="structured_logging_initialized")
    return app

# ====================== Rate Limiting ======================
def setup_rate_limiting(app):
    storage_uri = os.getenv('REDIS_URL', 'memory://')
    
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
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
        logger.warning(event="rate_limit_exceeded", ip=get_remote_address(), path=request.path)
        return jsonify({
            "error": "تم تجاوز الحد المسموح به",
            "retry_after": str(e.description)
        }), 429

    return limiter

limiter = setup_rate_limiting(app)
app = setup_structlog(app)

# ====================== Health Check ======================
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "exam_generator",
        "timestamp": datetime.now().isoformat()
    })

# ====================== توليد الاختبار ======================
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
    num_questions = min(int(data.get("num_questions", 6)), 20)

    if not all([subject, grade, topic]):
        return jsonify({"error": "الحقول subject, grade, topic مطلوبة"}), 400

    model_name = "llama-3.3-70b-versatile"
    max_retries = 3

    logger.info(event="exam_generation_started", subject=subject, grade=grade, topic=topic)

    system_prompt = """أنت أستاذ جزائري خبير في المنهاج الجزائري. أنشئ اختبارات متكاملة مع إجابات نموذجية دقيقة.
يجب أن تُرجع JSON صالح فقط بدون أي نص إضافي."""

    user_prompt = f"""أنشئ اختباراً في مادة {subject} للسنة {grade}، الموضوع: {topic}، نوع الاختبار: {exam_type}، الصعوبة: {difficulty}.
عدد الأسئلة المطلوب: {num_questions} أسئلة متنوعة (mcq, truefalse, essay, application, problem).

لكل سؤال: النص، النوع، الصعوبة (1-3)، النقاط، الكفاءة المستهدفة.
لكل إجابة نموذجية: رقم السؤال، النص، الإجابة الصحيحة، الحل المفصل، الأخطاء الشائعة.

رد بـ JSON صارم فقط يطابق هذا الهيكل:
{{
  "questions": [...],
  "model_answers": [...],
  "metadata": {{"subject": "...", "grade": "...", "topic": "...", "exam_type": "...", "difficulty": "..."}}
}}"""

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
            
            raw_content = response.choices[0].message.content.strip()
            raw_content = re.sub(r'^```json\s*|\s*```$', '', raw_content, flags=re.MULTILINE).strip()
            raw_data = json.loads(raw_content)
            
            # Ensure metadata exists
            if 'metadata' not in raw_data:
                raw_data['metadata'] = {
                    'subject': subject, 'grade': grade, 'semester': semester,
                    'topic': topic, 'exam_type': exam_type, 'difficulty': difficulty
                }
            
            full_exam = FullGeneratedExam.model_validate(raw_data)

            # حفظ في DB
            new_exam = GeneratedExam(
                subject=subject, grade=grade, semester=semester, topic=topic,
                exam_type=exam_type, difficulty=difficulty, 
                total_points=full_exam.total_points,
                questions=json.dumps([q.model_dump() for q in full_exam.questions], ensure_ascii=False),
                model_answers=json.dumps([a.model_dump() for a in full_exam.model_answers], ensure_ascii=False),
                metadata_info=json.dumps(full_exam.metadata.model_dump() if full_exam.metadata else {}, ensure_ascii=False),
                ip_address=client_ip
            )
            db.session.add(new_exam)
            db.session.commit()

            duration = round(time.time() - start_time, 2)
            logger.info(event="exam_generated_successfully", db_id=new_exam.id, duration=duration)

            response_data = full_exam.model_dump(mode='json')
            response_data["validation"] = {"status": "success", "db_id": new_exam.id, "duration": duration}
            response_data["links"] = {
                "self": f"/exam/{new_exam.id}",
                "pdf_student": f"/export/pdf/{new_exam.id}?teacher=false",
                "pdf_teacher": f"/export/pdf/{new_exam.id}?teacher=true",
                "aiken": f"/export/aiken/{new_exam.id}",
                "gift": f"/export/gift/{new_exam.id}"
            }
            return jsonify(response_data)

        except json.JSONDecodeError as e:
            logger.error(event="json_parse_failed", attempt=attempt+1, error=str(e))
        except Exception as e:
            logger.error(event="generation_failed", attempt=attempt+1, error=str(e))
        
        time.sleep(2 ** attempt)

    return jsonify({"error": "فشل توليد الاختبار بعد 3 محاولات"}), 500

# ====================== قائمة الاختبارات ======================
@app.route("/my_exams", methods=["GET"])
@limiter.limit("30 per minute")
def my_exams():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    subject = request.args.get('subject', '')
    grade = request.args.get('grade', '')
    
    query = GeneratedExam.query
    
    if subject:
        query = query.filter(GeneratedExam.subject.ilike(f'%{subject}%'))
    if grade:
        query = query.filter(GeneratedExam.grade.ilike(f'%{grade}%'))
    
    pagination = query.order_by(GeneratedExam.generated_at.desc()).paginate(
        page=page, per_page=min(per_page, 50), error_out=False
    )
    
    exams = []
    for exam in pagination.items:
        exams.append({
            "id": exam.id,
            "subject": exam.subject,
            "grade": exam.grade,
            "topic": exam.topic,
            "exam_type": exam.exam_type,
            "difficulty": exam.difficulty,
            "total_points": exam.total_points,
            "generated_at": exam.generated_at.isoformat() if exam.generated_at else None,
            "links": {
                "self": f"/exam/{exam.id}",
                "pdf": f"/export/pdf/{exam.id}"
            }
        })
    
    return jsonify({
        "exams": exams,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page,
        "per_page": per_page
    })

# ====================== عرض اختبار محدد ======================
@app.route("/exam/<int:exam_id>", methods=["GET"])
@limiter.limit("30 per minute")
def get_exam(exam_id):
    exam = db.session.get(GeneratedExam, exam_id)
    if not exam:
        abort(404, description="الاختبار غير موجود")
    
    return jsonify({
        "id": exam.id,
        "subject": exam.subject,
        "grade": exam.grade,
        "semester": exam.semester,
        "topic": exam.topic,
        "exam_type": exam.exam_type,
        "difficulty": exam.difficulty,
        "total_points": exam.total_points,
        "questions": json.loads(exam.questions) if exam.questions else [],
        "model_answers": json.loads(exam.model_answers) if exam.model_answers else [],
        "metadata": json.loads(exam.metadata_info) if exam.metadata_info else {},
        "generated_at": exam.generated_at.isoformat() if exam.generated_at else None,
        "links": {
            "pdf_student": f"/export/pdf/{exam.id}?teacher=false",
            "pdf_teacher": f"/export/pdf/{exam.id}?teacher=true",
            "aiken": f"/export/aiken/{exam.id}",
            "gift": f"/export/gift/{exam.id}"
        }
    })

# ====================== تصدير PDF ======================
@app.route("/export/pdf/<int:exam_id>", methods=["GET"])
@limiter.limit("10 per minute")
def export_pdf(exam_id):
    teacher_version = request.args.get("teacher", "false").lower() == "true"
    exam = db.session.get(GeneratedExam, exam_id)
    if not exam:
        abort(404, description="الاختبار غير موجود")
    
    questions = json.loads(exam.questions) if exam.questions else []
    answers = json.loads(exam.model_answers) if exam.model_answers else []
    
    tmpdir = tempfile.mkdtemp()
    filename = f"exam_{exam_id}_{'teacher' if teacher_version else 'student'}.pdf"
    filepath = os.path.join(tmpdir, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    # إنشاء style عربي
    arabic_style = ParagraphStyle(
        'Arabic',
        parent=styles['Normal'],
        fontName=ARABIC_FONT,
        fontSize=11,
        leading=16,
        alignment=TA_RIGHT,
        spaceAfter=12
    )
    
    title_style = ParagraphStyle(
        'ArabicTitle',
        parent=styles['Heading1'],
        fontName=ARABIC_FONT,
        fontSize=16,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor('#1a5276')
    )
    
    story = []
    
    # العنوان
    title_text = reshape_arabic(f"اختبار {exam.exam_type} - {exam.subject} - {exam.grade}")
    story.append(Paragraph(title_text, title_style))
    
    info_text = reshape_arabic(f"الموضوع: {exam.topic} | الصعوبة: {exam.difficulty} | النقاط: {exam.total_points}")
    story.append(Paragraph(info_text, arabic_style))
    story.append(Spacer(1, 20))
    
    # الأسئلة
    for i, q in enumerate(questions, 1):
        q_text = reshape_arabic(f"السؤال {i} ({q.get('points', 0)} نقطة): {q.get('text', '')}")
        story.append(Paragraph(q_text, arabic_style))
        
        if q.get('type') == 'mcq' and q.get('options'):
            for opt_idx, opt in enumerate(q['options']):
                opt_text = reshape_arabic(f"    {chr(0x0627 + opt_idx)}) {opt}")
                story.append(Paragraph(opt_text, arabic_style))
        elif q.get('type') == 'truefalse':
            tf_text = reshape_arabic("    □ صحيح    □ خطأ")
            story.append(Paragraph(tf_text, arabic_style))
        
        story.append(Spacer(1, 10))
    
    # الإجابات النموذجية (للأستاذ فقط)
    if teacher_version:
        story.append(Spacer(1, 30))
        story.append(Paragraph(reshape_arabic("=== الإجابات النموذجية ==="), title_style))
        
        for ans in answers:
            ans_header = reshape_arabic(f"سؤال {ans.get('question_index', '?')}: {ans.get('question_text', '')}")
            story.append(Paragraph(ans_header, arabic_style))
            
            correct = reshape_arabic(f"الإجابة الصحيحة: {str(ans.get('correct_answer', ''))}")
            story.append(Paragraph(correct, arabic_style))
            
            solution = reshape_arabic(f"الحل: {ans.get('detailed_solution', '')}")
            story.append(Paragraph(solution, arabic_style))
            
            if ans.get('common_mistakes'):
                mistakes = reshape_arabic(f"أخطاء شائعة: {', '.join(ans['common_mistakes'])}")
                story.append(Paragraph(mistakes, arabic_style))
            
            story.append(Spacer(1, 15))
    
    doc.build(story)
    
    return send_file(filepath, as_attachment=True, download_name=filename)

# ====================== تصدير Aiken ======================
@app.route("/export/aiken/<int:exam_id>", methods=["GET"])
@limiter.limit("10 per minute")
def export_aiken(exam_id):
    exam = db.session.get(GeneratedExam, exam_id)
    if not exam:
        abort(404, description="الاختبار غير موجود")
    
    questions = json.loads(exam.questions) if exam.questions else []
    answers = json.loads(exam.model_answers) if exam.model_answers else []
    
    lines = []
    answer_key = {}
    
    for i, q in enumerate(questions):
        if q.get('type') == 'mcq' and q.get('options'):
            lines.append(q['text'])
            for opt_idx, opt in enumerate(q['options']):
                letter = chr(65 + opt_idx)  # A, B, C...
                lines.append(f"{letter}. {opt}")
            
            # Find correct answer letter
            correct_letter = 'A'
            for opt_idx, opt in enumerate(q['options']):
                if opt == q.get('answer'):
                    correct_letter = chr(65 + opt_idx)
                    break
            
            lines.append(f"ANSWER: {correct_letter}")
            lines.append("")
    
    aiken_text = "\n".join(lines)
    
    tmpdir = tempfile.mkdtemp()
    filename = f"exam_{exam_id}.txt"
    filepath = os.path.join(tmpdir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(aiken_text)
    
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/plain')

# ====================== تصدير GIFT ======================
@app.route("/export/gift/<int:exam_id>", methods=["GET"])
@limiter.limit("10 per minute")
def export_gift(exam_id):
    exam = db.session.get(GeneratedExam, exam_id)
    if not exam:
        abort(404, description="الاختبار غير موجود")
    
    questions = json.loads(exam.questions) if exam.questions else []
    
    lines = []
    lines.append(f"// {exam.subject} - {exam.grade} - {exam.topic}")
    lines.append(f"// Exam ID: {exam_id}")
    lines.append("")
    
    for q in questions:
        q_text = q.get('text', '').replace('~', '\~').replace('=', '\=').replace('#', '\#')
        
        if q.get('type') == 'mcq' and q.get('options'):
            lines.append(f"::Q{q.get('question_index', '')}:: {q_text} {{")
            for opt in q['options']:
                opt_clean = opt.replace('~', '\~').replace('=', '\=')
                if opt == q.get('answer'):
                    lines.append(f"    ={opt_clean}")
                else:
                    lines.append(f"    ~{opt_clean}")
            lines.append("}")
        
        elif q.get('type') == 'truefalse':
            ans = "TRUE" if q.get('answer') == True else "FALSE"
            lines.append(f"::Q{q.get('question_index', '')}:: {q_text} {{{ans}}}")
        
        elif q.get('type') in ['essay', 'application', 'problem']:
            lines.append(f"::Q{q.get('question_index', '')}:: {q_text} {{}}")
        
        lines.append("")
    
    gift_text = "\n".join(lines)
    
    tmpdir = tempfile.mkdtemp()
    filename = f"exam_{exam_id}.gift"
    filepath = os.path.join(tmpdir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(gift_text)
    
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/plain')

# ====================== الصفحة الرئيسية ======================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "مولّد الاختبارات الجزائرية",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "generate": {"url": "/generate_full_exam", "method": "POST", "description": "توليد اختبار جديد"},
            "my_exams": {"url": "/my_exams", "method": "GET", "description": "قائمة الاختبارات"},
            "exam_detail": {"url": "/exam/<id>", "method": "GET", "description": "عرض اختبار محدد"},
            "export_pdf": {"url": "/export/pdf/<id>?teacher=true|false", "method": "GET"},
            "export_aiken": {"url": "/export/aiken/<id>", "method": "GET"},
            "export_gift": {"url": "/export/gift/<id>", "method": "GET"}
        },
        "docs": "استخدم POST /generate_full_exam لتوليد اختبارات!"
    })

# ====================== تشغيل التطبيق ======================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    is_debug = os.getenv('FLASK_DEBUG', '0').lower() == '1'
    app.run(debug=is_debug, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
