"""
تطبيق توليد الاختبارات الجزائرية - النسخة النهائية
مبني باستخدام Flask + Groq + Pydantic + structlog
"""

import os
import json
import time
import uuid
from datetime import datetime
from typing import List, Union, Any, Optional

from flask import Flask, request, jsonify, g, send_file
from flask_sqlalchemy import SQLAlchemy
from pydantic import BaseModel, Field, model_validator
from enum import Enum

import structlog
from structlog import get_logger
from groq import Groq
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# ====================== إعداد التطبيق ======================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exams.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key')

db = SQLAlchemy(app)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

logger = get_logger("app")

# ====================== إعداد structlog ======================
def setup_structlog():
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if app.debug:
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
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

    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        structlog.contextvars.bind_contextvars(
            request_id=g.request_id,
            ip=request.remote_addr,
            method=request.method,
            path=request.path
        )
        logger.info("Request started", event="request_started")

    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            logger.info("Request completed", 
                        event="request_completed",
                        status_code=response.status_code,
                        duration_ms=duration_ms)
        return response

    logger.info("✅ structlog initialized successfully")
    return True

setup_structlog()

# ====================== Pydantic Schemas ======================
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

class ApplicationOrProblem(BaseQuestion):
    type: QuestionType

Question = Union[MCQQuestion, TrueFalseQuestion, EssayQuestion, ApplicationOrProblem]

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
    model_answers: List[ModelAnswer]
    total_points: float
    metadata: dict

    @model_validator(mode='after')
    def calculate_total(self):
        self.total_points = round(sum(q.points for q in self.questions), 2)
        return self

# ====================== Database Model ======================
class GeneratedExam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    grade = db.Column(db.String(50), nullable=False, index=True)
    semester = db.Column(db.String(50))
    topic = db.Column(db.String(200), nullable=False)
    exam_type = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))
    total_points = db.Column(db.Float)
    questions = db.Column(db.Text, nullable=False)
    model_answers = db.Column(db.Text)
    metadata_info = db.Column(db.Text)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(50))

# ====================== الدالة الرئيسية ======================
@app.route("/generate_full_exam", methods=["POST"])
def generate_full_exam():
    start_time = time.time()
    client_ip = request.remote_addr
    logger = get_logger("app")

    data = request.get_json() or {}

    subject = data.get("subject", "").strip()
    grade = data.get("grade", "").strip()
    semester = data.get("semester", "").strip()
    exam_type = data.get("examType", "اختبار فصلي")
    topic = data.get("topic", "").strip()
    difficulty = data.get("difficulty", "متوسط")
    num_questions = int(data.get("num_questions", 6))

    if not all([subject, grade, topic]):
        return jsonify({"error": "الحقول subject, grade, topic مطلوبة"}), 400

    max_retries = 2

    logger.info("بدء توليد اختبار", subject=subject, grade=grade, topic=topic)

    for attempt in range(max_retries):
        try:
            prompt = f"""أنت أستاذ جزائري خبير منذ أكثر من 20 سنة في إعداد الاختبارات حسب الجيل الثاني.

المهمة: أنشئ {exam_type} كاملاً مع إجابات نموذجية في مادة **{subject}**، المستوى **{grade}**، الفصل **{semester}**، الموضوع **{topic}**.
مستوى الصعوبة: **{difficulty}**.

- أنشئ بالضبط {num_questions} سؤالاً متنوعاً.
- ركز على الكفاءات والواقع الجزائري.
- استخدم LaTeX عند الحاجة.
- غير السياقات والأرقام في كل مرة.

أعد JSON فقط بهذا الهيكل:
{{
  "questions": [...],
  "model_answers": [...],
  "total_points": ...,
  "metadata": {{...}}
}}
"""

            # الاتصال بـ Groq
            chat_completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "أنت متخصص في المناهج الجزائرية. أجب بـ JSON صالح فقط."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.25,
                max_tokens=5800,
                response_format={"type": "json_object"}
            )

            content = chat_completion.choices[0].message.content.strip()

            # تنظيف JSON
            for prefix in ["```json", "```"]:
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
            if content.endswith("```"):
                content = content[:-3].strip()

            raw_data = json.loads(content)
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

            logger.info("تم توليد الاختبار بنجاح", 
                        db_id=new_exam.id, 
                        total_questions=len(full_exam.questions),
                        duration_seconds=duration)

            response_data = full_exam.model_dump(mode='json')
            response_data["validation"] = {
                "status": "success",
                "db_id": new_exam.id,
                "duration_seconds": duration
            }

            return jsonify(response_data)

        except Exception as e:
            logger.error("فشل في توليد الاختبار", attempt=attempt+1, error=str(e))
            if attempt == max_retries - 1:
                return jsonify({"error": "فشل بعد محاولتين", "details": str(e)}), 500
            time.sleep(1.5)

    return jsonify({"error": "خطأ غير متوقع"}), 500


# ====================== Routes إضافية بسيطة ======================
@app.route("/my_exams", methods=["GET"])
def get_my_exams():
    exams = GeneratedExam.query.order_by(GeneratedExam.generated_at.desc()).limit(20).all()
    return jsonify([{
        "id": e.id,
        "subject": e.subject,
        "grade": e.grade,
        "topic": e.topic,
        "total_points": e.total_points,
        "generated_at": e.generated_at.isoformat()
    } for e in exams])


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "exam_generator"})


# ====================== تشغيل التطبيق ======================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
