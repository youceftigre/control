"""اختبارات قالب dzexams (HTML + توزيع نقاط الوضعيّات)."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app import (
    _build_exam_html_dzexams,
    _dzexams_quote,
    _group_questions_into_situations,
)


def _make_exam(**overrides):
    """صنع كائن GeneratedExam-ish خفيف لاختبار الرندر."""
    defaults = {
        "id": 1,
        "subject": "رياضيات",
        "grade": "السنة الرابعة متوسط",
        "semester": "الفصل الثاني",
        "topic": "الدوال — درس مراجعة",
        "exam_type": "اختبار فصلي",
        "generated_at": datetime(2025, 11, 15, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ----------------------- _group_questions_into_situations -----------------------


def test_group_questions_balances_targets():
    questions = [
        {"points": 2}, {"points": 2}, {"points": 3},
        {"points": 1}, {"points": 4}, {"points": 1},
    ]
    parts = [
        {"name": "الوضعية الأولى", "points": 7},
        {"name": "الوضعية الثانية", "points": 6},
    ]
    groups = _group_questions_into_situations(questions, parts)
    assert len(groups) == 2
    sum_g0 = sum(questions[i]["points"] for i in groups[0])
    sum_g1 = sum(questions[i]["points"] for i in groups[1])
    # المجموع الكلي محفوظ
    assert sum_g0 + sum_g1 == 13
    # كل سؤال موجود مرّة واحدة فقط
    flat = [i for g in groups for i in g]
    assert sorted(flat) == list(range(len(questions)))


def test_group_no_parts_returns_single_group():
    qs = [{"points": 1} for _ in range(3)]
    assert _group_questions_into_situations(qs, []) == [[0, 1, 2]]


def test_group_empty_questions_returns_empty_groups():
    parts = [{"name": "س1", "points": 7}, {"name": "س2", "points": 6}]
    groups = _group_questions_into_situations([], parts)
    assert groups == [[], []]


# ----------------------- _dzexams_quote -----------------------


def test_dzexams_quote_rotates_with_seed():
    q0 = _dzexams_quote(0)
    q1 = _dzexams_quote(1)
    assert q0 and q1
    # على الأقلّ بعض البذور تنتج عبارات مختلفة
    seen = {_dzexams_quote(s) for s in range(8)}
    assert len(seen) > 1


# ----------------------- _build_exam_html_dzexams -----------------------


def test_dzexams_html_contains_three_column_header():
    exam = _make_exam()
    questions = [
        {"type": "essay", "text": "اشرح المفهوم", "points": 4, "difficulty": 1},
        {"type": "application", "text": "احسب", "points": 3, "difficulty": 2},
        {"type": "problem", "text": "حلّ المسألة", "points": 6, "difficulty": 3},
    ]
    parts = [
        {"name": "الوضعية الأولى", "points": 4},
        {"name": "الوضعية الثانية", "points": 3},
        {"name": "الوضعية الثالثة", "points": 6},
    ]
    out = _build_exam_html_dzexams(
        exam, questions, None, parts=parts, duration_minutes=120,
    )
    # رأس بثلاث خانات
    assert 'class="dz-header"' in out
    assert "وزارة التربية الوطنية" in out
    assert "المستوى" in out
    assert "السنة الرابعة متوسط" in out
    assert "ساعات" in out or "ساعة" in out  # 2 ساعات
    # وضعيّات الـ 3
    assert "الوضعية الأولى" in out
    assert "الوضعية الثانية" in out
    assert "الوضعية الثالثة" in out
    # تذييل
    assert "بالتوفيق للجميع" in out


def test_dzexams_html_renders_mcq_options():
    exam = _make_exam()
    questions = [
        {
            "type": "mcq",
            "text": "ما هو ناتج 2+2؟",
            "options": ["3", "4", "5"],
            "answer": "4",
            "points": 2,
            "difficulty": 1,
        },
    ]
    parts = [{"name": "الوضعية الأولى", "points": 2}]
    out = _build_exam_html_dzexams(exam, questions, None, parts=parts)
    assert "dz-options" in out
    assert ">3<" in out and ">4<" in out and ">5<" in out


def test_dzexams_html_includes_correction_when_provided():
    exam = _make_exam()
    questions = [
        {"type": "essay", "text": "اشرح", "points": 4, "difficulty": 1},
    ]
    answers = [
        {
            "question_index": 0,
            "question_text": "اشرح",
            "correct_answer": "الإجابة هي…",
            "detailed_solution": "خطوة 1\nخطوة 2",
        },
    ]
    parts = [{"name": "الوضعية الأولى", "points": 4}]
    out = _build_exam_html_dzexams(exam, questions, answers, parts=parts)
    assert "التصحيح النموذجي" in out
    assert "الإجابة هي" in out


def test_dzexams_html_handles_no_parts():
    exam = _make_exam()
    questions = [
        {"type": "essay", "text": "اشرح", "points": 5, "difficulty": 1},
    ]
    out = _build_exam_html_dzexams(exam, questions, None, parts=None)
    # حتى بدون توزيع، يبقى الرأس والتذييل
    assert "dz-header" in out
    assert "بالتوفيق للجميع" in out


def test_dzexams_html_school_year_inferred():
    exam = _make_exam(generated_at=datetime(2026, 1, 10, tzinfo=timezone.utc))
    questions = [{"type": "essay", "text": "x", "points": 1, "difficulty": 1}]
    parts = [{"name": "س1", "points": 1}]
    out = _build_exam_html_dzexams(exam, questions, None, parts=parts)
    # يناير 2026 → سنة دراسية 2025-2026
    assert "2025-2026" in out


def test_dzexams_html_custom_institution():
    exam = _make_exam()
    questions = [{"type": "essay", "text": "x", "points": 1, "difficulty": 1}]
    parts = [{"name": "س1", "points": 1}]
    out = _build_exam_html_dzexams(
        exam, questions, None, parts=parts,
        institution_name="ثانوية ابن خلدون",
    )
    assert "ثانوية ابن خلدون" in out
    assert "وزارة التربية الوطنية" not in out
