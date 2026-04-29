import os
import html
import io
import json
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

# Flask & Extensions
from flask import Flask, g, jsonify, render_template, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

# Pydantic for Data Validation
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# Algerian curriculum catalog (subjects × grades × stages)
from curriculum import (
    CurriculumMatch,
    get_exam_structure,
    load_curriculum,
    validate_subject_grade,
)

# Logging
import structlog
from structlog import get_logger

# AI Client
from groq import Groq

# PDF Generation - استيراد كسول حتى لا يفشل التطبيق على Render Native Python
# (الواجهة تستعمل window.print() بدلاً من /export/pdf، لكن الـ endpoint يبقى للاستعمال الإداري)
_WEASYPRINT_AVAILABLE: Optional[bool] = None


def _try_import_weasyprint():
    """Lazy import of weasyprint. يُستدعى فقط عند طلب PDF فعلياً."""
    global _WEASYPRINT_AVAILABLE
    if _WEASYPRINT_AVAILABLE is not None:
        return _WEASYPRINT_AVAILABLE
    try:
        import weasyprint  # noqa: F401
        _WEASYPRINT_AVAILABLE = True
    except (ImportError, OSError):
        # OSError يحدث على Render Native لو libpango غير متوفّر
        _WEASYPRINT_AVAILABLE = False
    return _WEASYPRINT_AVAILABLE


# ====================== إعداد التطبيق ======================
app = Flask(__name__)

# --- إعداد قاعدة البيانات ---
# على Render: يُستخدم disk mount على /data إن توفر (محدّد في render.yaml)
_DEFAULT_DB_DIR = "/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else \
    os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "exams.db")
db_uri = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- إعداد عميل Groq ---
# لا نرفع استثناء عند عدم توفر المفتاح؛ التطبيق يبدأ ونعطي خطأ واضح عند استعمال /generate
api_key = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=api_key) if api_key else None


# ====================== Pydantic Models ======================

class QuestionType(str, Enum):
    MCQ = "mcq"
    TRUEFALSE = "truefalse"
    ESSAY = "essay"
    APPLICATION = "application"
    PROBLEM = "problem"


class BaseQuestion(BaseModel):
    difficulty: int = Field(..., ge=1, le=3)
    text: str = Field(..., min_length=15)
    points: float = Field(..., gt=0)
    competence: Optional[str] = None


class MCQQuestion(BaseQuestion):
    type: Literal[QuestionType.MCQ] = QuestionType.MCQ
    options: List[str] = Field(..., min_length=2)
    answer: str

    @field_validator("options")
    @classmethod
    def options_must_be_unique(cls, v: List[str]) -> List[str]:
        """خيارات MCQ يجب أن تكون متميّزة بعد حذف الفراغات المحيطة."""
        cleaned = [opt.strip() for opt in v]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("خيارات MCQ يجب أن تكون متميّزة دون تكرار")
        if any(not c for c in cleaned):
            raise ValueError("خيارات MCQ لا يجوز أن تحوي على خيار فارغ")
        return cleaned

    @model_validator(mode="after")
    def answer_in_options(self):
        if self.answer not in self.options:
            raise ValueError("الإجابة يجب أن تكون موجودة ضمن الخيارات")
        return self


class TrueFalseQuestion(BaseQuestion):
    type: Literal[QuestionType.TRUEFALSE] = QuestionType.TRUEFALSE
    answer: bool


class EssayQuestion(BaseQuestion):
    type: Literal[QuestionType.ESSAY] = QuestionType.ESSAY


class ApplicationQuestion(BaseQuestion):
    type: Literal[QuestionType.APPLICATION] = QuestionType.APPLICATION


class ProblemQuestion(BaseQuestion):
    type: Literal[QuestionType.PROBLEM] = QuestionType.PROBLEM


# Discriminated union: pydantic uses the `type` field to pick the right variant.
# The discriminator MUST be applied to the Union itself (via Annotated), NOT to
# the surrounding List — pydantic 2.x raises TypeError otherwise.
Question = Annotated[
    Union[
        MCQQuestion,
        TrueFalseQuestion,
        EssayQuestion,
        ApplicationQuestion,
        ProblemQuestion,
    ],
    Field(discriminator="type"),
]


class ModelAnswer(BaseModel):
    question_index: int
    question_text: str
    correct_answer: Any
    detailed_solution: str
    justification: Optional[str] = None
    competence: Optional[str] = None
    common_mistakes: List[str] = Field(default_factory=list)
    points_breakdown: Optional[Dict[str, float]] = None


class FullGeneratedExam(BaseModel):
    questions: List[Question]
    model_answers: List[ModelAnswer]
    total_points: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_consistency(self):
        """
        تحقّقات عبر-حقليّة:

        1. إعادة حساب ``total_points`` من مجموع نقاط الأسئلة فعلياً
           (لا نثق في رقم الـ LLM).
        2. عدد عناصر ``model_answers`` يجب أن يساوي عدد الأسئلة.
        3. ``question_index`` داخل كلّ تصحيح يجب أن يكون فريداً وضمن النطاق.
        """
        self.total_points = round(sum(q.points for q in self.questions), 2)

        if len(self.model_answers) != len(self.questions):
            raise ValueError(
                f"عدد التصحيحات ({len(self.model_answers)}) يجب أن يساوي عدد الأسئلة "
                f"({len(self.questions)})"
            )

        seen_indices: set[int] = set()
        n = len(self.questions)
        for ans in self.model_answers:
            if ans.question_index < 0 or ans.question_index >= n:
                raise ValueError(
                    f"question_index={ans.question_index} خارج النطاق [0, {n - 1}]"
                )
            if ans.question_index in seen_indices:
                raise ValueError(
                    f"question_index={ans.question_index} مكرّر في model_answers"
                )
            seen_indices.add(ans.question_index)

        return self


# ====================== نموذج قاعدة البيانات ======================

class GeneratedExam(db.Model):
    __tablename__ = "generated_exams"

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
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(50))


# ====================== إعداد Structlog ======================

