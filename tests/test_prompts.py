"""اختبارات بُناة الـ prompts و الدوال المساعدة."""

import pytest

from app import _build_system_prompt, _build_user_prompt, _compute_max_tokens


# --------------------- _compute_max_tokens ---------------------


def test_compute_max_tokens_within_bounds():
    assert _compute_max_tokens(1) >= 2000  # MIN
    assert _compute_max_tokens(1000) <= 8000  # MAX


def test_compute_max_tokens_increases_with_questions():
    a = _compute_max_tokens(5)
    b = _compute_max_tokens(20)
    assert b > a


def test_compute_max_tokens_thirty_questions_uses_max():
    # 30 سؤالاً × 350 + 800 = 11300 → سيُقصّ إلى 8000
    assert _compute_max_tokens(30) == 8000


# --------------------- _build_system_prompt ---------------------


@pytest.mark.parametrize("stage,expected_total", [
    ("primary", "10 نقاط"),
    ("middle", "20 نقطة"),
    ("secondary", "20 نقطة"),
])
def test_system_prompt_mentions_stage_total(stage, expected_total):
    p = _build_system_prompt(stage, "اختبار فصلي")
    assert expected_total in p


def test_system_prompt_bac_mentions_subjects():
    p = _build_system_prompt("secondary", "بكالوريا تجريبية")
    # في البكالوريا التجريبية نطلب موضوع كامل من 20 نقطة
    assert "بنية البكالوريا" in p


def test_system_prompt_uses_official_terminology():
    p = _build_system_prompt("middle", "اختبار فصلي")
    assert "الكفاءة الختامية" in p
    assert "الوضعية الإدماجية" in p


def test_system_prompt_lists_allowed_question_types():
    p = _build_system_prompt(None, "اختبار فصلي")
    for t in ("mcq", "truefalse", "essay", "application", "problem"):
        assert t in p


# --------------------- _build_user_prompt ---------------------


def test_user_prompt_includes_all_fields():
    p = _build_user_prompt(
        subject="رياضيات",
        grade="السنة 3 علوم",
        semester="الفصل الثاني",
        branch="علوم تجريبية",
        exam_type="اختبار فصلي",
        topic="الدوال اللوغاريتمية",
        difficulty="متوسط",
        num_questions=6,
        structure={"parts": [{"name": "الجزء الأول: التمارين", "points": 13}]},
        exam_total=20.0,
        coefficient=5,
    )
    for tok in (
        "رياضيات", "السنة 3 علوم", "الفصل الثاني", "علوم تجريبية",
        "اختبار فصلي", "الدوال اللوغاريتمية", "متوسط",
        "20", "المعامل", "الجزء الأول",
    ):
        assert tok in p, f"missing {tok!r}"


def test_user_prompt_no_structure_no_section_hint():
    p = _build_user_prompt(
        subject="رياضيات",
        grade="السنة الأولى ابتدائي",
        semester="الفصل الأول",
        branch="",
        exam_type="اختبار فصلي",
        topic="الجمع",
        difficulty="سهل",
        num_questions=4,
        structure=None,
        exam_total=10.0,
        coefficient=None,
    )
    assert "بنية الاختبار المطلوبة" not in p
    assert "10" in p


def test_user_prompt_describes_index_range():
    p = _build_user_prompt(
        subject="رياضيات",
        grade="السنة 3 علوم",
        semester="الفصل الأول",
        branch="",
        exam_type="اختبار فصلي",
        topic="...",
        difficulty="متوسط",
        num_questions=5,
        structure=None,
        exam_total=20.0,
        coefficient=None,
    )
    # يجب ذكر المدى [0, 4]
    assert "0 إلى 4" in p
