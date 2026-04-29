"""End-to-end smoke tests for app.py using Flask test client.

Exercises every endpoint, validates real DB writes/reads, JSON shape, and the
WeasyPrint PDF export. The Groq API call is monkey-patched so no network is hit.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

# ---- Set up env BEFORE importing app ----
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
DB_FILE = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_FILE.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE.name}"

# Add the directory containing app.py to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402

flask_app = app_module.app
flask_app.config["TESTING"] = True
client = flask_app.test_client()


# ---- Fixture: a fake LLM response ----
SAMPLE_EXAM_JSON = {
    "questions": [
        {
            "type": "mcq",
            "difficulty": 1,
            "text": "ما هو ناتج 2 + 2 في الحساب الأساسي؟",
            "points": 1.5,
            "competence": "العمليات الأساسية",
            "options": ["3", "4", "5", "6"],
            "answer": "4",
        },
        {
            "type": "truefalse",
            "difficulty": 1,
            "text": "العدد 7 هو عدد أولي ولا يقبل القسمة على غير نفسه و1.",
            "points": 1.0,
            "competence": "الأعداد الأولية",
            "answer": True,
        },
        {
            "type": "essay",
            "difficulty": 2,
            "text": "اشرح بإيجاز مفهوم نظرية فيثاغورس وأهميتها في الهندسة.",
            "points": 3.0,
            "competence": "الهندسة الإقليدية",
        },
    ],
    "model_answers": [
        {
            "question_index": 0,
            "question_text": "ما هو ناتج 2 + 2؟",
            "correct_answer": "4",
            "detailed_solution": "نجمع 2 + 2 = 4.",
            "justification": "حقيقة حسابية أساسية.",
            "competence": "العمليات الأساسية",
            "common_mistakes": ["الخلط مع 2 × 2", "الجمع الخاطئ"],
            "points_breakdown": {"الفهم": 0.5, "التطبيق": 1.0},
        },
        {
            "question_index": 1,
            "question_text": "العدد 7 أولي.",
            "correct_answer": True,
            "detailed_solution": "7 لا يقبل القسمة إلا على 1 و7.",
            "justification": "تعريف العدد الأولي.",
            "competence": "الأعداد الأولية",
            "common_mistakes": [],
        },
        {
            "question_index": 2,
            "question_text": "نظرية فيثاغورس.",
            "correct_answer": "في المثلث القائم a² + b² = c²",
            "detailed_solution": "النظرية تربط أضلاع المثلث القائم.",
            "competence": "الهندسة",
            "common_mistakes": ["نسيان أن المثلث يجب أن يكون قائماً"],
        },
    ],
    "metadata": {
        "subject": "رياضيات",
        "grade": "السنة الأولى متوسط",
        "topic": "الحساب",
        "difficulty": "متوسط",
        "generated_for": "المنهاج الجزائري",
        "notes": "اختبار تجريبي",
    },
}


def make_fake_groq_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
            )
        ]
    )


# ============================================================
# Tests
# ============================================================
PASS, FAIL = 0, 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        failures.append(f"{name}: {detail}")
        print(f"  ✗ {name} — {detail}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# --- /health ---
section("health endpoint")
r = client.get("/health")
check("status 200", r.status_code == 200, f"got {r.status_code}")
check("returns healthy", r.is_json and r.get_json().get("status") == "healthy")


# --- /generate_full_exam: missing fields ---
section("/generate_full_exam validation")
r = client.post("/generate_full_exam", json={})
check("400 when fields missing", r.status_code == 400, f"got {r.status_code}: {r.data[:200]}")

r = client.post("/generate_full_exam", json={"subject": "x", "grade": "y", "topic": "z", "num_questions": "abc"})
check("400 when num_questions not int", r.status_code == 400)


# --- /generate_full_exam: success path with mocked Groq ---
section("/generate_full_exam happy path")
fake_resp = make_fake_groq_response(SAMPLE_EXAM_JSON)
exam_id: int | None = None
with patch.object(app_module.groq_client.chat.completions, "create", return_value=fake_resp):
    r = client.post(
        "/generate_full_exam",
        json={
            "subject": "رياضيات",
            "grade": "السنة الأولى متوسط",
            "semester": "الفصل الأول",
            "examType": "اختبار فصلي",
            "topic": "الحساب",
            "difficulty": "متوسط",
            "num_questions": 3,
        },
    )

check("status 200", r.status_code == 200, f"got {r.status_code}: {r.data[:300]}")
if r.status_code == 200:
    body = r.get_json()
    exam_id = body.get("validation", {}).get("db_id")
    check("has 3 questions", len(body.get("questions", [])) == 3)
    check("total_points recomputed", body.get("total_points") == 5.5,
          f"got {body.get('total_points')}")
    check("links present", "view_exam" in body.get("links", {}))
    check("db_id integer", isinstance(exam_id, int))


# --- /my_exams ---
section("/my_exams")
r = client.get("/my_exams")
check("status 200", r.status_code == 200)
body = r.get_json() if r.is_json else {}
check("contains the exam we just created", body.get("total", 0) >= 1)

# Filtering
r = client.get("/my_exams?subject=رياضيات&grade=الأولى")
check("filter by subject+grade returns >=1", r.is_json and r.get_json().get("total", 0) >= 1)

r = client.get("/my_exams?limit=abc")
check("non-integer limit handled gracefully", r.status_code == 200)


# --- /exam/<id> ---
section("/exam/<id>")
if exam_id is not None:
    r = client.get(f"/exam/{exam_id}")
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.get_json()
        check("questions deserialized", isinstance(d.get("questions"), list) and len(d["questions"]) == 3)
        check("metadata present", isinstance(d.get("metadata"), dict))

r = client.get("/exam/999999")
check("non-existent returns 404", r.status_code == 404)


# --- /export/aiken/<id> ---
section("/export/aiken/<id>")
if exam_id is not None:
    r = client.get(f"/export/aiken/{exam_id}")
    check("status 200", r.status_code == 200)
    body = r.get_json() if r.is_json else {}
    content = body.get("content", "")
    check("contains ANSWER: B (correct letter for '4')",
          "ANSWER: B" in content,
          f"content was: {content[:300]}")
    check("contains A. 3 prefix", "A. 3" in content)
    check("contains true/false branch", "ANSWER: A" in content or "ANSWER: B" in content)


# --- /export/gift/<id> ---
section("/export/gift/<id>")
if exam_id is not None:
    r = client.get(f"/export/gift/{exam_id}")
    check("status 200", r.status_code == 200)
    body = r.get_json() if r.is_json else {}
    content = body.get("content", "")
    check("contains =4 (correct option marker)", "=4" in content)
    check("contains ~3 (distractor marker)", "~3" in content)
    check("contains TRUE/FALSE block for truefalse", "TRUE" in content or "FALSE" in content)

    # Verify GIFT escaping for special chars
    escaped = app_module._gift_escape("a~b=c{d}e:f#g")
    check("GIFT escaping works for ~ = { } : #",
          all(seq in escaped for seq in [r"\~", r"\=", r"\{", r"\}", r"\:", r"\#"]),
          f"got: {escaped!r}")


# --- /export/pdf/<id> --- (student version)
section("/export/pdf/<id> student")
if exam_id is not None:
    r = client.get(f"/export/pdf/{exam_id}")
    check("status 200", r.status_code == 200, f"got {r.status_code}: {r.data[:300]}")
    check("content-type pdf", r.mimetype == "application/pdf")
    check("PDF magic header", r.data[:4] == b"%PDF")
    check("non-trivial size", len(r.data) > 2000, f"size={len(r.data)}")

# --- /export/pdf/<id>?teacher=true ---
section("/export/pdf/<id> teacher")
if exam_id is not None:
    r_student = client.get(f"/export/pdf/{exam_id}")
    r_teacher = client.get(f"/export/pdf/{exam_id}?teacher=true")
    check("teacher 200", r_teacher.status_code == 200)
    check("teacher PDF larger than student", len(r_teacher.data) > len(r_student.data),
          f"teacher={len(r_teacher.data)} student={len(r_student.data)}")


# --- pydantic discriminator: bad type ---
section("pydantic edge cases")
bad = dict(SAMPLE_EXAM_JSON)
bad = json.loads(json.dumps(bad))  # deep copy
bad["questions"][0]["type"] = "INVALID_TYPE"
fake_resp = make_fake_groq_response(bad)
with patch.object(app_module.groq_client.chat.completions, "create", return_value=fake_resp):
    r = client.post(
        "/generate_full_exam",
        json={"subject": "x", "grade": "y", "topic": "z", "num_questions": 3},
    )
check("invalid type rejected (502 from validation_error path)", r.status_code == 502,
      f"got {r.status_code}")

# --- pydantic: MCQ answer not in options ---
bad = json.loads(json.dumps(SAMPLE_EXAM_JSON))
bad["questions"][0]["answer"] = "999_NOT_AN_OPTION"
fake_resp = make_fake_groq_response(bad)
with patch.object(app_module.groq_client.chat.completions, "create", return_value=fake_resp):
    r = client.post(
        "/generate_full_exam",
        json={"subject": "x", "grade": "y", "topic": "z", "num_questions": 3},
    )
check("answer-not-in-options rejected (502)", r.status_code == 502,
      f"got {r.status_code}")
body = r.get_json() or {}
check("error response does NOT leak raw exception details",
      "details" not in body and "Traceback" not in str(body),
      f"body was: {body}")


# --- 404 + 429 handling ---
section("error handlers")
r = client.get("/exam/9999999")
check("missing exam → 404", r.status_code == 404)


# --- Summary ---
print(f"\n{'=' * 50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  - {f}")
sys.exit(0 if FAIL == 0 else 1)