def setup_structlog(flask_app: Flask) -> Flask:
    log_dir = "logs"
    if not os.path.exists(log_dir):
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

    if flask_app.debug:
        processors = shared_processors + [
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = get_logger("app")
    flask_app.logger = logger  # type: ignore[assignment]

    @flask_app.before_request
    def before_request_logging():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        structlog.contextvars.bind_contextvars(
            request_id=g.request_id,
            ip=request.remote_addr,
            method=request.method,
            path=request.path,
        )
        logger.info(event="request_started")

    @flask_app.after_request
    def after_request_logging(response):
        if hasattr(g, "start_time"):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            logger.info(
                event="request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        return response

    logger.info(event="structured_logging_initialized")
    return flask_app


# ====================== Rate Limiting ======================

def setup_rate_limiting(flask_app: Flask) -> Limiter:
    storage_uri = os.getenv("RATE_LIMIT_STORAGE", "memory://")

    rate_limiter = Limiter(
        key_func=get_remote_address,
        app=flask_app,
        default_limits=["60 per minute"],
        storage_uri=storage_uri,
        strategy="fixed-window",
    )

    @rate_limiter.request_filter
    def exempt_health_check():
        return request.path.startswith("/health")

    @flask_app.errorhandler(429)
    def ratelimit_handler(e):
        logger = get_logger("app")
        logger.warning(
            event="rate_limit_exceeded",
            ip=get_remote_address(),
            path=request.path,
        )
        return jsonify({
            "error": "تم تجاوز الحد المسموح به من الطلبات",
            "message": "يرجى الانتظار قليلاً قبل المحاولة مرة أخرى",
            "retry_after": str(e.description),
        }), 429

    get_logger("app").info(event="rate_limiting_activated")
    return rate_limiter


# Configure logging BEFORE rate limiting so app.logger is the structlog logger
# when downstream code calls it with kwargs like event=...
setup_structlog(app)
limiter = setup_rate_limiting(app)

# Create tables at import time so this also works under gunicorn/uwsgi.
with app.app_context():
    db.create_all()


# ====================== Health Check ======================

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "exam_generator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ====================== واجهة HTML ======================

@app.route("/", methods=["GET"])
def index():
    """تقديم صفحة الواجهة الرئيسية."""
    return render_template("index.html")


# ====================== بنك الأسئلة ======================
# الواجهة تستدعي `GET /questions` عند الإقلاع لتعبئة البنك المحلي.
# البنية المتوقعة: { "<subject>": { "<grade>": { "<chapter>": [questions...] } } }
# إذا وجد ملف questions_bank.json في مجلد المشروع سيُحمل منه، وإلا سيُعاد وثائق فارغة.

# بنك الأسئلة: المسار الافتراضي هو data/questions_full_bank.json (ما يتبعه الريبو)
QUESTION_BANK_FILE = os.getenv("QUESTION_BANK_FILE", "data/questions_full_bank.json")
SUBJECTS_CONFIG_FILE = os.getenv("SUBJECTS_CONFIG_FILE", "data/subjects_config.json")


@app.route("/questions", methods=["GET"])
@limiter.limit("60 per minute")
def get_questions_bank():
    logger = get_logger("app")
    bank_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), QUESTION_BANK_FILE)

    if not os.path.exists(bank_path):
        logger.info(event="question_bank_missing", path=bank_path)
        return jsonify({})

    try:
        with open(bank_path, encoding="utf-8") as f:
            bank = json.load(f)
        logger.info(event="question_bank_loaded", subjects=len(bank))
        return jsonify(bank)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(event="question_bank_load_failed", error=str(e))
        return jsonify({})


# ====================== كتالوج المنهاج الجزائري ======================

@app.route("/curriculum", methods=["GET"])
@limiter.limit("60 per minute")
def get_curriculum():
    """
    أعِد كتالوج المنهاج الجزائري (المراحل، الشُّعب، المواد، أنواع الاختبارات…).

    يستعمله الـ frontend لتعبئة قوائم الاختيار وضمان عدم إرسال توليفات غير
    صالحة. الكتالوج مُخزَّن في ``data/algeria_curriculum.json``.
    """
    logger = get_logger("app")
    try:
        catalog = load_curriculum()
        return jsonify(catalog)
    except FileNotFoundError:
        logger.warning(event="curriculum_file_missing")
        return jsonify({"error": "ملف كتالوج المنهاج غير موجود"}), 503
    except json.JSONDecodeError as e:
        logger.error(event="curriculum_invalid_json", error=str(e))
        return jsonify({"error": "ملف كتالوج المنهاج غير صالح JSON"}), 500


@app.route("/curriculum/validate", methods=["POST"])
@limiter.limit("60 per minute")
def validate_curriculum_request():
    """
    تحقّق سريعاً من توافق توليفة (subject, grade) مع الكتالوج دون توليد اختبار.

    Body: ``{"subject": "...", "grade": "..."}``.

    Returns:
        ``{"is_exact": bool, "stage": str|null, "exam_total": float,
            "coefficient": int|null, "subject_canonical": str,
            "warnings": [str]}``
    """
    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or "").strip()
    grade = (payload.get("grade") or "").strip()
    if not subject or not grade:
        return jsonify({"error": "subject و grade مطلوبان"}), 400
    try:
        catalog = load_curriculum()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return jsonify({"error": f"تعذّر تحميل الكتالوج: {e}"}), 503

    match = validate_subject_grade(catalog, subject, grade)
    return jsonify({
        "is_exact": match.is_exact,
        "stage": match.stage,
        "exam_total": match.exam_total,
        "coefficient": match.coefficient,
        "subject_canonical": match.subject_canonical,
        "warnings": match.warnings,
    })


# ====================== التوليد المختصر للواجهة ======================
# الواجهة تستدعي `POST /generate` وتتوقع {questions: [...]}.
# هذا الـ endpoint غلاف رفيع حول /generate_full_exam: يحفظ في الـ DB و يعيد
# فقط الأسئلة (دون التصحيح النموذجي) لأنه غير لازم لـ buildExamHTML.

