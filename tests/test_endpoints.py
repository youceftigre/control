"""اختبارات تكاملية بسيطة للـ endpoints التي لا تتطلّب Groq."""

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"


def test_curriculum_endpoint(client):
    r = client.get("/curriculum")
    assert r.status_code == 200
    body = r.get_json()
    assert "stages" in body and "subjects" in body
    assert "exam_types" in body
    # تأكّد من وجود الأطوار الثلاثة
    assert set(body["stages"]) == {"primary", "middle", "secondary"}


def test_curriculum_validate_exact(client):
    r = client.post(
        "/curriculum/validate",
        json={"subject": "الرياضيات", "grade": "السنة 3 علوم"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["is_exact"] is True
    assert body["stage"] == "secondary"
    assert body["coefficient"] == 5
    assert body["subject_canonical"] == "رياضيات"


def test_curriculum_validate_missing_fields(client):
    r = client.post("/curriculum/validate", json={"subject": "رياضيات"})
    assert r.status_code == 400


def test_curriculum_validate_returns_warnings(client):
    r = client.post(
        "/curriculum/validate",
        json={"subject": "السباحة", "grade": "السنة الأولى ابتدائي"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["is_exact"] is False
    assert body["warnings"]


def test_generate_missing_groq_returns_503(client):
    """عند غياب GROQ_API_KEY، يجب أن نُرجع 503 بشكل واضح وليس 500."""
    r = client.post("/generate", json={
        "subject": "رياضيات",
        "grade": "السنة 3 علوم",
        "semester": "الفصل الثاني",
        "topic": "الدوال",
    })
    assert r.status_code == 503
    body = r.get_json()
    assert "غير مهيأة" in body["error"]


def test_generate_missing_required_returns_400(client):
    r = client.post("/generate", json={"subject": "رياضيات"})
    assert r.status_code == 400


def test_get_unknown_exam_returns_404(client):
    r = client.get("/exam/999999")
    assert r.status_code == 404
    assert "العثور" in r.get_json()["error"]


def test_export_unknown_exam_returns_404(client):
    r = client.get("/export/aiken/999999")
    assert r.status_code == 404
    r2 = client.get("/export/gift/999999")
    assert r2.status_code == 404


def test_exam_styles_endpoint(client):
    r = client.get("/exam-styles")
    assert r.status_code == 200
    body = r.get_json()
    styles = body["styles"]
    assert {"default", "dzexams", "bem", "bac"}.issubset(styles)
    assert styles["dzexams"]["uses_situations"] is True
    assert "name_ar" in styles["bem"]


def test_export_pdf_unknown_exam_with_style_returns_404(client):
    r = client.get("/export/pdf/999999?style=dzexams")
    assert r.status_code == 404


def test_generate_returns_model_answers_field(client, monkeypatch):
    """تحقق أن /generate يعيد model_answers (مهم للواجهة لرسم التصحيح النموذجي)."""
    from app import (
        FullGeneratedExam,
        MCQQuestion,
        ProblemQuestion,
        ModelAnswer,
        QuestionType,
    )

    def mock_generate(data, client_ip=None):
        exam = FullGeneratedExam(
            questions=[
                MCQQuestion(
                    type=QuestionType.MCQ,
                    difficulty=1,
                    text="اختر الإجابة الصحيحة لـ 2+2",
                    points=2.0,
                    options=["3", "4", "5"],
                    answer="4",
                ),
                ProblemQuestion(
                    type=QuestionType.PROBLEM,
                    difficulty=3,
                    text="السياق: مزرعة. السند: 100 شجرة. التعليمات: 1. احسب...",
                    points=8.0,
                ),
            ],
            model_answers=[
                ModelAnswer(
                    question_index=0,
                    question_text="اختر الإجابة الصحيحة لـ 2+2",
                    correct_answer="4",
                    detailed_solution="2+2=4 مباشرة.",
                    competence="عمليات حسابية",
                    common_mistakes=["الخلط مع 5"],
                ),
                ModelAnswer(
                    question_index=1,
                    question_text="السياق: مزرعة...",
                    correct_answer="نتيجة المسألة",
                    detailed_solution="1. ... 2. ...",
                    competence="حل وضعية",
                    points_breakdown={"تطبيق القاعدة": 4.0, "الحساب": 4.0},
                ),
            ],
            total_points=10.0,
            metadata={"subject": "الرياضيات", "grade": "السنة 4 متوسط"},
        )
        return exam, 1

    monkeypatch.setattr("app._generate_exam_internal", mock_generate)
    resp = client.post("/generate", json={
        "subject": "الرياضيات",
        "grade": "السنة 4 متوسط",
        "semester": "الفصل الثاني",
        "topic": "الجبر",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "model_answers" in data
    assert len(data["model_answers"]) == 2
    assert data["model_answers"][0]["correct_answer"] == "4"
    assert "points_breakdown" in data["model_answers"][1]
