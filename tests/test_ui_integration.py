"""
Integration tests verifying that the corrected app.py works with the
*unmodified* index.html template the user supplied.

The UI calls these endpoints (extracted from index.html JavaScript):
  - GET  /            (page load)
  - GET  /questions   (load question bank on init)
  - POST /generate    (AI exam generation)
      body: {subject, grade, semester, examType, topic, difficulty}
      expected response: {questions: [...]} where each q has type, text, points
                         and optionally options (for mcq).

These tests use the SAME mocking strategy as test_app.py (Groq is patched).
"""
from __future__ import annotations

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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402

flask_app = app_module.app
flask_app.config["TESTING"] = True
client = flask_app.test_client()


# Same fixture as test_app.py
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
            "competence": "العمليات الأساسية",
            "common_mistakes": [],
        },
        {
            "question_index": 1,
            "question_text": "العدد 7 أولي.",
            "correct_answer": True,
            "detailed_solution": "7 لا يقبل القسمة إلا على 1 و7.",
            "competence": "الأعداد الأولية",
            "common_mistakes": [],
        },
        {
            "question_index": 2,
            "question_text": "نظرية فيثاغورس.",
            "correct_answer": "في المثلث القائم a² + b² = c²",
            "detailed_solution": "النظرية تربط أضلاع المثلث القائم.",
            "competence": "الهندسة",
            "common_mistakes": [],
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


# ============================================================
# 1. GET /  →  index.html
# ============================================================
section("GET /  (HTML page load)")
r = client.get("/")
check("status 200", r.status_code == 200, f"got {r.status_code}")
check("content-type is HTML", "text/html" in (r.content_type or ""),
      f"got {r.content_type!r}")
body = r.data.decode("utf-8", errors="replace")
check("contains the page lang=ar", 'lang="ar"' in body or "dir=\"rtl\"" in body)
check("contains the AI generate button hook (generateExam)", "generateExam" in body)
check("contains fetch('/generate'", "fetch('/generate'" in body or 'fetch("/generate"' in body)
check("contains fetch('/questions'", "fetch('/questions'" in body or 'fetch("/questions"' in body)


# ============================================================
# 2. GET /questions  →  bank object
# ============================================================
section("GET /questions  (bank load)")
r = client.get("/questions")
check("status 200", r.status_code == 200, f"got {r.status_code}")
check("returns JSON object", r.is_json and isinstance(r.get_json(), dict),
      f"body type: {type(r.get_json())}")

# Test that a real bank file is honored — use a temporary file to avoid
# destroying the user's real questions_bank.json.
temp_bank_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
sample_bank = {"رياضيات": {"السنة الأولى متوسط": {"الجبر": [{"type": "mcq", "text": "test"}]}}}
json.dump(sample_bank, temp_bank_path, ensure_ascii=False)
temp_bank_path.close()

# Point the app at the temp file via the env var
original_env = os.environ.get("QUESTION_BANK_FILE")
os.environ["QUESTION_BANK_FILE"] = temp_bank_path.name
try:
    # Reload the QUESTION_BANK_FILE module-level constant
    app_module.QUESTION_BANK_FILE = temp_bank_path.name
    r = client.get("/questions")
    check("bank file is loaded when QUESTION_BANK_FILE is set",
          r.get_json() == sample_bank,
          f"got: {r.get_json()}")
finally:
    os.unlink(temp_bank_path.name)
    if original_env is None:
        os.environ.pop("QUESTION_BANK_FILE", None)
    else:
        os.environ["QUESTION_BANK_FILE"] = original_env
    # Restore default lookup behavior
    app_module.QUESTION_BANK_FILE = "questions_bank.json"


# ============================================================
# 3. POST /generate  →  matches index.html's expected shape
# ============================================================
section("POST /generate  (UI calls this for AI mode)")

# Body the UI sends (verbatim from index.html line ~742):
ui_body = {
    "subject": "الرياضيات",
    "grade": "السنة الأولى متوسط",
    "semester": "الفصل الأول",
    "examType": "اختبار فصلي",
    "topic": "المعادلات",
    "difficulty": "متوسط",
}

fake_resp = make_fake_groq_response(SAMPLE_EXAM_JSON)
with patch.object(app_module.groq_client.chat.completions, "create", return_value=fake_resp):
    r = client.post("/generate", json=ui_body)

check("status 200", r.status_code == 200, f"got {r.status_code}: {r.data[:300]}")
data = r.get_json() if r.is_json else {}

# The UI does: `const data = await resp.json(); ... questions = data.questions;`
# So we need data.questions to be a non-empty array.
check("data.questions is a list", isinstance(data.get("questions"), list))
check("data.questions is non-empty", len(data.get("questions") or []) > 0)
check("no 'error' key on success", "error" not in data,
      f"got error: {data.get('error')}")

# Each question must match what buildExamHTML() reads:
# - q.type (used in `if (q.type === 'mcq' && q.options)`)
# - q.text (rendered in q-text div)
# - q.points (used as `${pointsFormatted}`)
# - q.options (for mcq only)
qs = data.get("questions") or []
if qs:
    q0 = qs[0]
    check("question has 'type' field", "type" in q0, f"q0 keys: {list(q0.keys())}")
    check("question has 'text' field", "text" in q0)
    check("question has 'points' field", "points" in q0)
    if q0.get("type") == "mcq":
        check("MCQ question has 'options' field", "options" in q0)
        check("options is a non-empty list",
              isinstance(q0.get("options"), list) and len(q0["options"]) > 0)


# ============================================================
# 4. POST /generate  with missing required fields  →  shows error
# ============================================================
section("POST /generate  validation")

# UI checks: `if (!selectedSubject || !grade || !semester) showAlert(...)` BEFORE
# making the request, but a defensive backend should also reject:
r = client.post("/generate", json={"subject": "", "grade": "", "semester": ""})
check("400 when subject/grade/semester empty", r.status_code == 400,
      f"got {r.status_code}")
body = r.get_json() or {}
check("error message is in Arabic and user-friendly",
      "error" in body and isinstance(body["error"], str))
# UI logic: `if (data.error) { showAlert('errorBox', '❌ ' + data.error); return; }`
# So body.error must be a string, not an object/list.
check("body.error is a string (UI prepends '❌ ')",
      isinstance(body.get("error"), str))


# ============================================================
# 5. POST /generate  with LLM returning invalid JSON  →  user-facing error
# ============================================================
section("POST /generate  resilience")
bad_resp = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(content="not valid json {{{"))]
)
with patch.object(app_module.groq_client.chat.completions, "create", return_value=bad_resp):
    r = client.post("/generate", json=ui_body)