@app.route("/generate", methods=["POST"])
@limiter.limit("5 per minute")
def generate_for_ui():
    """
    واجهة متوافقة مع index.html.

    تستقبل: {subject, grade, semester, examType, topic, difficulty}
    تعيد: {questions: [...], db_id: int} أو {error: "..."}.
    """
    logger = get_logger("app")
    data = request.get_json(silent=True) or {}

    # توحيد الحقول لتطابق /generate_full_exam (لا نغيّر الواجهة)
    payload = {
        "subject": data.get("subject", ""),
        "grade": data.get("grade", ""),
        "semester": data.get("semester", ""),
        "branch": data.get("branch", ""),
        "examType": data.get("examType", "اختبار فصلي"),
        "topic": (data.get("topic") or "").strip() or data.get("subject", ""),
        "difficulty": data.get("difficulty", "متوسط"),
        "num_questions": data.get("num_questions", 6),
    }

    # الحد الأدنى للتحقق بنفس الدلالة التي تفرضها الواجهة
    if not all([payload["subject"], payload["grade"], payload["semester"]]):
        return jsonify({
            "error": "يرجى ملء الحقول الإلزامية: المادة، السنة، الفصل",
        }), 400

    result = _generate_exam_internal(payload, client_ip=request.remote_addr)
    # حالة الخطأ: ``result`` يكون (error_dict, status_code)
    if isinstance(result[0], dict):
        return jsonify(result[0]), result[1]

    full_exam, db_id = result
    questions_only = [q.model_dump(mode="json") for q in full_exam.questions]

    logger.info(event="ui_generate_completed", db_id=db_id, count=len(questions_only))
    response_body = {
        "success": True,
        "questions": questions_only,
        "db_id": db_id,
        "total_points": full_exam.total_points,
        "metadata": full_exam.metadata,
    }
    warnings = (full_exam.metadata or {}).get("curriculum_warnings")
    if warnings:
        response_body["warnings"] = warnings
    return jsonify(response_body)


# ====================== الدالة الرئيسية (مع Retry) ======================

# الحدّ الأعلى لـ ``num_questions``. عدد كبير من الأسئلة + تصحيح نموذجي مفصّل
# يستهلك الكثير من tokens، لذلك نُبقي السقف معقولاً.
MAX_QUESTIONS = 30

# تقدير عدد التوكنات لكلّ سؤال + تصحيح (متوسط بالعربية).
# يُستعمل لحساب ``max_tokens`` ديناميكياً.
TOKENS_PER_QUESTION = 350
MIN_MAX_TOKENS = 2000
MAX_MAX_TOKENS = 8000


def _compute_max_tokens(num_questions: int) -> int:
    """
    حساب ``max_tokens`` ديناميكياً بحسب عدد الأسئلة.

    قيمة ثابتة (4000) كانت تُقطع إجابة الـ LLM عند طلب 20+ سؤالاً مع تصحيح
    مفصّل، فيُرجَع JSON ناقص ويفشل التحليل.
    """
    estimated = num_questions * TOKENS_PER_QUESTION + 800  # +هامش للـ metadata
    return max(MIN_MAX_TOKENS, min(MAX_MAX_TOKENS, estimated))


def _build_system_prompt(stage: Optional[str], exam_type: str) -> str:
    """
    بناء ``system_prompt`` الخاص بالأستاذ/المُولّد وفق المرحلة + نوع الاختبار.

    تُستعمل المصطلحات الرسمية للمنهاج الجزائري: «الكفاءة الختامية»،
    «الوضعية الإدماجية»، «السند»، «التعليمات» …
    """
    base = """أنت أستاذ جزائري خبير في تطوير الاختبارات التعليمية وفق المناهج الرسمية للمنظومة التربوية الجزائرية.
مهمتك إنشاء اختبارات متكاملة عالية الجودة تحترم البنية الرسمية مع الإجابات النموذجية والحلول التفصيلية.

قواعد صارمة:
1. الأسئلة واضحة ومباشرة وخالية من الغموض، وتراعي مستوى التلميذ في السنة المُحدَّدة.
2. خيارات MCQ يجب أن تكون متقاربة منطقياً ومتميّزة (لا تكرار) — plausible distractors.
3. الإجابة النموذجية دقيقة ومفصّلة، مع تبرير كل خطوة.
4. اذكر الأخطاء الشائعة التي يرتكبها التلاميذ في كلّ سؤال.
5. حدِّد الكفاءة الختامية المستهدفة (competence) لكلّ سؤال وفق المنهاج الجزائري.
6. اعتمد المصطلحات الرسمية: «الكفاءة الختامية»، «الوضعية الإدماجية»، «السند»، «التعليمات».
7. أنواع الأسئلة المسموحة: mcq, truefalse, essay, application, problem (لا تستعمل أنواعاً أخرى)."""

    if stage == "primary":
        base += "\n8. سُلّم التنقيط الكلّي: 10 نقاط (المعيار الجزائري للابتدائي)."
        base += "\n9. ركّز على أنشطة الفهم البسيط ثم التطبيق + إدماج خفيف."
    elif stage == "middle":
        base += "\n8. سُلّم التنقيط الكلّي: 20 نقطة (المعيار الجزائري للمتوسط)."
        base += "\n9. البنية المُوصَى بها: الجزء الأوّل (تمارين ~12ن) + الجزء الثاني (وضعية إدماجية ~8ن)."
    elif stage == "secondary":
        base += "\n8. سُلّم التنقيط الكلّي: 20 نقطة (المعيار الجزائري للثانوي)."
        if "بكالوريا" in (exam_type or ""):
            base += (
                "\n9. اعتمد بنية البكالوريا: موضوع واحد كامل من 20 نقطة "
                "(تستطيع لاحقاً صياغة موضوع ثانٍ مستقل عند الطلب)."
            )
        else:
            base += "\n9. البنية المُوصَى بها: الجزء الأوّل (تمارين ~13ن) + الجزء الثاني (وضعية إدماجية ~7ن)."

    return base


