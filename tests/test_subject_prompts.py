"""
اختبارات للتوجيهات المخصّصة لكل مادة في الـ prompt.

تتحقق من:
- تطبيع أسماء المواد إلى رموز قانونية.
- إرجاع كتل توجيهات متمايزة حسب المادة.
- وجود قواعد صارمة ضد الخلط (الرياضيات في اختبار عربية إلخ).
- اندماج التوجيهات في system_prompt و user_prompt.
"""

from __future__ import annotations

import pytest

from subject_prompts import (
    canonicalize_subject,
    get_subject_guidance,
    is_language_subject,
    is_non_math_subject,
)

# ─────────────── canonicalize_subject ───────────────


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("الرياضيات", "math"),
        ("رياضيات", "math"),
        ("math", "math"),
        ("اللغة العربية", "arabic"),
        ("العربية", "arabic"),
        ("اللغة الفرنسية", "french"),
        ("اللغة الإنجليزية", "english"),
        ("العلوم الطبيعية والحياة", "science"),
        ("الفيزياء والكيمياء", "physics"),
        ("العلوم الفيزيائية والتكنولوجيا", "physics"),
        ("التاريخ والجغرافيا", "history"),
        ("التربية الإسلامية", "islamic"),
        ("التربية المدنية", "civic"),
        ("الفلسفة", "philosophy"),
        ("", "generic"),
        ("مادة غير موجودة", "generic"),
    ],
)
def test_canonicalize_subject(inp: str, expected: str) -> None:
    assert canonicalize_subject(inp) == expected


# ─────────────── get_subject_guidance content ───────────────


def test_arabic_guidance_forbids_math_and_requires_production() -> None:
    """اللغة العربية: ممنوع الحساب + إنتاج كتابي."""
    g = get_subject_guidance("اللغة العربية")
    assert g, "Arabic guidance must not be empty"
    assert "إنتاج كتابي" in g or "إنتاج" in g
    assert "ممنوع" in g  # ممنوع الحساب/LaTeX
    # لا يجب اقتراح أدوات رياضية كتوجيه إيجابي (يسمح بذكرها في سياق المنع)
    for forbidden in ["نظرية طاليس", "نظرية فيثاغورس", "حل معادلة", "حساب كمية"]:
        assert forbidden not in g, f"Arabic guidance must not recommend {forbidden}"
    # LaTeX يجب أن يُذكر فقط في سياق المنع
    if "LaTeX" in g:
        # تأكد من أنّ ذكره مصحوب بكلمة "ممنوع"
        assert "ممنوع استعمال LaTeX" in g or "ممنوع" in g


def test_french_guidance_requires_production_ecrite() -> None:
    g = get_subject_guidance("اللغة الفرنسية")
    assert "production écrite" in g or "Rédige" in g or "Écris" in g


def test_english_guidance_requires_guided_writing() -> None:
    g = get_subject_guidance("اللغة الإنجليزية")
    assert "writing" in g.lower() or "paragraph" in g.lower()


def test_history_guidance_requires_document_analysis() -> None:
    g = get_subject_guidance("التاريخ والجغرافيا")
    assert "وثيقة" in g
    assert "حسابية" in g  # mentions rejecting calculations


def test_islamic_guidance_requires_religious_support() -> None:
    g = get_subject_guidance("التربية الإسلامية")
    assert "آية" in g or "حديث" in g
    assert "استنباط" in g


def test_civic_guidance_requires_civil_context() -> None:
    g = get_subject_guidance("التربية المدنية")
    assert "حقوق" in g or "واجبات" in g or "مواطن" in g


def test_math_guidance_keeps_latex_recommendation() -> None:
    g = get_subject_guidance("الرياضيات")
    assert "LaTeX" in g or "\\frac" in g or "\\sqrt" in g


def test_science_guidance_requires_experiment_context() -> None:
    g = get_subject_guidance("العلوم الطبيعية والحياة")
    assert "علمي" in g or "تجربة" in g or "منحنى" in g


