"""اختبارات وحدة كتالوج المنهاج الجزائري."""

import pytest

from curriculum import (
    detect_stage,
    find_subject,
    get_exam_structure,
    load_curriculum,
    reset_curriculum_cache,
    validate_subject_grade,
)


@pytest.fixture(scope="module")
def catalog():
    reset_curriculum_cache()
    return load_curriculum()


def test_catalog_has_three_stages(catalog):
    stages = catalog["stages"]
    assert set(stages) == {"primary", "middle", "secondary"}


def test_catalog_has_mandatory_subjects(catalog):
    names = {s["name"] for s in catalog["subjects"]}
    assert "رياضيات" in names
    assert "اللغة العربية" in names
    assert "الفلسفة" in names


# ----------------------- detect_stage -----------------------


def test_detect_stage_primary(catalog):
    assert detect_stage(catalog, "السنة الأولى ابتدائي") == "primary"


def test_detect_stage_middle(catalog):
    assert detect_stage(catalog, "السنة الرابعة متوسط") == "middle"


def test_detect_stage_secondary(catalog):
    assert detect_stage(catalog, "السنة 3 علوم") == "secondary"


def test_detect_stage_with_normalization(catalog):
    # الألف الهمزة المختلفة يجب ألا تمنع الكشف
    assert detect_stage(catalog, "السنه الأولى متوسط") == "middle"


def test_detect_stage_unknown(catalog):
    # السنة الجامعية ليست ضمن المنظومة المدرسية
    assert detect_stage(catalog, "السنة الأولى جامعي") is None


# ----------------------- find_subject -----------------------


def test_find_subject_canonical(catalog):
    assert find_subject(catalog, "رياضيات")["name"] == "رياضيات"


def test_find_subject_via_alias(catalog):
    # "الرياضيات" alias لـ "رياضيات"
    assert find_subject(catalog, "الرياضيات")["name"] == "رياضيات"


def test_find_subject_case_insensitive_normalization(catalog):
    # "اللغه العربيه" بدل "اللغة العربية"
    assert find_subject(catalog, "اللغه العربيه")["name"] == "اللغة العربية"


def test_find_subject_unknown(catalog):
    assert find_subject(catalog, "ميكانيك الكوانتا") is None


# ------------------- validate_subject_grade -------------------


def test_validate_exact_match(catalog):
    m = validate_subject_grade(catalog, "الرياضيات", "السنة 3 علوم")
    assert m.is_exact is True
    assert m.stage == "secondary"
    assert m.exam_total == 20.0
    assert m.coefficient == 5
    assert m.subject_canonical == "رياضيات"
    assert m.warnings == []


def test_validate_primary_uses_10_total(catalog):
    m = validate_subject_grade(catalog, "رياضيات", "السنة الأولى ابتدائي")
    assert m.stage == "primary"
    assert m.exam_total == 10.0


def test_validate_subject_not_offered_in_grade(catalog):
    # الفلسفة غير متاحة في الابتدائي
    m = validate_subject_grade(catalog, "الفلسفة", "السنة الأولى ابتدائي")
    assert m.is_exact is False
    assert any("ليست مُسجَّلة" in w for w in m.warnings)


def test_validate_unknown_subject(catalog):
    m = validate_subject_grade(catalog, "السباحة", "السنة 3 علوم")
    assert any("غير معروفة" in w for w in m.warnings)


def test_validate_unknown_grade(catalog):
    m = validate_subject_grade(catalog, "رياضيات", "السنة الخامسة جامعي")
    assert m.stage is None or any("لم يتم تصنيفها" in w for w in m.warnings)


# -------------------- get_exam_structure --------------------


def test_get_structure_secondary_default(catalog):
    s = get_exam_structure(catalog, "secondary", "اختبار فصلي")
    assert s is not None
    parts = s["parts"]
    assert any("الجزء الأول" in p["name"] for p in parts)
    assert any("الوضعية الإدماجية" in p["name"] for p in parts)


def test_get_structure_secondary_bac(catalog):
    s = get_exam_structure(catalog, "secondary", "بكالوريا تجريبية")
    assert s is not None
    assert any("موضوع" in p["name"] for p in s["parts"])


def test_get_structure_unknown_stage_returns_none(catalog):
    assert get_exam_structure(catalog, None, "اختبار فصلي") is None