def _build_user_prompt(
    *,
    subject: str,
    grade: str,
    semester: str,
    branch: str,
    exam_type: str,
    topic: str,
    difficulty: str,
    num_questions: int,
    structure: Optional[Dict[str, Any]],
    exam_total: float,
    coefficient: Optional[int],
) -> str:
    """بناء ``user_prompt`` بحقول صريحة + بنية رسمية حسب المنهاج."""
    structure_hint = ""
    if structure and structure.get("parts"):
        parts_desc = "، ".join(
            f"{p['name']} ({p['points']} نقطة)" for p in structure["parts"]
        )
        structure_hint = f"\nبنية الاختبار المطلوبة: {parts_desc}."

    coef_hint = f"\nالمعامل (coefficient): {coefficient}" if coefficient else ""
    branch_hint = f"\nالشعبة: {branch}" if branch else ""

    return f"""أنشئ اختباراً كاملاً في مادة {subject} للسنة {grade}، الفصل {semester or 'غير محدد'}.

الموضوع/الوحدة التعلّمية: {topic}
نوع الاختبار: {exam_type}{branch_hint}{coef_hint}
المستوى: {difficulty}
عدد الأسئلة: {num_questions}
المجموع الكلّي للنقاط: {exam_total} (معياري — يجب أن يكون مجموع points مساوياً لهذه القيمة بهامش ±0.5){structure_hint}

يجب أن يحتوي الاختبار على تنوّع في أنواع الأسئلة (MCQ، صح/خطأ، مقالي، تطبيقي/مسألة)
مع التدرّج من السهل إلى الصعب.

أعد الرد بتنسيق JSON صارم يتبع هذا الهيكل (كلّ القيم بالعربية إلا أسماء الحقول):
{{
  "questions": [
    {{
      "type": "mcq",
      "difficulty": 1,
      "text": "نص السؤال بالعربية",
      "points": 1.5,
      "competence": "اسم الكفاءة الختامية",
      "options": ["خيار أ", "خيار ب", "خيار ج", "خيار د"],
      "answer": "خيار أ"
    }}
  ],
  "model_answers": [
    {{
      "question_index": 0,
      "question_text": "نص السؤال",
      "correct_answer": "الإجابة الصحيحة",
      "detailed_solution": "شرح مفصّل للحلّ خطوة بخطوة",
      "justification": "لماذا هذه الإجابة صحيحة",
      "competence": "اسم الكفاءة الختامية",
      "common_mistakes": ["خطأ شائع 1", "خطأ شائع 2"],
      "points_breakdown": {{"فهم المفهوم": 0.5, "التطبيق": 1.0}}
    }}
  ],
  "total_points": 0.0,
  "metadata": {{
    "subject": "{subject}",
    "grade": "{grade}",
    "branch": "{branch}",
    "topic": "{topic}",
    "difficulty": "{difficulty}",
    "generated_for": "المنهاج الجزائري",
    "notes": "أي ملاحظات إضافية"
  }}
}}

شروط:
- ``model_answers`` يجب أن يحتوي على عدد عناصر = عدد الأسئلة بالضبط، مع question_index من 0 إلى {num_questions - 1}.
- ``total_points`` يُحتسب تلقائياً من مجموع points (لا تتلاعب به).
- خيارات MCQ متميّزة (لا تكرار) و answer ضمن الخيارات حرفياً.
- لا تُضف أيّ نص خارج JSON ولا تستعمل ```."""


