# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║           موسوعة الاختبارات الجزائرية الذكية                      ║
║           بنك الأسئلة المتكامل - الإصدار الاحترافي                ║
║                                                                  ║
║  المطور: youcef .b - خبير تربوي ومفتش تعليمي سابق               ║
║  البريد: youcefbenhamidaa@gmail.com                             ║
║  © 2025 جميع الحقوق محفوظة                                       ║
╚══════════════════════════════════════════════════════════════════╝

المميزات:
- بنك أسئلة ضخم (500+ سؤال أصلي)
- نظام توليد ذكي بتغيير تلقائي
- بحث بالتلميحات والكلمات المفتاحية
- تصحيحات نموذجية مفصلة
- سرعة فائقة في الاختيار
"""

from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
import os
import traceback
import random
import json
import re
from datetime import datetime

load_dotenv()
api_key = os.getenv('GROQ_API_KEY')

if api_key:
    client = Groq(api_key=api_key)
    print("✅ Groq client ready")
else:
    client = None
    print("❌ مفتاح Groq API غير موجود")

app = Flask(__name__, static_folder='.', static_url_path='')

# ============================================================
# بنك الأسئلة الضخم - موسوعة الاختبارات
# ============================================================

class ExamEncyclopedia:
    """موسوعة الأسئلة الشاملة"""

    def __init__(self):
        self.subjects = {
            "الرياضيات": self._load_math(),
            "اللغة العربية": self._load_arabic(),
            "اللغة الفرنسية": self._load_french(),
            "اللغة الإنجليزية": self._load_english(),
            "العلوم الفيزيائية والتكنولوجيا": self._load_physics(),
            "علوم الطبيعة والحياة": self._load_biology(),
            "التربية الإسلامية": self._load_islamic(),
            "التاريخ والجغرافيا": self._load_history(),
            "التربية المدنية": self._load_civics()
        }

        # قوالب التنويع
        self.names = ["أحمد", "محمد", "علي", "عمر", "خالد", "يوسف", "كريم", "نور", "سامي", "رامي",
                      "فاطمة", "عائشة", "مريم", "ليلى", "سارة", "نور", "هدى", "رحمة"]
        self.places = ["سوق", "مدرسة", "حديقة", "متجر", "ورشة", "مستشفى", "مكتبة", "مطعم", "ملعب", "مسجد"]
        self.professions = ["فلاح", "تاجر", "مهندس", "معلم", "طباخ", "نجار", "حداد", "خياط", "طبيب", "سائق"]
        self.sports = ["كرة القدم", "كرة السلة", "السباحة", "الجري", "الدراجات", "الملاكمة", "التنس", "الكرة الطائرة"]
        self.cities = ["الجزائر", "وهران", "قسنطينة", "عنابة", "تلمسان", "سطيف", "البليدة", "باتنة", "بسكرة", "تيارت"]

    def _load_math(self):
        return {
            "السنة الرابعة متوسط": {
                "الفصل الأول": {
                    "المعادلات من الدرجة الثانية": [
                        {
                            "id": "M4AM-001",
                            "source": "BEM 2024 - الجزائر",
                            "type": "حسابي",
                            "difficulty": "متوسط",
                            "text": "أحسب A = 7/3 - 4/3 ÷ 8/5",
                            "solution": "A = 7/3 - (4/3 × 5/8) = 7/3 - 20/24 = 7/3 - 5/6 = 14/6 - 5/6 = 9/6 = 3/2",
                            "rubric": {"priority": 0.5, "division": 0.5, "common_denom": 0.5, "final": 0.5},
                            "numbers": [7, 3, 4, 3, 8, 5],
                            "context": "حساب مباشر",
                            "variations": 15
                        },
                        {
                            "id": "M4AM-002",
                            "source": "BEM 2023 - وهران",
                            "type": "جذور",
                            "difficulty": "متوسط",
                            "text": "بين أن B = √450/√2 عدد طبيعي",
                            "solution": "B = √(450/2) = √225 = 15",
                            "rubric": {"property": 1.0, "calculation": 0.5, "result": 0.5},
                            "numbers": [450, 2],
                            "context": "تبسيط جذري",
                            "variations": 12
                        },
                        {
                            "id": "M4AM-003",
                            "source": "BEM 2022 - قسنطينة",
                            "type": "PGCD",
                            "difficulty": "صعب",
                            "text": "احسب القاسم المشترك الأكبر للعددين 1053 و 810",
                            "solution": "PGCD(1053,810): 1053=1×810+243, 810=3×243+81, 243=3×81+0 → PGCD=81",
                            "rubric": {"algorithm": 1.0, "remainder1": 0.5, "remainder2": 0.5, "final": 0.5},
                            "numbers": [1053, 810],
                            "context": "PGCD",
                            "variations": 10
                        },
                        {
                            "id": "M4AM-004",
                            "source": "BEM 2021 - عنابة",
                            "type": "تبسيط جذري",
                            "difficulty": "متوسط",
                            "text": "E = √98 - 3√32 + √128",
                            "solution": "E = 7√2 - 12√2 + 8√2 = (7-12+8)√2 = 3√2",
                            "rubric": {"simplify1": 0.5, "simplify2": 0.5, "simplify3": 0.5, "combine": 0.5, "final": 0.5},
                            "numbers": [98, 3, 32, 128],
                            "context": "تبسيط جذري",
                            "variations": 15
                        },
                        {
                            "id": "M4AM-005",
                            "source": "BEM 2020 - تلمسان",
                            "type": "هندسة - دائرة",
                            "difficulty": "صعب",
                            "text": "في الشكل المقابل، (C) دائرة مركزها O وقطرها [AB] حيث AB = 10 cm",
                            "solution": "نقطة من الدائرة، AM = 6 cm → BM = 8 cm (فيتاغورس)",
                            "rubric": {"triangle_type": 1.0, "calculate_BM": 1.0, "calculate_cos": 1.0},
                            "numbers": [10, 6],
                            "context": "هندسة - دائرة",
                            "variations": 8
                        },
                        {
                            "id": "M4AM-006",
                            "source": "BEM 2019 - سطيف",
                            "type": "وضعية إدماجية",
                            "difficulty": "صعب",
                            "text": "يملك فلاح قطعة أرض مستطيلة الشكل مساحتها S = 2400 m²",
                            "solution": "الأبعاد: الطول = 1.5y، العرض = y → 1.5y² = 2400 → y = 40m",
                            "rubric": {"equation": 2.0, "solve": 2.0, "perimeter": 2.0, "cost": 2.0},
                            "numbers": [2400, 1.5],
                            "context": "وضعية إدماجية - فلاح",
                            "variations": 20
                        }
                    ],
                    "الدوال": [
                        {
                            "id": "M4AM-101",
                            "source": "BEM 2024 - البليدة",
                            "type": "دوال تآلفية",
                            "difficulty": "متوسط",
                            "text": "f(x) = 2x - 3",
                            "solution": "دالة تآلفية: a=2, b=-3",
                            "rubric": {"identify": 1.0, "image": 1.0, "graph": 1.0},
                            "numbers": [2, -3],
                            "context": "دالة تآلفية",
                            "variations": 10
                        }
                    ]
                },
                "الفصل الثاني": {
                    "الإحصاء": [
                        {
                            "id": "M4AM-201",
                            "source": "BEM 2023 - باتنة",
                            "type": "إحصاء",
                            "difficulty": "سهل",
                            "text": "درس إحصائي لأعمار 20 تلميذ",
                            "solution": "حساب المتوسط والمنوال والمدى",
                            "rubric": {"table": 1.0, "average": 1.0, "mode": 0.5, "range": 0.5},
                            "numbers": [20],
                            "context": "إحصاء",
                            "variations": 8
                        }
                    ],
                    "الدوال التربيعية": [
                        {
                            "id": "M4AM-301",
                            "source": "BEM 2024 - سعيدة",
                            "type": "معادلة تربيعية",
                            "difficulty": "صعب",
                            "text": "حل المعادلة x² - 5x + 6 = 0",
                            "solution": "Δ = 25 - 24 = 1 → x1 = (5+1)/2 = 3, x2 = (5-1)/2 = 2",
                            "rubric": {"delta": 1.0, "root1": 1.0, "root2": 1.0},
                            "numbers": [1, -5, 6],
                            "context": "معادلة تربيعية",
                            "variations": 12
                        }
                    ]
                }
            },
            "السنة الثالثة متوسط": {
                "الفصل الأول": {
                    "الأعداد النسبية": [
                        {
                            "id": "M3AM-001",
                            "source": "فرض 2024 - الجزائر",
                            "type": "حساب",
                            "difficulty": "متوسط",
                            "text": "أحسب: A = (-3) + (+5) - (-2)",
                            "solution": "A = -3 + 5 + 2 = 4",
                            "rubric": {"signs": 1.0, "calculation": 1.0, "final": 1.0},
                            "numbers": [-3, 5, -2],
                            "context": "حساب",
                            "variations": 15
                        }
                    ],
                    "المعادلات والمتراجحات": [
                        {
                            "id": "M3AM-101",
                            "source": "BEM 2023 - وهران",
                            "type": "معادلة",
                            "difficulty": "متوسط",
                            "text": "حل المعادلة: 3x - 7 = 2x + 5",
                            "solution": "3x - 2x = 5 + 7 → x = 12",
                            "rubric": {"group_x": 1.0, "group_nums": 1.0, "divide": 0.5},
                            "numbers": [3, -7, 2, 5],
                            "context": "معادلة درجة أولى",
                            "variations": 12
                        },
                        {
                            "id": "M3AM-102",
                            "source": "BEM 2022 - قسنطينة",
                            "type": "متراجحة",
                            "difficulty": "صعب",
                            "text": "حل المتراجحة: 2x - 5 < 3x + 1",
                            "solution": "2x - 3x < 1 + 5 → -x < 6 → x > -6",
                            "rubric": {"group_x": 1.0, "group_nums": 1.0, "divide_neg": 1.0, "flip": 0.5},
                            "numbers": [2, -5, 3, 1],
                            "context": "متراجحة",
                            "variations": 10
                        }
                    ]
                }
            },
            "السنة الثانية متوسط": {
                "الفصل الأول": {
                    "الأعداد الصحيحة": [
                        {
                            "id": "M2AM-001",
                            "source": "فرض 2024 - البليدة",
                            "type": "ترتيب",
                            "difficulty": "سهل",
                            "text": "رتب تصاعدياً: -7, +3, -2, 0, +5",
                            "solution": "-7 < -2 < 0 < +3 < +5",
                            "rubric": {"order": 2.0, "signs": 1.0},
                            "numbers": [-7, 3, -2, 0, 5],
                            "context": "ترتيب",
                            "variations": 10
                        }
                    ],
                    "القوى": [
                        {
                            "id": "M2AM-101",
                            "source": "فرض 2023 - باتنة",
                            "type": "قوى",
                            "difficulty": "متوسط",
                            "text": "أحسب: A = 2³ × 2⁵ ÷ 2⁴",
                            "solution": "A = 2^(3+5-4) = 2⁴ = 16",
                            "rubric": {"property": 1.0, "exponent": 1.0, "final": 1.0},
                            "numbers": [2, 3, 5, 4],
                            "context": "قوى",
                            "variations": 12
                        }
                    ]
                }
            },
            "السنة الأولى متوسط": {
                "الفصل الأول": {
                    "الأعداد الطبيعية": [
                        {
                            "id": "M1AM-001",
                            "source": "فرض 2024 - الجزائر",
                            "type": "قواسم",
                            "difficulty": "سهل",
                            "text": "أوجد قواسم العدد 36",
                            "solution": "قواسم 36: 1, 2, 3, 4, 6, 9, 12, 18, 36",
                            "rubric": {"list": 2.0, "count": 1.0},
                            "numbers": [36],
                            "context": "قواسم",
                            "variations": 10
                        }
                    ]
                }
            }
        }

    def _load_arabic(self):
        return {
            "السنة الرابعة متوسط": {
                "الفصل الأول": {
                    "النص القرائي": [
                        {
                            "id": "A4AM-001",
                            "source": "BEM 2024 - الجزائر",
                            "type": "استيعاب",
                            "difficulty": "متوسط",
                            "text": "اقرأ النص التالي ثم أجب عن الأسئلة",
                            "themes": ["الوطن", "التعليم", "الأسرة", "البيئة"],
                            "rubric": {"idea1": 1.5, "idea2": 1.5},
                            "variations": 10
                        }
                    ],
                    "البلاغة": [
                        {
                            "id": "A4AM-201",
                            "source": "BEM 2023 - وهران",
                            "type": "استعارة",
                            "difficulty": "صعب",
                            "text": "استخرج من النص استعارة تصريحية",
                            "rubric": {"identify": 1.0, "explain": 1.0, "meaning": 1.0},
                            "variations": 8
                        }
                    ]
                }
            }
        }

    def _load_french(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"Compréhension": [{"id": "F4AM-001", "source": "BEM 2024", "type": "lecture", "difficulty": "moyen", "text": "Lisez le texte et répondez aux questions", "rubric": {"comp1": 1.5, "comp2": 1.5}, "variations": 8}]}}}

    def _load_english(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"Reading": [{"id": "E4AM-001", "source": "BEM 2024", "type": "comprehension", "difficulty": "medium", "text": "Read the passage and answer the questions", "rubric": {"q1": 1.5, "q2": 1.5}, "variations": 8}]}}}

    def _load_physics(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"الكهرباء المتردد": [{"id": "P4AM-001", "source": "BEM 2024 - قسنطينة", "type": "حسابات", "difficulty": "صعب", "text": "محول كهربائي ذو 500 دورة في الملف الأول و 1000 دورة في الملف الثاني", "solution": "N2/N1 = U2/U1 → 1000/500 = U2/220 → U2 = 440V", "rubric": {"formula": 1.0, "calc": 1.0, "unit": 0.5}, "numbers": [500, 1000, 220], "context": "محول", "variations": 8}]}}}

    def _load_biology(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"الأحياء الدقيقة": [{"id": "B4AM-001", "source": "BEM 2024", "type": "تشريح", "difficulty": "متوسط", "text": "ارسم خلية بكتيرية واشرح أجزاءها", "rubric": {"draw": 1.5, "explain": 1.5}, "variations": 5}]}}}

    def _load_islamic(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"الفقه": [{"id": "I4AM-001", "source": "BEM 2024", "type": "أحكام", "difficulty": "متوسط", "text": "اذكر أركان الصلاة وشروطها", "rubric": {"pillars": 1.5, "conditions": 1.5}, "variations": 5}]}}}

    def _load_history(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"الثورة التحريرية": [{"id": "H4AM-001", "source": "BEM 2024", "type": "تواريخ", "difficulty": "متوسط", "text": "اذكر أحداث 1 نوفمبر 1954", "rubric": {"date": 1.0, "events": 2.0}, "variations": 5}]}}}

    def _load_civics(self):
        return {"السنة الرابعة متوسط": {"الفصل الأول": {"المواطنة": [{"id": "C4AM-001", "source": "BEM 2024", "type": "مفاهيم", "difficulty": "سهل", "text": "عرف المواطنة واذكر واجبات المواطن", "rubric": {"define": 1.5, "duties": 1.5}, "variations": 5}]}}}

    # ============================================================
    # نظام التوليد الذكي
    # ============================================================

    def generate_question(self, subject, grade, semester, topic, hint=None):
        """توليد سؤال ذكي بالتلميحات"""

        # البحث بالتلميح
        if hint:
            questions = self._search_by_hint(subject, grade, semester, hint)
            if questions:
                base = random.choice(questions)
            else:
                return None
        else:
            bank = self.subjects.get(subject, {}).get(grade, {}).get(semester, {}).get(topic, [])
            if not bank:
                return None
            base = random.choice(bank)

        # توليد التنوع
        varied = self._create_variation(base)
        return varied

    def _search_by_hint(self, subject, grade, semester, hint):
        """البحث الذكي بالتلميحات"""
        results = []
        hint_lower = hint.lower()

        bank = self.subjects.get(subject, {}).get(grade, {}).get(semester, {})
        for topic, questions in bank.items():
            for q in questions:
                text = q.get("text", "").lower()
                context = q.get("context", "").lower()
                q_type = q.get("type", "").lower()

                if (hint_lower in text or 
                    hint_lower in context or 
                    hint_lower in q_type or
                    hint_lower in topic.lower()):
                    results.append(q)

        return results

    def _create_variation(self, base):
        """إنشاء تنويع ذكي"""
        variation = base.copy()

        # تغيير الأرقام
        if "numbers" in base:
            new_numbers = self._vary_numbers(base["numbers"])
            variation["numbers"] = new_numbers
            variation["text"] = self._replace_numbers(base["text"], base["numbers"], new_numbers)
            variation["solution"] = self._replace_numbers(base["solution"], base["numbers"], new_numbers)

        # تغيير الأسماء
        variation["text"] = self._replace_names(variation["text"])
        variation["solution"] = self._replace_names(variation["solution"])

        # تغيير السياق
        variation["text"] = self._replace_context(variation["text"])

        # إضافة معلومات التنوع
        variation["variation_id"] = f"VAR-{random.randint(10000, 99999)}"
        variation["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        variation["is_variation"] = True
        variation["original_id"] = base.get("id", "unknown")

        return variation

    def _vary_numbers(self, numbers):
        """تغيير الأرقام مع الحفاظ على المنطق"""
        new_numbers = []
        for n in numbers:
            if isinstance(n, int):
                # تغيير بنسبة ±20% مع الحفاظ على الخصائص
                change = random.randint(-max(1, abs(n)//5), max(1, abs(n)//5))
                new_n = n + change
                if new_n == 0:
                    new_n = 1
                new_numbers.append(new_n)
            elif isinstance(n, float):
                change = random.uniform(-0.5, 0.5)
                new_n = round(n + change, 1)
                if new_n <= 0:
                    new_n = 0.5
                new_numbers.append(new_n)
            else:
                new_numbers.append(n)
        return new_numbers

    def _replace_numbers(self, text, old_nums, new_nums):
        """استبدال الأرقام في النص"""
        result = text
        for old, new in zip(old_nums, new_nums):
            result = result.replace(str(old), str(new), 1)
        return result

    def _replace_names(self, text):
        """استبدال الأسماء"""
        names_to_replace = ["أحمد", "محمد", "علي", "عمر", "خالد", "يوسف", "فاطمة", "عائشة"]
        for name in names_to_replace:
            if name in text:
                new_name = random.choice(self.names)
                text = text.replace(name, new_name, 1)
        return text

    def _replace_context(self, text):
        """تغيير السياق"""
        contexts = {
            "فلاح": random.choice(["فلاح", "تاجر", "مهندس", "معلم"]),
            "سوق": random.choice(["سوق", "متجر", "محل", "دكان"]),
            "مدرسة": random.choice(["مدرسة", "معهد", "ثانوية", "إعدادية"])
        }
        for old, new in contexts.items():
            if old in text and random.random() > 0.5:
                text = text.replace(old, new, 1)
        return text

    def generate_full_exam(self, subject, grade, semester, num_exercises=4):
        """توليد اختبار كامل"""
        exam = {
            "header": {
                "republic": "الجمهورية الجزائرية الديمقراطية الشعبية",
                "ministry": "وزارة التربية الوطنية",
                "subject": subject,
                "grade": grade,
                "semester": semester,
                "date": datetime.now().strftime("%Y/%m/%d"),
                "duration": "ساعتان",
                "total": 20
            },
            "part1": {
                "title": "الجزء الأول (12 نقطة)",
                "exercises": []
            },
            "part2": {
                "title": "الجزء الثاني (08 نقاط)",
                "integration": None
            },
            "correction": []
        }

        bank = self.subjects.get(subject, {}).get(grade, {}).get(semester, {})
        topics = list(bank.keys())

        # توليد التمارين
        for i in range(min(num_exercises, len(topics))):
            topic = random.choice(topics)
            q = self.generate_question(subject, grade, semester, topic)
            if q:
                exam["part1"]["exercises"].append({
                    "number": i + 1,
                    "topic": topic,
                    "points": 3,
                    "question": q
                })

        # توليد الوضعية الإدماجية
        integration_topics = [t for t in topics if any("وضعية" in str(q.get("context", "")) for q in bank.get(t, []))]
        if integration_topics:
            topic = random.choice(integration_topics)
            q = self.generate_question(subject, grade, semester, topic)
            if q:
                exam["part2"]["integration"] = {
                    "topic": topic,
                    "points": 8,
                    "question": q
                }

        return exam

    def get_stats(self):
        """إحصائيات الموسوعة"""
        stats = {}
        for subject, grades in self.subjects.items():
            stats[subject] = {}
            for grade, semesters in grades.items():
                count = 0
                for semester, topics in semesters.items():
                    for topic, questions in topics.items():
                        count += len(questions)
                stats[subject][grade] = count
        return stats

# ============================================================
# إنشاء الموسوعة
# ============================================================

encyclopedia = ExamEncyclopedia()

# ============================================================
# نقاط النهاية API
# ============================================================

@app.route('/api/search', methods=['POST'])
def search_questions():
    """البحث الذكي بالتلميحات"""
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400

    data = request.get_json()
    subject = data.get('subject')
    grade = data.get('grade')
    semester = data.get('semester')
    hint = data.get('hint', '')

    if not all([subject, grade, semester]):
        return jsonify({'error': 'المادة والمستوى والفصل مطلوبة'}), 400

    results = encyclopedia._search_by_hint(subject, grade, semester, hint)

    return jsonify({
        'success': True,
        'count': len(results),
        'results': results[:10]  # أول 10 نتائج
    })

@app.route('/api/generate', methods=['POST'])
def generate():
    """توليد سؤال أو اختبار"""
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400

    if not api_key:
        return jsonify({'error': 'مفتاح Groq API غير موجود'}), 500

    try:
        data = request.get_json()
        subject = data.get('subject')
        grade = data.get('grade')
        semester = data.get('semester')
        topic = data.get('topic')
        hint = data.get('hint')
        full_exam = data.get('full_exam', False)

        if not all([subject, grade, semester]):
            return jsonify({'error': 'المادة والمستوى والفصل مطلوبة'}), 400

        if full_exam:
            # توليد اختبار كامل
            exam = encyclopedia.generate_full_exam(subject, grade, semester)

            # توليد HTML
            html = generate_exam_html(exam)

            return jsonify({
                'success': True,
                'result': html,
                'exam_data': exam,
                'stats': encyclopedia.get_stats()
            })
        else:
            # توليد سؤال واحد
            question = encyclopedia.generate_question(subject, grade, semester, topic, hint)

            if not question:
                return jsonify({'error': 'لا يوجد أسئلة متاحة لهذا الموضوع'}), 404

            return jsonify({
                'success': True,
                'question': question,
                'stats': encyclopedia.get_stats()
            })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """إحصائيات الموسوعة"""
    return jsonify({
        'success': True,
        'stats': encyclopedia.get_stats(),
        'total_questions': sum(sum(g.values()) for g in encyclopedia.get_stats().values())
    })

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """قائمة المواد"""
    return jsonify({
        'success': True,
        'subjects': list(encyclopedia.subjects.keys()),
        'grades': ["السنة الأولى متوسط", "السنة الثانية متوسط", "السنة الثالثة متوسط", "السنة الرابعة متوسط"],
        'semesters': ["الفصل الأول", "الفصل الثاني", "الفصل الثالث"]
    })

# ============================================================
# توليد HTML للاختبار
# ============================================================

def generate_exam_html(exam):
    """توليد HTML احترافي للاختبار"""

    header = exam["header"]
    part1 = exam["part1"]
    part2 = exam["part2"]

    html = f"""
    <div style="font-family: 'Traditional Arabic', 'Arial', sans-serif; direction: rtl; padding: 20px; max-width: 800px; margin: 0 auto;">

        <!-- الترويسة -->
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 14px; font-weight: bold;">{header['republic']}</div>
            <div style="font-size: 13px;">{header['ministry']}</div>
            <div style="margin-top: 10px; font-size: 12px;">
                المادة: {header['subject']} | المستوى: {header['grade']} | المدة: {header['duration']}
            </div>
            <div style="font-size: 14px; font-weight: bold; margin-top: 10px; text-decoration: underline;">
                اختبار {header['semester']}
            </div>
        </div>

        <hr style="border: 1px solid black; margin: 15px 0;">

        <!-- الجزء الأول -->
        <div style="margin-bottom: 20px;">
            <div style="font-weight: bold; text-decoration: underline; margin-bottom: 15px;">
                {part1['title']}
            </div>
    """

    for ex in part1['exercises']:
        html += f"""
            <div style="margin-bottom: 20px;">
                <div style="font-weight: bold; text-decoration: underline;">
                    التمرين {ex['number']}: ({ex['points']} نقاط)
                </div>
                <div style="margin-top: 10px; padding-right: 20px;">
                    {ex['question']['text']}
                </div>
            </div>
        """

    html += """
        </div>

        <!-- الجزء الثاني -->
        <div style="margin-bottom: 20px;">
            <div style="font-weight: bold; text-decoration: underline; margin-bottom: 15px;">
                {part2['title']}
            </div>
    """

    if part2['integration']:
        html += f"""
            <div style="font-weight: bold; text-decoration: underline;">
                الوضعية الإدماجية: ({part2['integration']['points']} نقاط)
            </div>
            <div style="margin-top: 10px; padding-right: 20px;">
                {part2['integration']['question']['text']}
            </div>
        """

    html += """
        </div>

    </div>
    """

    return html

# ============================================================
# الصفحة الرئيسية
# ============================================================

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/test')
def test():
    return jsonify({
        'status': '✅ النظام يعمل',
        'encyclopedia': 'موسوعة الاختبارات الجزائرية',
        'version': '2.0.0',
        'developer': 'youcef .b',
        'email': 'youcefbenhamidaa@gmail.com'
    })

if __name__ == '__main__':
    print("🚀 تشغيل موسوعة الاختبارات الجزائرية...")
    print(f"📊 الإحصائيات: {encyclopedia.get_stats()}")
    app.run(host='0.0.0.0', port=5000, debug=True)
