"""اختبارات تهريب GIFT — تأكّد من معالجة الـ backslash بشكل صحيح."""

from app import _gift_escape


def test_gift_escapes_special_chars():
    assert _gift_escape("a~b=c#d{e}f:g") == r"a\~b\=c\#d\{e\}f\:g"


def test_gift_escapes_backslash_correctly():
    """الـ backslash المفرد يجب أن يصبح زوج backslash (\\)، لا أربع."""
    # قبل التصحيح: كان ينتج r"\\\\" (4 backslashes) ويرفضه Moodle.
    assert _gift_escape("\\") == "\\\\"


def test_gift_no_special_chars_unchanged():
    text = "سؤال عربي بسيط بدون حروف خاصّة"
    assert _gift_escape(text) == text


def test_gift_handles_non_string_input():
    assert _gift_escape(42) == "42"
    assert _gift_escape(None) == "None"


def test_gift_combined_special_with_backslash():
    # تأكّد أنّ ترتيب الاستبدال لا يضاعف الفوارق العكسية
    assert _gift_escape("a\\b{c}") == r"a\\b\{c\}"