def _generate_exam_internal(
    data: Dict[str, Any],
    client_ip: Optional[str] = None,
):
    """
    المنطق المشترك لتوليد الاختبار وفق المنهاج الجزائري.

    Args:
        data: قاموس يحتوي على ``subject``, ``grade``, ``semester``, ``examType``,
            ``topic``, ``difficulty``, ``num_questions`` (اختياري — افتراضي 6).
            يدعم أيضاً ``branch`` (الشعبة) كحقل اختياري.
        client_ip: عنوان IP للمستخدم (يُحفظ في DB لأغراض التتبع).

    Returns:
        - عند النجاح: ``(FullGeneratedExam, db_id)``.
        - عند الفشل: ``({"error": ..., ...}, status_code)``.

    Side effects:
        يحفظ سجلّاً جديداً في جدول ``generated_exams`` عند نجاح التحقق.

    مثال:
        >>> data = {
        ...     "subject": "الرياضيات",
        ...     "grade": "السنة 3 علوم",
        ...     "semester": "الفصل الثاني",
        ...     "examType": "اختبار فصلي",
        ...     "topic": "الدوال اللوغاريتمية",
        ...     "difficulty": "متوسط",
        ...     "num_questions": 6,
        ... }
        >>> result = _generate_exam_internal(data, client_ip="127.0.0.1")
    """
    logger = get_logger("app")
    start_time = time.time()

    subject = (data.get("subject") or "").strip()
    grade = (data.get("grade") or "").strip()
    semester = (data.get("semester") or "").strip()
    branch = (data.get("branch") or "").strip()
    exam_type = (data.get("examType") or "اختبار فصلي").strip()
    topic = (data.get("topic") or "").strip()
    difficulty = (data.get("difficulty") or "متوسط").strip()

    try:
        num_questions = int(data.get("num_questions", 6))
    except (TypeError, ValueError):
        return ({"error": "num_questions يجب أن يكون عدداً صحيحاً"}, 400)
    num_questions = max(1, min(num_questions, MAX_QUESTIONS))

    if not all([subject, grade, topic]):
        logger.warning(event="incomplete_request", missing_fields=["subject", "grade", "topic"])
        return ({"error": "الحقول subject, grade, topic مطلوبة"}, 400)

    # --- التحقق من توافق المادة/السنة مع كتالوج المنهاج الجزائري ---
    curriculum_warnings: List[str] = []
    stage: Optional[str] = None
    exam_total = 20.0
    coefficient: Optional[int] = None
    structure: Optional[Dict[str, Any]] = None
    try:
        catalog = load_curriculum()
        match: CurriculumMatch = validate_subject_grade(catalog, subject, grade)
        stage = match.stage
        exam_total = match.exam_total
        coefficient = match.coefficient
        curriculum_warnings = match.warnings
        # تطبيع اسم المادة إن أمكن (مثلاً "الرياضيات" → "رياضيات")
        if match.is_exact:
            subject = match.subject_canonical
        structure = get_exam_structure(catalog, stage, exam_type)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(event="curriculum_load_failed", error=str(e))
        # نواصل بدون التحقق — الكتالوج مساعد لا حاجز

    if curriculum_warnings:
        logger.info(event="curriculum_warnings", warnings=curriculum_warnings)

    if groq_client is None:
        logger.error(event="groq_client_not_configured")
        return ({
            "error": "خدمة الذكاء الاصطناعي غير مهيأة على السيرفر",
            "hint": "يجب ضبط متغير البيئة GROQ_API_KEY في إعدادات Render",
        }, 503)

    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    max_retries = 2

    logger.info(
        event="exam_generation_started",
        subject=subject,
        grade=grade,
        stage=stage,
        topic=topic,
        num_questions=num_questions,
        difficulty=difficulty,
        exam_total=exam_total,
        coefficient=coefficient,
    )

    system_prompt = _build_system_prompt(stage, exam_type)
    user_prompt = _build_user_prompt(
        subject=subject,
        grade=grade,
        semester=semester,
        branch=branch,
        exam_type=exam_type,
        topic=topic,
        difficulty=difficulty,
        num_questions=num_questions,
        structure=structure,
        exam_total=exam_total,
        coefficient=coefficient,
    )

    max_tokens = _compute_max_tokens(num_questions)
    # درجة حرارة أدنى للبكالوريا/الفروض الرسمية (لتقليل التهلوس)
    temperature = 0.5 if "بكالوريا" in exam_type or "فرض" in exam_type else 0.7

    for attempt in range(max_retries):
        try:
            response = groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or ""

            # تنظيف JSON إذا لزم الأمر
            raw_content = raw_content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            elif raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()

            try:
                raw_data = json.loads(raw_content)
                full_exam = FullGeneratedExam.model_validate(raw_data)
            except (json.JSONDecodeError, ValidationError) as ve:
                # خطأ في إخراج LLM — سنعيد المحاولة برسالة تصحيحية
                logger.warning(
                    event="llm_output_invalid",
                    attempt=attempt + 1,
                    error=str(ve)[:500],
                )
                if attempt == max_retries - 1:
                    return ({
                        "error": "فشل في تحليل إجابة نموذج الذكاء الاصطناعي",
                        "hint": "حاول إعادة الطلب أو عدّل الموضوع",
                    }, 502)
                time.sleep(1.0)
                continue

            # إثراء الـ metadata بمعلومات الكتالوج لتسهيل الاستعلام لاحقاً
            enriched_metadata = dict(full_exam.metadata or {})
            enriched_metadata.setdefault("subject", subject)
            enriched_metadata.setdefault("grade", grade)
            enriched_metadata.setdefault("topic", topic)
            enriched_metadata["stage"] = stage
            enriched_metadata["branch"] = branch or enriched_metadata.get("branch", "")
            enriched_metadata["coefficient"] = coefficient
            enriched_metadata["exam_total_official"] = exam_total
            enriched_metadata["model"] = model_name
            if curriculum_warnings:
                enriched_metadata["curriculum_warnings"] = curriculum_warnings
            full_exam.metadata = enriched_metadata

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
                    ensure_ascii=False,
                    default=str,
                ),
                model_answers=json.dumps(
                    [a.model_dump() for a in full_exam.model_answers],
                    ensure_ascii=False,
                    default=str,
                ),
                metadata_info=json.dumps(enriched_metadata, ensure_ascii=False),
                ip_address=client_ip,
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
                attempt=attempt + 1,
            )

            return (full_exam, new_exam.id)

        except Exception:
            db.session.rollback()
            logger.error(
                event="exam_generation_failed",
                attempt=attempt + 1,
                exc_info=True,
            )
            if attempt == max_retries - 1:
                return ({
                    "error": "فشل في إنشاء الاختبار بعد عدة محاولات",
                    "request_id": getattr(g, "request_id", None),
                }, 500)
            time.sleep(1.5)

    return ({"error": "خطأ غير متوقع"}, 500)


@app.route("/generate_full_exam", methods=["POST"])
@limiter.limit("5 per minute")
def generate_full_exam():
    """الـ endpoint الأصلي: يعيد الاختبار بالكامل مع التصحيح النموذجي."""
    data = request.get_json(silent=True) or {}
    result = _generate_exam_internal(data, client_ip=request.remote_addr)

    if isinstance(result, tuple) and isinstance(result[0], dict):
        return jsonify(result[0]), result[1]

    full_exam, db_id = result
    response_data = full_exam.model_dump(mode="json")
    response_data["validation"] = {
        "status": "success",
        "db_id": db_id,
    }
    response_data["links"] = {
        "view_exam": f"/exam/{db_id}",
        "my_exams": "/my_exams",
        "export_aiken": f"/export/aiken/{db_id}",
        "export_gift": f"/export/gift/{db_id}",
        "export_pdf": f"/export/pdf/{db_id}",
    }
    return jsonify(response_data)


# ====================== عرض الاختبارات ======================

