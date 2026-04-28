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
from flask_migrate import Migrate  # إضافة للهجرة

# Pydantic for Data Validation
from pydantic import BaseModel, Field, model_validator
from enum import Enum

# Logging
import structlog
from structlog import get_logger

# AI Client
from groq import Groq

# PDF Generation - استخدام reportlab بدلاً من pylatex لدعم العربية
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT  # للـ RTL

# ====================== إعداد التطبيق ======================
app = Flask(__name__)

# --- إعداد قاعدة البيانات (PostgreSQL جاهز) ---
db_uri = os.getenv('DATABASE_URL', 'sqlite:///exams.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)  # للهجرة: flask db init/migrate/upgrade

# --- إعداد عميل Groq ---
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("❌ GROQ_API_KEY مطلوب.")
groq_client = Groq(api_key=api_key)

# ====================== Pydantic Models (مُصححة) ======================
class QuestionType(str, Enum):
    MCQ = "mcq"
    TRUEFALSE = "truefalse"  # إضافة الفاصلة
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

class FullGeneratedExam(BaseModel):
    questions: List[Question]
    model_answers: List[ModelAnswer]  # إضافة الفاصلة
    total_points: float = 0.0  # إضافة default

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

# ====================== إعداد الخط العربي لـ PDF ======================
def register_arabic_font():
    try:
        # حمل خط عربي (ضعه في مجلد static أو حمل runtime)
        font_path = 'NotoSansArabic-Regular.ttf'  # حمل من Google Fonts
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Arabic', font_path))
        return 'Arabic'
    except:
        return 'Helvetica'  # fallback

ARABIC_FONT = register_arabic_font()

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

# ====================== Rate Limiting مع Redis ======================
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

    app.logger.info("Rate limiting activated", event="rate_limiting_activated")

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

# ====================== الدالة الرئيسية (مع JSON Schema) ======================
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
    num_questions = min(int(data.get("num_questions", 6)), 20)  # حد أقصى

    if not all([subject, grade, topic]):
        return jsonify({"error": "الحقول subject, grade, topic مطلوبة"}), 400

    model_name = "llama-3.3-70b-versatile"
    max_retries = 3

    logger.info(event="exam_generation_started", subject=subject, grade=grade, topic=topic, num_questions=num_questions)

    system_prompt = """أنت أستاذ جزائري خبير في المنهاج الجزائري. أنشئ اختبارات متكاملة مع إجابات نموذجية دقيقة."""

    user_prompt = f"""أنشئ اختباراً في {subject} لـ {grade}، الموضوع: {topic}، {num_questions} أسئلة متنوعة (mcq, truefalse, essay, application, problem).

رد بـ JSON صارم فقط:"""  # اختصار للاختبار

    # JSON Schema للدقة
    json_schema = {
        "type": "object",
        "properties": {
            "questions": {"type": "array"},
            "model_answers": {"type": "array"},
            "total_points": {"type": "number"},
            "metadata": {"type": "object"}
        },
        "required": ["questions", "model_answers"]
    }

    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_schema", "json_schema": json_schema}  # إضافة schema
            )
            
            raw_content = response.choices[0].message.content.strip()
            # تنظيف
            raw_content = re.sub(r'^```jsons*|s*```$', '', raw_content, flags=re.MULTILINE).strip()
            raw_data = json.loads(raw_content)
            full_exam = FullGeneratedExam.model_validate(raw_data)

            # حفظ DB
            new_exam = GeneratedExam(
                subject=subject, grade=grade, semester=semester, topic=topic,
                exam_type=exam_type, difficulty=difficulty, total_points=full_exam.total_points,
                questions=json.dumps([q.model_dump() for q in full_exam.questions], ensure_ascii=False),
                model_answers=json.dumps([a.model_dump() for a in full_exam.model_answers], ensure_ascii=False),
                metadata_info=json.dumps(full_exam.metadata, ensure_ascii=False),
                ip_address=client_ip
            )
            db.session.add(new_exam)
            db.session.commit()

            duration = round(time.time() - start_time, 2)
            logger.info(event="exam_generated_successfully", db_id=new_exam.id, duration_seconds=duration)

            response_data = full_exam.model_dump(mode='json')
            response_data["validation"] = {"status": "success", "db_id": new_exam.id, "duration": duration}
            response_data["links"] = {f"/export/{fmt}/{new_exam.id}" for fmt in ["aiken", "gift", "pdf"]}
            return jsonify(response_data)

        except json.JSONDecodeError as e:
            logger.error(event="json_parse_failed", attempt=attempt+1, error=str(e))
        except Exception as e:
            logger.error(event="generation_failed", attempt=attempt+1, error=str(e))
        
        time.sleep(2 ** attempt)  # Exponential backoff

    return jsonify({"error": "فشل بعد 3 محاولات"}), 500

# باقي الـ routes (my_exams, exam/<id>, exports) كما هي مع إصلاحات صغيرة...

# مثال مختصر لـ PDF المُحدث
@app.route("/export/pdf/<int:exam_id>", methods=["GET"])
@limiter.limit("10 per minute")
def export_pdf(exam_id: int):
    teacher_version = request.args.get("teacher", "false").lower() == "true"
    exam = db.session.get(GeneratedExam, exam_id) or abort(404)  # SQLAlchemy 2.0+
    questions = json.loads(exam.questions)
    
    tmpdir = tempfile.mkdtemp()
    filename = f"exam_{exam_id}_{'teacher' if teacher_version else 'student'}.pdf"
    filepath = os.path.join(tmpdir, filename)
    
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    y = height - 2*cm
    
    c.setFont(ARABIC_FONT, 12)
    c.drawString(width - 2*cm, y, exam.subject)  # RTL alignment
    y -= 20
    # أضف الأسئلة هنا بنفس الطريقة...
    
    c.save()
    return send_file(filepath, as_attachment=True, download_name=filename)

# باقي الـ routes: my_exams, exam/<id>, aiken, gift (انسخ من الكود الأصلي مع الإصلاحات)
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "مولّد الاختبارات الجزائرية",
        "endpoints": {
            "health": "/health",
            "generate": "/generate_full_exam (POST)",
            "my_exams": "/my_exams",
            "exam/<id>": "/exam/1"
        },
        "docs": "استخدم POST لتوليد اختبارات!"
    })
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    is_debug = os.getenv('FLASK_DEBUG', '0').lower() == '1'
    app.run(debug=is_debug, host='0.0.0.0')