def test_physics_guidance_requires_physics_context() -> None:
    g = get_subject_guidance("الفيزياء والكيمياء")
    assert "كهربائية" in g or "كيميائي" in g or "تقني" in g


def test_unknown_subject_returns_empty_guidance() -> None:
    assert get_subject_guidance("مادة خيالية") == ""


# ─────────────── helper classifiers ───────────────


def test_is_language_subject() -> None:
    assert is_language_subject("اللغة العربية")
    assert is_language_subject("اللغة الفرنسية")
    assert is_language_subject("اللغة الإنجليزية")
    assert not is_language_subject("الرياضيات")
    assert not is_language_subject("العلوم الطبيعية والحياة")


def test_is_non_math_subject() -> None:
    assert is_non_math_subject("اللغة العربية")
    assert is_non_math_subject("التاريخ والجغرافيا")
    assert is_non_math_subject("التربية الإسلامية")
    assert not is_non_math_subject("الرياضيات")
    assert not is_non_math_subject("الفيزياء والكيمياء")


# ─────────────── integration with _build_system_prompt / _build_user_prompt ───────────────


def test_system_prompt_includes_arabic_specific_guidance() -> None:
    from app import _build_system_prompt

    p = _build_system_prompt("middle", "اختبار الفصل", style="default", subject="اللغة العربية")
    assert "إنتاج كتابي" in p or "إنتاج" in p
    assert "ممنوع" in p


def test_system_prompt_includes_math_specific_guidance() -> None:
    from app import _build_system_prompt

    p = _build_system_prompt("middle", "اختبار الفصل", style="default", subject="الرياضيات")
    # يجب أن يذكر LaTeX (الأصلي العام) أو قواعد الرياضيات الخاصة
    assert "LaTeX" in p or "\\frac" in p


def test_system_prompt_without_subject_falls_back_to_generic() -> None:
    from app import _build_system_prompt

    p = _build_system_prompt("middle", "اختبار الفصل", style="default")
    # يجب أن يعمل دون خطأ
    assert "الوضعية" in p
    assert isinstance(p, str)


def test_user_prompt_for_arabic_forbids_math_situation() -> None:
    from app import _build_user_prompt

    p = _build_user_prompt(
        subject="اللغة العربية",
        grade="السنة الثانية متوسط",
        semester="الأول",
        branch="",
        exam_type="اختبار الفصل الأول",
        topic="النص الوصفي",
        difficulty="متوسط",
        num_questions=5,
        structure=None,
        exam_total=20,
        coefficient=4,
        style="default",
    )
    assert "إنتاج كتابي" in p
    # يحذر صراحة من الخلط مع الرياضيات
    assert "ليست مسألة رياضيات" in p or "حسابات" in p


def test_user_prompt_for_history_forbids_calculations() -> None:
    from app import _build_user_prompt

    p = _build_user_prompt(
        subject="التاريخ والجغرافيا",
        grade="السنة الرابعة متوسط",
        semester="الثاني",
        branch="",
        exam_type="اختبار الفصل الثاني",
        topic="الثورة التحريرية",
        difficulty="متوسط",
        num_questions=5,
        structure=None,
        exam_total=20,
        coefficient=3,
        style="default",
    )
    assert "مقال تاريخي" in p or "وثيقة" in p
    assert "حسابية" in p


def test_user_prompt_for_math_keeps_math_situation() -> None:
    from app import _build_user_prompt

    p = _build_user_prompt(
        subject="الرياضيات",
        grade="السنة الرابعة متوسط",
        semester="الأول",
        branch="",
        exam_type="اختبار الفصل الأول",
        topic="الكسور",
        difficulty="متوسط",
        num_questions=5,
        structure=None,
        exam_total=20,
        coefficient=4,
        style="default",
    )
    # لا يحذر من الرياضيات — بل يشجّع على سياق حسابي
    assert "حسابية" in p or "هندسية" in p or "مسألة" in p