@app.route("/my_exams", methods=["GET"])
@limiter.limit("30 per minute")
def get_my_exams():
    logger = get_logger("app")

    try:
        subject = request.args.get("subject")
        grade = request.args.get("grade")
        try:
            limit = int(request.args.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        query = GeneratedExam.query.order_by(GeneratedExam.generated_at.desc())
        if subject:
            query = query.filter(GeneratedExam.subject.ilike(f"%{subject}%"))
        if grade:
            query = query.filter(GeneratedExam.grade.ilike(f"%{grade}%"))

        exams = query.limit(limit).all()

        exams_list = []
        for exam in exams:
            exams_list.append({
                "id": exam.id,
                "subject": exam.subject,
                "grade": exam.grade,
                "semester": exam.semester,
                "topic": exam.topic,
                "exam_type": exam.exam_type,
                "difficulty": exam.difficulty,
                "total_points": exam.total_points,
                "generated_at": exam.generated_at.isoformat() if exam.generated_at else None,
                "ip_address": exam.ip_address,
                "links": {
                    "view": f"/exam/{exam.id}",
                    "download_json": f"/exam/{exam.id}",
                    "download_pdf": f"/export/pdf/{exam.id}",
                    "export_aiken": f"/export/aiken/{exam.id}",
                    "export_gift": f"/export/gift/{exam.id}",
                },
            })

        logger.info(
            event="exams_list_retrieved",
            count=len(exams_list),
            subject_filter=subject,
            grade_filter=grade,
        )
        return jsonify({
            "success": True,
            "total": len(exams_list),
            "exams": exams_list,
        })

    except Exception as e:
        logger.error(event="failed_to_retrieve_exams", error=str(e), exc_info=True)
        return jsonify({"error": "حدث خطأ أثناء جلب الاختبارات"}), 500


# ====================== جلب اختبار واحد ======================

@app.route("/exam/<int:exam_id>", methods=["GET"])
@limiter.limit("30 per minute")
def get_exam_by_id(exam_id: int):
    logger = get_logger("app")

    exam = db.session.get(GeneratedExam, exam_id)
    if exam is None:
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404

    try:
        response = {
            "id": exam.id,
            "subject": exam.subject,
            "grade": exam.grade,
            "semester": exam.semester,
            "topic": exam.topic,
            "exam_type": exam.exam_type,
            "difficulty": exam.difficulty,
            "total_points": exam.total_points,
            "generated_at": exam.generated_at.isoformat() if exam.generated_at else None,
            "questions": json.loads(exam.questions) if exam.questions else [],
            "model_answers": json.loads(exam.model_answers) if exam.model_answers else [],
            "metadata": json.loads(exam.metadata_info) if exam.metadata_info else {},
            "links": {
                "export_aiken": f"/export/aiken/{exam.id}",
                "export_gift": f"/export/gift/{exam.id}",
                "export_pdf": f"/export/pdf/{exam.id}",
            },
        }
        logger.info(event="exam_retrieved", exam_id=exam_id, subject=exam.subject)
        return jsonify(response)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(event="failed_to_decode_exam", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "تعذّر تحليل بيانات الاختبار المحفوظة"}), 500


# ====================== تصدير Aiken ======================

@app.route("/export/aiken/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_aiken(exam_id: int):
    logger = get_logger("app")

    exam = db.session.get(GeneratedExam, exam_id)
    if exam is None:
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404

    try:
        questions = json.loads(exam.questions) if exam.questions else []

        aiken_content: List[str] = []
        skipped_truefalse = 0
        for q in questions:
            qtype = q.get("type")
            text = (q.get("text") or "").strip()
            if not text:
                continue
            if qtype == "mcq":
                aiken_content.append(text)
                options = q.get("options") or []
                # Aiken expects A., B., C., ... prefixes and ANSWER: <letter>
                for idx, option in enumerate(options):
                    letter = chr(ord("A") + idx)
                    aiken_content.append(f"{letter}. {option}")
                answer = q.get("answer", "")
                try:
                    answer_idx = options.index(answer)
                    answer_letter = chr(ord("A") + answer_idx)
                except ValueError:
                    answer_letter = ""
                aiken_content.append(f"ANSWER: {answer_letter}")
                aiken_content.append("")
            elif qtype == "truefalse":
                # صيغة Aiken الرسمية تدعم MCQ فقط.
                # أسئلة True/False تُصديرها عبر GIFT بدلاً من ذلك.
                skipped_truefalse += 1

        aiken_text = "\n".join(aiken_content)
        filename = f"exam_{exam_id}_aiken.txt"

        logger.info(
            event="aiken_exported",
            exam_id=exam_id,
            mcq_count=len([q for q in questions if q.get("type") == "mcq"]),
            skipped_truefalse=skipped_truefalse,
        )
        response_payload = {
            "success": True,
            "format": "Aiken",
            "filename": filename,
            "content": aiken_text,
            "instructions": "في Moodle: Question Bank → Import → اختر صيغة Aiken Format ثم الصق المحتوى",
        }
        if skipped_truefalse:
            response_payload["warnings"] = [
                f"تم تجاوز {skipped_truefalse} سؤال صح/خطأ — صيغة Aiken لا تدعمها رسمياً. "
                "استعمل GIFT لتصديرها."
            ]
        return jsonify(response_payload)

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(event="aiken_export_failed", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "تعذّر تحليل أسئلة الاختبار للتصدير"}), 500


# ====================== تصدير GIFT ======================
# https://docs.moodle.org/en/GIFT_format — must escape: ~ = # { } : \
# ملحوظة: في صيغة GIFT يُهرّب الـ backslash الواحد بـ backslash-backslash (أي \\)،
# فترجمة ``\\`` إلى ``\\\\`` خاطئة (تطبع أربع فواصل عكسية).
GIFT_SPECIAL = str.maketrans({
    "~": r"\~",
    "=": r"\=",
    "#": r"\#",
    "{": r"\{",
    "}": r"\}",
    ":": r"\:",
    "\\": r"\\",
})


def _gift_escape(s: Any) -> str:
    return str(s).translate(GIFT_SPECIAL)


@app.route("/export/gift/<int:exam_id>", methods=["GET"])
@limiter.limit("15 per minute")
def export_gift(exam_id: int):
    logger = get_logger("app")

    exam = db.session.get(GeneratedExam, exam_id)
    if exam is None:
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404

    try:
        questions = json.loads(exam.questions) if exam.questions else []

        gift_content: List[str] = []
        for i, q in enumerate(questions):
            qtype = q.get("type")
            text = (q.get("text") or "").strip()
            if not text:
                continue
            if qtype == "mcq":
                gift_content.append(f"::Q{i + 1}:: {_gift_escape(text)} {{")
                for opt in q.get("options") or []:
                    prefix = "=" if opt == q.get("answer") else "~"
                    gift_content.append(f"{prefix}{_gift_escape(opt)}")
                gift_content.append("}")
                gift_content.append("")
            elif qtype == "truefalse":
                answer = "TRUE" if q.get("answer") else "FALSE"
                gift_content.append(f"::Q{i + 1}:: {_gift_escape(text)} {{ {answer} }}")
                gift_content.append("")

        gift_text = "\n".join(gift_content)
        filename = f"exam_{exam_id}_gift.txt"

        logger.info(event="gift_exported", exam_id=exam_id)
        return jsonify({
            "success": True,
            "format": "GIFT",
            "filename": filename,
            "content": gift_text,
            "instructions": "في Moodle: Question Bank → Import → اختر صيغة GIFT ثم ارفع الملف أو الصق المحتوى",
        })

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(event="gift_export_failed", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "تعذّر تحليل أسئلة الاختبار للتصدير"}), 500


