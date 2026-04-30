"""
اختبارات للواجهة التفاعلية: تبويبات الاختبار/التصحيح + زر عرض الحلّ inline.

نتحقّق من وجود العناصر في templates/index.html (CSS + JS) دون تشغيل متصفح.
"""

from __future__ import annotations

import os

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")


def _template_source() -> str:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────── CSS checks ───────────────


def test_exam_tabs_css_defined() -> None:
    src = _template_source()
    assert ".exam-tabs" in src
    assert ".tab-btn" in src
    assert ".tab-btn.active" in src


def test_mode_classes_defined() -> None:
    """أنماط mode-exam / mode-correction / mode-both تتحكم بالرؤية."""
    src = _template_source()
    assert ".mode-exam" in src
    assert ".mode-correction" in src


def test_inline_answer_css_defined() -> None:
    src = _template_source()
    assert ".inline-answer" in src
    assert ".show-sol-btn" in src
    assert ".inline-answer.open" in src


def test_print_rules_hide_interactive_controls() -> None:
    """الطباعة يجب ألّا تُظهر الأزرار التفاعلية."""
    src = _template_source()
    # في @media print يجب إخفاء .exam-tabs و .show-sol-btn
    print_section = src[src.index("@media print"):]
    assert ".exam-tabs" in print_section
    assert ".show-sol-btn" in print_section


# ─────────────── JS functions ───────────────


def test_toggle_inline_answer_function_defined() -> None:
    src = _template_source()
    assert "function toggleInlineAnswer(" in src
    # يجب أن يُعيد MathJax layout عند الفتح
    assert "typesetMath(card)" in src


def test_switch_exam_tab_function_defined() -> None:
    src = _template_source()
    assert "function switchExamTab(" in src
    assert "mode-exam" in src
    assert "mode-correction" in src
    assert "mode-both" in src


def test_render_inline_answer_body_function_defined() -> None:
    src = _template_source()
    assert "function renderInlineAnswerBody(" in src
    # يحوي الأقسام الأساسية
    assert "الكفاءة" in src
    assert "الإجابة" in src
    assert "الحل المفصل" in src
    assert "سُلَم التنقيط" in src
    assert "أخطاء شائعة" in src


def test_escape_html_helper_defined() -> None:
    """helper escapeHtml يجب أن يكون موجوداً لتفادي XSS في الإجابات."""
    src = _template_source()
    assert "function escapeHtml(" in src


# ─────────────── build integration ───────────────


def test_buildExamHTML_emits_tabs_when_answers_exist() -> None:
    src = _template_source()
    # يفحص لوجود الشرط hasAnswers ورسم التبويبات
    assert "hasAnswers" in src
    assert '<div class="exam-tabs"' in src
    assert "📝 الاختبار" in src
    assert "التصحيح النموذجي" in src
    assert "📖 عرض الكل" in src


def test_buildExamHTML_emits_inline_button_per_question() -> None:
    src = _template_source()
    # زر show-sol-btn مرتبط بفهرس السؤال
    assert "show-sol-btn" in src
    assert "toggleInlineAnswer(" in src
    assert 'id="inlineAns_' in src


def test_default_mode_is_exam_on_initial_render() -> None:
    """بعد التوليد الأوّل يجب أن يكون الوضع الافتراضي = exam (إخفاء صفحة التصحيح)."""
    src = _template_source()
    assert "switchExamTab('exam')" in src


def test_answers_by_idx_mapping_built() -> None:
    """نبني خريطة question_index → answer لربط الزر بالبطاقة."""
    src = _template_source()
    assert "answersByIdx" in src
    assert "lastModelAnswers" in src