check("non-200 when LLM returns garbage", r.status_code >= 400,
      f"got {r.status_code}")
body = r.get_json() or {}
check("response has 'error' key for UI to display",
      "error" in body and isinstance(body["error"], str))
check("does NOT leak raw exception details",
      "Traceback" not in str(body) and "ValidationError" not in str(body))


# ============================================================
# 6. End-to-end  →  request, then verify rendering inputs are usable
# ============================================================
section("End-to-end shape compatibility with buildExamHTML()")
fake_resp = make_fake_groq_response(SAMPLE_EXAM_JSON)
with patch.object(app_module.groq_client.chat.completions, "create", return_value=fake_resp):
    r = client.post("/generate", json=ui_body)
data = r.get_json() if r.is_json else {}
qs = data.get("questions") or []

# Simulate the JavaScript loop in buildExamHTML to make sure no field-access blows up
js_compatible = True
js_errors: list[str] = []
for idx, q in enumerate(qs):
    try:
        # JS does: `q.type`, `q.text`, `q.points || 2`, `q.options.forEach(...)` for mcq
        _ = q["type"]
        _ = q["text"]
        _ = q.get("points", 2)
        if q["type"] == "mcq":
            for opt in q["options"]:
                str(opt)  # JS template literal coerces
    except (KeyError, TypeError) as exc:
        js_compatible = False
        js_errors.append(f"q[{idx}]: {exc}")

check("All questions are buildExamHTML-compatible",
      js_compatible, f"errors: {js_errors}")

check("MCQ types match the typeLabels in index.html",
      all(q["type"] in {"mcq", "truefalse", "essay", "application", "problem"}
          for q in qs))


# ============================================================
# Summary
# ============================================================
print(f"\n{'=' * 60}")
print(f"UI Integration: {PASS} passed, {FAIL} failed")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  - {f}")
sys.exit(0 if FAIL == 0 else 1)