# ====================== تصدير PDF (WeasyPrint) ======================
# WeasyPrint يحوّل HTML/CSS → PDF و يدعم العربية و RTL بشكل ممتاز.
# المتطلبات على Debian/Ubuntu:
#   sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
#   pip install weasyprint
# يُستحسن تثبيت خط عربي مثل Amiri أو Noto Naskh Arabic:
#   sudo apt install fonts-noto-naskh-arabic fonts-amiri

PDF_CSS = """
@page {
    size: A4;
    margin: 1.8cm 1.8cm 2cm 1.8cm;
    @top-right { content: "وزارة التربية الوطنية"; font-size: 10pt; color: #555; }
    @top-left  { content: string(subject_grade); font-size: 10pt; color: #555; }
    @top-center{ content: string(topic_header);  font-size: 10pt; color: #555; }
    @bottom-right { content: "صفحة " counter(page) " / " counter(pages); font-size: 9pt; color: #777; }
}
html { direction: rtl; }
body {
    font-family: "Amiri", "Noto Naskh Arabic", "Scheherazade New", "DejaVu Sans", serif;
    font-size: 12pt;
    line-height: 1.7;
    color: #1a1a1a;
    direction: rtl;
    text-align: right;
}
h1.exam-title { text-align: center; font-size: 20pt; margin: 0 0 4pt 0; }
p.exam-meta   { text-align: center; font-size: 12pt; margin: 0; color: #333; }
p.exam-topic  { text-align: center; font-size: 11pt; margin: 0 0 18pt 0; color: #555; }
hr.divider    { border: 0; border-top: 1px solid #999; margin: 12pt 0 18pt 0; }
section.question {
    margin-bottom: 14pt;
    page-break-inside: avoid;
}
section.question h2 {
    font-size: 13pt;
    background: #f0f4f8;
    border-right: 4px solid #2c5282;
    padding: 6pt 10pt;
    margin: 0 0 8pt 0;
}
section.question .points { color: #2c5282; font-weight: normal; font-size: 11pt; }
section.question .qtext  { margin: 4pt 0 6pt 0; }
ol.options { margin: 4pt 25pt 4pt 0; padding: 0; }
ol.options li { margin-bottom: 3pt; }
div.answer-box {
    margin-top: 8pt;
    padding: 8pt 12pt;
    background: #fff8e1;
    border-right: 4px solid #d97706;
    border-radius: 2pt;
    font-size: 11pt;
}
div.answer-box .label { font-weight: bold; color: #92400e; }
div.answer-box .solution { margin-top: 4pt; white-space: pre-wrap; }
div.answer-box ul.mistakes { margin: 4pt 20pt 0 0; padding: 0; }
.string-subject-grade { string-set: subject_grade content(); display: none; }
.string-topic-header  { string-set: topic_header content();  display: none; }
"""


def _esc(value: Any) -> str:
    """HTML-escape any value (handles None safely)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _render_question_html(index: int, q: Dict[str, Any]) -> str:
    points = q.get("points", 1)
    parts: List[str] = [
        '<section class="question">',
        f'<h2>السؤال {index + 1} <span class="points">({_esc(points)} نقطة)</span></h2>',
        f'<div class="qtext">{_esc(q.get("text", ""))}</div>',
    ]

    qtype = q.get("type")
    if qtype == "mcq" and q.get("options"):
        parts.append('<ol class="options">')
        for opt in q["options"]:
            parts.append(f"<li>{_esc(opt)}</li>")
        parts.append("</ol>")
    elif qtype == "truefalse":
        parts.append('<ol class="options"><li>صحيح</li><li>خطأ</li></ol>')

    parts.append("</section>")
    return "".join(parts)


def _render_answer_html(index: int, ans: Dict[str, Any]) -> str:
    parts: List[str] = [
        '<div class="answer-box">',
        f'<div><span class="label">الإجابة الصحيحة:</span> {_esc(ans.get("correct_answer", ""))}</div>',
    ]

    solution = ans.get("detailed_solution")
    if solution:
        parts.append(
            '<div class="solution"><span class="label">الحل التفصيلي:</span><br>'
            f"{_esc(solution)}</div>"
        )

    justification = ans.get("justification")
    if justification:
        parts.append(
            '<div class="solution"><span class="label">المبرر:</span> '
            f"{_esc(justification)}</div>"
        )

    mistakes = ans.get("common_mistakes") or []
    if mistakes:
        parts.append('<div class="solution"><span class="label">الأخطاء الشائعة:</span>')
        parts.append('<ul class="mistakes">')
        for m in mistakes:
            parts.append(f"<li>{_esc(m)}</li>")
        parts.append("</ul></div>")

    parts.append("</div>")
    return "".join(parts)


def _build_exam_html(
    exam: "GeneratedExam",
    questions: List[Dict[str, Any]],
    model_answers: Optional[List[Dict[str, Any]]],
) -> str:
    sections: List[str] = []
    for i, q in enumerate(questions):
        sections.append(_render_question_html(i, q))
        if model_answers and i < len(model_answers):
            sections.append(_render_answer_html(i, model_answers[i]))

    subject_grade = f"{exam.subject} - {exam.grade}"
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{_esc(exam.exam_type)} - {_esc(exam.subject)}</title>
</head>
<body>
<span class="string-subject-grade">{_esc(subject_grade)}</span>
<span class="string-topic-header">{_esc(exam.topic)}</span>

<h1 class="exam-title">{_esc(exam.exam_type)} - {_esc(exam.subject)}</h1>
<p class="exam-meta">{_esc(exam.grade)} | {_esc(exam.semester or '')}</p>
<p class="exam-topic">الموضوع: {_esc(exam.topic)}</p>
<hr class="divider">

{''.join(sections)}
</body>
</html>"""


