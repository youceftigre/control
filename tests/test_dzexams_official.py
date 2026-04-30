"""
اختبارات لنمط "dzexams الرسمي" (ترويسة جدولية + خانات الاسم + صندوق الحاسبة + ترقيم الصفحات).
"""

from __future__ import annotations

import json
import os

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
CURRICULUM_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "algeria_curriculum.json"
)


def _template_source() -> str:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _curriculum() -> dict:
    with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────── Registration ───────────────


def test_style_registered_in_curriculum() -> None:
    styles = _curriculum()["exam_styles"]
    assert "dzexams_official" in styles
    meta = styles["dzexams_official"]
    assert "name_ar" in meta and meta["name_ar"]
    assert meta.get("template_html")


def test_style_offered_in_frontend_dropdown() -> None:
    src = _template_source()
    assert 'value="dzexams_official"' in src


# ─────────────── CSS presence ───────────────


def test_official_css_classes_defined() -> None:
    src = _template_source()
    for cls in (
        ".a4-exam.dz-official",
        ".dz-official-header",
        ".dz-name-row",
        ".dz-calc-warning",
        ".dz-exam-title-box",
        ".dz-part-label",
        ".dz-official-footer",
    ):
        assert cls in src, f"CSS class {cls} missing"


def test_official_page_counter_in_print() -> None:
    """ترقيم الصفحات عبر CSS counter في @media print."""
    src = _template_source()
    print_section = src[src.index("@media print"):]
    assert "counter(page)" in print_section
    assert "counter(pages)" in print_section


# ─────────────── JS emission ───────────────


def test_build_switches_on_is_official() -> None:
    src = _template_source()
    assert "_isOfficial" in src
    assert "dzexams_official" in src


def test_official_header_table_emitted() -> None:
    src = _template_source()
    assert '<table class="dz-official-header">' in src
    assert '<table class="dz-name-row">' in src
    assert "الاسم:" in src
    assert "اللقب:" in src
    assert "القسم:" in src


def test_official_calculator_warning_guarded_by_subject() -> None:
    """صندوق «يمنع استعمال الآلة الحاسبة» يجب أن يكون مشروطاً بمواد حسابية."""
    src = _template_source()
    assert "يمنع استعمال الآلة الحاسبة" in src
    # الشرط يتفحّص subject
    assert "needsCalcWarning" in src
    assert "رياضيات" in src


def test_official_part_labels_present() -> None:
    src = _template_source()
    assert "الجزء الأول" in src
    assert "الجزء الثاني" in src
    assert "dz-part-label" in src


def test_official_footer_brand_emitted() -> None:
    src = _template_source()
    assert "www.dzexams.com" in src
    assert "dz-brand" in src
