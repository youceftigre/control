"""
وحدة كتالوج المنهاج الجزائري.

توفّر هذه الوحدة:
- تحميل ملف ``data/algeria_curriculum.json`` (مع cache بسيط).
- التحقق من توافق ``(subject, grade)`` مع الكتالوج.
- تطبيع الأسماء (بمراعاة المرادفات/aliases مثل "الرياضيات" → "رياضيات").
- استخراج المعامل (coefficient) والعلامة الإجمالية المعيارية لكلّ مرحلة.
- تحديد المرحلة (ابتدائي/متوسط/ثانوي) من اسم السنة.

الفلسفة: لا نُفشل التوليد عند عدم تطابق دقيق — نُرجع تحذيراً مع السماح
بالمتابعة، حتى يبقى التطبيق صالحاً للمستقبل وعند تحديث المناهج. الخطّ الأحمر
الوحيد هو السنوات/المواد التي ليست أصلاً ضمن نظام التعليم الجزائري.

أمثلة الاستعمال
---------------
>>> cat = load_curriculum()
>>> validate_subject_grade(cat, "الرياضيات", "السنة 3 علوم")
CurriculumMatch(subject_canonical='رياضيات', stage='secondary',
                exam_total=20, coefficient=5, is_exact=True, warnings=[])
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional


CURRICULUM_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "algeria_curriculum.json",
)


# ----------------------------- API نتائج التحقق -----------------------------


@dataclass
class CurriculumMatch:
    """نتيجة التحقق من توافق المادة/السنة مع الكتالوج."""

    subject_canonical: str
    stage: Optional[str]  # primary | middle | secondary | None
    exam_total: float
    coefficient: Optional[int]
    is_exact: bool  # هل وُجدت توليفة (subject, grade) كما هي في الكتالوج
    warnings: List[str] = field(default_factory=list)


# ------------------------------ تحميل الكتالوج ------------------------------


@lru_cache(maxsize=4)
def load_curriculum(path: Optional[str] = None) -> Dict[str, Any]:
    """
    حمّل ملف الكتالوج الجزائري من القرص.

    Args:
        path: مسار الملف. إن لم يُمرَّر يُستعمل ``CURRICULUM_DEFAULT_PATH``.

    Returns:
        قاموس JSON المحلَّل.

    Raises:
        FileNotFoundError: إن كان الملف غير موجود.
        json.JSONDecodeError: إن كان الملف غير صالح JSON.
    """
    p = path or CURRICULUM_DEFAULT_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def reset_curriculum_cache() -> None:
    """مسح ذاكرة التخزين المؤقت — يُستعمل في الاختبارات."""
    load_curriculum.cache_clear()


# --------------------------- مساعدات تطبيع الأسماء --------------------------


def _normalize(s: str) -> str:
    """تطبيع بسيط: حذف المسافات الزائدة + توحيد بعض الأحرف العربية الشائعة."""
    if not s:
        return ""
    out = s.strip()
    # توحيد الألف
    for ch in ("أ", "إ", "آ"):
        out = out.replace(ch, "ا")
    # توحيد الياء/الألف المقصورة
    out = out.replace("ى", "ي")
    # توحيد التاء المربوطة
    out = out.replace("ة", "ه")
    return " ".join(out.split())


def find_subject(catalog: Dict[str, Any], subject: str) -> Optional[Dict[str, Any]]:
    """
    ابحث عن المادة في الكتالوج باستعمال الاسم القانوني أو aliases.

    التطابق غير حساس للزيادات الإملائية الشائعة (أ/إ/ا، ة/ه، ى/ي).
    """
    target = _normalize(subject)
    if not target:
        return None
    for item in catalog.get("subjects", []):
        candidates = [item.get("name", "")] + list(item.get("aliases", []))
        if any(_normalize(c) == target for c in candidates):
            return item
    return None


def detect_stage(catalog: Dict[str, Any], grade: str) -> Optional[str]:
    """تحديد المرحلة (primary/middle/secondary) من اسم السنة."""
    target = _normalize(grade)
    if not target:
        return None
    for stage_key, stage in catalog.get("stages", {}).items():
        for g in stage.get("grades", []):
            if _normalize(g) == target:
                return stage_key
    # heuristic: استنتاج المرحلة من الكلمات المفتاحية حتى عند اختلاف الصياغة
    if "ابتدائ" in target:
        return "primary"
    if "متوسط" in target:
        return "middle"
    if "ثانو" in target or "علوم" in target or "اداب" in target or "بكالوريا" in target:
        return "secondary"
    return None


# ----------------------------- التحقق الكامل -------------------------------


def validate_subject_grade(
    catalog: Dict[str, Any],
    subject: str,
    grade: str,
) -> CurriculumMatch:
    """
    تحقّق أنّ توليفة (subject, grade) متوافقة مع المنهاج الجزائري.

    لا يرفع هذا التحقق استثناءات — يُرجع ``CurriculumMatch`` مع ``warnings``
    حتى يستطيع المستدعي اتخاذ قرار (تسجيل تحذير / رفض الطلب).
    """
    warnings: List[str] = []
    meta = catalog.get("_meta", {})
    default_total = float(meta.get("exam_total_default", 20))
    primary_total = float(meta.get("exam_total_primary", 10))

    subject_doc = find_subject(catalog, subject)
    if subject_doc is None:
        warnings.append(
            f"المادة «{subject}» غير معروفة ضمن المنهاج الجزائري المُسجَّل"
        )
        subject_canonical = subject.strip()
    else:
        subject_canonical = subject_doc["name"]

    stage = detect_stage(catalog, grade)
    if stage is None:
        warnings.append(
            f"السنة «{grade}» لم يتم تصنيفها (ابتدائي/متوسط/ثانوي)"
        )

    exam_total = primary_total if stage == "primary" else default_total

    is_exact = False
    coefficient: Optional[int] = None
    if subject_doc is not None:
        available = [_normalize(g) for g in subject_doc.get("available_grades", [])]
        is_exact = _normalize(grade) in available
        if not is_exact and stage is not None:
            warnings.append(
                f"المادة «{subject_canonical}» ليست مُسجَّلة في السنة «{grade}» — "
                "تأكّد من توافق المنهاج"
            )
        coeffs = subject_doc.get("coefficients", {})
        # نبحث بمطابقة مطبَّعة لتسامُح الاختلافات الإملائية
        for k, v in coeffs.items():
            if _normalize(k) == _normalize(grade):
                coefficient = int(v)
                break

    return CurriculumMatch(
        subject_canonical=subject_canonical,
        stage=stage,
        exam_total=exam_total,
        coefficient=coefficient,
        is_exact=is_exact,
        warnings=warnings,
    )


def get_exam_structure(
    catalog: Dict[str, Any],
    stage: Optional[str],
    exam_type: str = "اختبار فصلي",
    style: str = "default",
) -> Optional[Dict[str, Any]]:
    """
    أعِد بنية الاختبار المعيارية حسب المرحلة ونوع الاختبار والنمط.

    Args:
        catalog: كتالوج المنهاج (نتيجة ``load_curriculum``).
        stage: المرحلة (``"primary"``/``"middle"``/``"secondary"``).
        exam_type: نوع الاختبار (يستعمل عند ``style="default"`` لتحديد بكالوريا/BEM).
        style: نمط الاختبار: ``"default"``, ``"dzexams"``, ``"bem"``, ``"bac"``.

    Returns:
        بنية الاختبار (dict مع ``parts`` ومعلومات إضافية)، أو ``None`` إن لم تتوفّر.

    قواعد الاختيار:
    - ``style="bem"`` (متوسط): ``bem_template`` (3 تمارين + وضعية إدماجية).
    - ``style="bac"`` (ثانوي): ``bac_template`` (موضوعان مخيَّران).
    - ``style="dzexams"``: ``dzexams_template`` (3 وضعيّات بتوزيع متفاوت).
    - ``style="default"``: استدلال تلقائي من ``exam_type``.
    """
    if not stage:
        return None
    stage_doc = catalog.get("stages", {}).get(stage, {})
    if not stage_doc:
        return None

    if style == "bem" and stage == "middle":
        return stage_doc.get("bem_template") or stage_doc.get("structure_template")
    if style == "bac" and stage == "secondary":
        return stage_doc.get("bac_template")
    if style == "dzexams":
        return stage_doc.get("dzexams_template") or stage_doc.get("structure_template")

    # default: استدلال من exam_type
    et = exam_type or ""
    if stage == "secondary" and "بكالوريا" in et:
        return stage_doc.get("bac_template")
    if stage == "middle" and "شهادة التعليم المتوسط" in et:
        return stage_doc.get("bem_template") or stage_doc.get("structure_template")
    return stage_doc.get("structure_template")


def list_exam_styles(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """أنماط الاختبار المدعومة (default/dzexams/bem/bac…)."""
    return dict(catalog.get("exam_styles", {}))


def resolve_exam_style(
    catalog: Dict[str, Any],
    requested_style: Optional[str],
    *,
    stage: Optional[str] = None,
    exam_type: Optional[str] = None,
    grade: Optional[str] = None,
) -> str:
    """
    اختر نمط الاختبار المناسب.

    - إن طُلب نمط صريح (``requested_style``) ووُجد في الكتالوج → نُعيده.
    - وإلا نستدلّ من ``exam_type`` و ``stage``:
      * ``"بكالوريا"`` + ثانوي → ``"bac"``
      * ``"شهادة التعليم المتوسط"`` + متوسط → ``"bem"``
      * غير ذلك → ``"default"``.

    لا نُفشل إن لم يتطابق النمط المطلوب — نُسجّل تحذيراً ضمنياً ونُرجع ``"default"``.
    """
    styles = list_exam_styles(catalog)
    if requested_style:
        rs = requested_style.strip().lower()
        if rs in styles:
            return rs

    et = exam_type or ""
    if stage == "secondary" and "بكالوريا" in et:
        return "bac"
    if stage == "middle" and "شهادة التعليم المتوسط" in et:
        return "bem"
    return "default"


def distribute_points_for_situations(
    catalog: Dict[str, Any],
    stage: Optional[str],
    style: str = "dzexams",
    *,
    rotation_index: int = 0,
) -> List[Dict[str, Any]]:
    """
    أعِد توزيع النقاط لـ 3 وضعيّات بأسلوب dzexams.

    الكتالوج يُعرّف ``parts`` (التوزيع الافتراضي) و ``alternative_distributions``
    (قائمة بدائل). نستعمل ``rotation_index`` للدوران بين البدائل لإحداث التنوّع
    من اختبار لآخر (يتم تمريره مثلاً من id الاختبار أو طابع زمني).
    """
    if not stage:
        return []
    stage_doc = catalog.get("stages", {}).get(stage, {})
    template = stage_doc.get(f"{style}_template") if style else None
    if not template:
        return []

    parts = list(template.get("parts", []))
    alternatives = template.get("alternative_distributions") or []

    if alternatives and rotation_index >= 0:
        # نختار توزيعاً من alternatives بناء على rotation_index
        all_distributions: List[List[int]] = [[int(p["points"]) for p in parts]]
        for alt in alternatives:
            if isinstance(alt, list) and len(alt) == len(parts):
                all_distributions.append([int(x) for x in alt])
        chosen = all_distributions[rotation_index % len(all_distributions)]
        return [
            {"name": parts[i]["name"], "points": chosen[i]}
            for i in range(len(parts))
        ]

    return parts


def list_supported_exam_types(catalog: Dict[str, Any]) -> List[str]:
    """أنواع الاختبارات المدعومة في النظام الجزائري."""
    return list(catalog.get("exam_types", []))


def list_supported_semesters(catalog: Dict[str, Any]) -> List[str]:
    """الفصول الدراسية الجزائرية."""
    return list(catalog.get("semesters", []))
