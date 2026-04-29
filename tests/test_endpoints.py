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