@app.route("/export/pdf/<int:exam_id>", methods=["GET"])
@limiter.limit("20 per minute")
def export_pdf(exam_id: int):
    logger = get_logger("app")
    teacher_version = request.args.get("teacher", "false").lower() == "true"

    exam = db.session.get(GeneratedExam, exam_id)
    if exam is None:
        return jsonify({"error": "لم يتم العثور على الاختبار"}), 404

    if not _try_import_weasyprint():
        return jsonify({
            "error": "تصدير PDF غير متاح على هذا السيرفر",
            "hint": "استخدم زر 'طباعة / حفظ PDF' في الواجهة (يعمل عبر المتصفّح)",
        }), 503

    try:
        questions = json.loads(exam.questions) if exam.questions else []
        model_answers = (
            json.loads(exam.model_answers)
            if teacher_version and exam.model_answers
            else None
        )

        from weasyprint import HTML, CSS  # استيراد كسول
        html_doc = _build_exam_html(exam, questions, model_answers)
        pdf_bytes = HTML(string=html_doc).write_pdf(stylesheets=[CSS(string=PDF_CSS)])

        version = "مع_التصحيح" if teacher_version else "للتلميذ"
        filename = f"{exam.subject}_{exam.grade}_{exam.topic}_{version}.pdf".replace(" ", "_")

        logger.info(
            event="pdf_exported_successfully",
            exam_id=exam_id,
            teacher_version=teacher_version,
            filename=filename,
            size_bytes=len(pdf_bytes),
        )
        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(event="pdf_export_decode_failed", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({"error": "تعذّر تحليل بيانات الاختبار للتصدير"}), 500
    except Exception as e:
        logger.error(event="pdf_export_failed", exam_id=exam_id, error=str(e), exc_info=True)
        return jsonify({
            "error": "فشل في إنشاء ملف PDF",
            "details": str(e),
            "hint": "تأكد من تثبيت WeasyPrint وخطوط عربية (مثل fonts-noto-naskh-arabic) على السيرفر",
        }), 500


# ====================== /api/* aliases (لتوافقية مع test_api.py) ======================
# هذه aliases للـ endpoints الموجودة بالفعل، حتى يعمل test_api.py الموجود في الريبو
# الذي يستعمل BASE_URL = "http://localhost:5000/api".

@app.route("/api/questions", methods=["GET"])
@limiter.limit("60 per minute")
def api_questions():
    return get_questions_bank()


@app.route("/api/generate", methods=["POST"])
@limiter.limit("5 per minute")
def api_generate():
    return generate_for_ui()


@app.route("/api/stats", methods=["GET"])
@limiter.limit("30 per minute")
def api_stats():
    """إحصائيات بنك الأسئلة (لـ test_api.py)."""
    bank_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), QUESTION_BANK_FILE)
    if not os.path.exists(bank_path):
        return jsonify({"total_questions": 0, "by_level": {}, "by_type": {}, "by_difficulty": {}})

    try:
        with open(bank_path, encoding="utf-8") as f:
            bank = json.load(f)
    except (OSError, json.JSONDecodeError):
        return jsonify({"total_questions": 0, "by_level": {}, "by_type": {}, "by_difficulty": {}})

    by_level: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    by_difficulty: Dict[str, int] = {}
    total = 0

    if isinstance(bank, dict):
        for _subject, grades in bank.items():
            if not isinstance(grades, dict):
                continue
            for grade_name, chapters in grades.items():
                if not isinstance(chapters, dict):
                    continue
                for _chapter, qs in chapters.items():
                    if not isinstance(qs, list):
                        continue
                    total += len(qs)
                    by_level[grade_name] = by_level.get(grade_name, 0) + len(qs)
                    for q in qs:
                        if not isinstance(q, dict):
                            continue
                        qt = q.get("type", "unknown")
                        by_type[qt] = by_type.get(qt, 0) + 1
                        diff = str(q.get("difficulty", "unknown"))
                        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

    return jsonify({
        "total_questions": total,
        "by_level": by_level,
        "by_type": by_type,
        "by_difficulty": by_difficulty,
    })


@app.route("/api/filter-bank", methods=["POST"])
@limiter.limit("30 per minute")
def api_filter_bank():
    """ترشيح بنك الأسئلة حسب subject/grade/topic (لـ test_api.py)."""
    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or "").strip()
    grade = (payload.get("grade") or "").strip()
    topic = (payload.get("topic") or "").strip()

    bank_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), QUESTION_BANK_FILE)
    if not os.path.exists(bank_path):
        return jsonify({"questions": []})

    try:
        with open(bank_path, encoding="utf-8") as f:
            bank = json.load(f)
    except (OSError, json.JSONDecodeError):
        return jsonify({"questions": []})

    matched: List[Dict[str, Any]] = []
    if isinstance(bank, dict):
        subjects = [subject] if subject and subject in bank else list(bank.keys())
        for s in subjects:
            grades = bank.get(s) or {}
            if not isinstance(grades, dict):
                continue
            grade_keys = [grade] if grade and grade in grades else list(grades.keys())
            for grade_name in grade_keys:
                chapters = grades.get(grade_name) or {}
                if not isinstance(chapters, dict):
                    continue
                for chapter, qs in chapters.items():
                    if topic and topic not in chapter:
                        continue
                    if isinstance(qs, list):
                        matched.extend(qs)

    return jsonify({"questions": matched, "count": len(matched)})


@app.route("/api/health", methods=["GET"])
def api_health():
    return health_check()


# ====================== تشغيل التطبيق ======================

if __name__ == "__main__":
    is_debug = os.getenv("FLASK_DEBUG", "0").lower() == "1"
    app.run(debug=is_debug, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
