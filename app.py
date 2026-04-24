# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║     منصة الاختبارات الجزائرية الذكية - الإصدار المدمج الاحترافي   ║
║                                                                  ║
║  المطور: youcef .b                                               ║
║  البريد: youcefbenhamidaa@gmail.com                             ║
║  © 2025 جميع الحقوق محفوظة                                       ║
╚══════════════════════════════════════════════════════════════════╝

المميزات:
- 📚 منهج جزائري شامل (12 مادة × 4 سنوات × 3 فصول)
- 🧠 توليد ذكي: 70% من البنك + 30% بالذكاء الاصطناعي
- 🔄 نظام تنويع تلقائي (أرقام، أسماء، سياقات)
- 🔍 بحث ذكي بالتلميحات والكلمات المفتاحية
- 📊 إحصائيات وتقارير مفصلة
- 💾 تصدير/استيراد بنك الأسئلة
- 🎯 سلم تنقيط مفصل لكل سؤال
"""

from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
import os, json, random, re, traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

# ============================================================
# 1. إعدادات البيئة والذكاء الاصطناعي
# ============================================================
load_dotenv()
API_KEY = os.getenv('GROQ_API_KEY')

if API_KEY:
    ai_client = Groq(api_key=API_KEY)
    print("✅ Groq AI Client Ready")
else:
    ai_client = None
    print("⚠️ Groq API Key not found - AI generation disabled")

app = Flask(__name__, static_folder='.', static_url_path='')

# ============================================================
# 2. قاعدة بيانات المنهاج الجزائري الشاملة
# ============================================================
CURRICULUM_DB = {
    "الرياضيات": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["الأعداد الطبيعية والعشرية", "العمليات على الأعداد", "القاسم المشترك الأكبر"],
            "الفصل الثاني": ["الكسور", "النسبة والتناسب", "المعادلات البسيطة"],            "الفصل الثالث": ["الزوايا", "المثلثات", "الدوائر"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الأعداد النسبية", "القوى", "الجذور"],
            "الفصل الثاني": ["المعادلات", "الدوال", "الإحصاء"],
            "الفصل الثالث": ["المتوازيات", "مبرهنة طاليس", "التشابه"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الأعداد الحقيقية", "المتطابقات الهامة", "الجذور"],
            "الفصل الثاني": ["المعادلات والمتراجحات", "الدوال التآلفية", "الإحصاء"],
            "الفصل الثالث": ["النسب المثلثية", "المتجهات", "هندسة الفضاء"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["المعادلات من الدرجة الثانية", "الدوال", "التغيرات"],
            "الفصل الثاني": ["الإحصاء", "الدوال التربيعية", "الاحتمالات"],
            "الفصل الثالث": ["الهندسة في الفضاء", "المساحات والحجوم", "التكافؤ"]
        }
    },
    "اللغة العربية": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["النص القرائي: الوطن", "النحو: المبتدأ والخبر", "الإملاء"],
            "الفصل الثاني": ["النص القرائي: الأسرة", "النحو: الفاعل", "التعبير"],
            "الفصل الثالث": ["النص القرائي: البيئة", "النحو: النعت", "البلاغة"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["النص القرائي: التراث", "النحو: المضاف", "الصرف"],
            "الفصل الثاني": ["النص القرائي: العلم", "النحو: الأفعال الخمسة", "البلاغة"],
            "الفصل الثالث": ["النص القرائي: السلام", "النحو: الضمائر", "التعبير"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["النص القرائي: التاريخ", "النحو: المفعول المطلق", "العروض"],
            "الفصل الثاني": ["النص القرائي: الاقتصاد", "النحو: المستثنى", "البلاغة"],
            "الفصل الثالث": ["النص القرائي: الفنون", "النحو: التوابع", "التعبير"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["النص القرائي: القيم", "النحو: إعراب الفعل", "البلاغة: التشبيه"],
            "الفصل الثاني": ["النص القرائي: التحديات", "النحو: المبني للمجهول", "العروض"],
            "الفصل الثالث": ["النص القرائي: الهوية", "النحو: التوابع", "الحجاج"]
        }
    },
    "اللغة الفرنسية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["Compréhension", "Grammaire: présent", "Vocabulaire: famille"],
            "الفصل الثاني": ["Expression écrite", "Grammaire: passé composé", "Vocabulaire: loisirs"],
            "الفصل الثالث": ["Texte argumentatif", "Grammaire: subjonctif", "Vocabulaire: environnement"]
        }
    },
    "اللغة الإنجليزية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["Present Simple", "Daily routines", "Family"],            "الفصل الثاني": ["Past Simple", "School life", "Hobbies"],
            "الفصل الثالث": ["Future with will", "Environment", "Technology"]
        }
    },
    "العلوم الفيزيائية والتكنولوجيا": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["الضوء", "المرآة", "العدسات"],
            "الفصل الثاني": ["الكهرباء", "الدوائر", "الموصلات"],
            "الفصل الثالث": ["المادة", "التحولات", "الخلائط"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الحركة", "القوى", "التوازن"],
            "الفصل الثاني": ["الضغط", "الطفو", "الضغط الجوي"],
            "الفصل الثالث": ["الطاقة", "أشكال الطاقة", "التحولات"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["التيار المستمر", "قانون أوم", "القدرة"],
            "الفصل الثاني": ["الحركة والقوى", "العمل والطاقة", "الآلات"],
            "الفصل الثالث": ["انكسار الضوء", "العدسات", "العين"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["التيار المتردد", "المحولات", "التوزيع"],
            "الفصل الثاني": ["الحركة الدائرية", "الجاذبية", "الأقمار"],
            "الفصل الثالث": ["الطاقة النووية", "التفاعلات", "الاستخدامات"]
        }
    },
    "علوم الطبيعة والحياة": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["التغذية", "الجهاز الهضمي", "المواد الغذائية"],
            "الفصل الثاني": ["التنفس", "الجهاز التنفسي", "تبادل الغازات"],
            "الفصل الثالث": ["النباتات", "التكاثر", "البذور"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الجهاز الدوري", "الدم", "القلب"],
            "الفصل الثاني": ["الجهاز البولي", "الهرمونات", "الجهاز العصبي"],
            "الفصل الثالث": ["التكاثر", "الجهاز التناسلي", "النمو"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الخلايا", "الأغشية", "التنظيم"],
            "الفصل الثاني": ["الوراثة", "الجينات", "الشفرة الوراثية"],
            "الفصل الثالث": ["النظم البيئية", "التنوع", "الحماية"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["الأحياء الدقيقة", "البكتيريا", "الفيروسات"],
            "الفصل الثاني": ["المناعة", "اللقاحات", "الأمراض"],
            "الفصل الثالث": ["التكنولوجيا الحيوية", "الهندسة الوراثية", "التطبيقات"]
        }
    },
    "التربية الإسلامية": {
        "السنة الأولى متوسط": {            "الفصل الأول": ["التوحيد", "الإيمان بالملائكة", "الكتب السماوية"],
            "الفصل الثاني": ["الإيمان بالرسل", "اليوم الآخر", "القدر"],
            "الفصل الثالث": ["الطهارة", "الصلاة", "الزكاة"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الصيام", "الحج", "الجهاد"],
            "الفصل الثاني": ["آداب الطعام", "آداب اللباس", "آداب السفر"],
            "الفصل الثالث": ["الأخلاق", "بر الوالدين", "صلة الرحم"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["السيرة: مكة", "الهجرة", "الغزوات"],
            "الفصل الثاني": ["صلح الحديبية", "فتح مكة", "الوداع"],
            "الفصل الثالث": ["القيم", "التسامح", "العدل"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["المعاملات", "البيوع", "الرهن"],
            "الفصل الثاني": ["الأسرة", "الزواج", "الطلاق"],
            "الفصل الثالث": ["القضاء", "الشورى", "المواطنة"]
        }
    },
    "التاريخ والجغرافيا": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["الجزائر القديمة", "الحضارات", "القرطاجيون"],
            "الفصل الثاني": ["العصر الوسيط", "الفتح الإسلامي", "الدول الإسلامية"],
            "الفصل الثالث": ["موقع الجزائر", "التضاريس", "المناخ"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الجزائر العثمانية", "الإيالة", "الحياة الاجتماعية"],
            "الفصل الثاني": ["الاستعمار", "المقاومة", "الثورة"],
            "الفصل الثالث": ["السكان", "المدن", "النقل"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الجمهورية", "البناء الوطني", "التنمية"],
            "الفصل الثاني": ["الحرب العالمية الأولى", "الثانية", "الحرب الباردة"],
            "الفصل الثالث": ["الموارد", "الفلاحة", "الصناعة"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["العولمة", "المنظمات", "الأمم المتحدة"],
            "الفصل الثاني": ["حركات التحرر", "الاستقلال", "الديمقراطية"],
            "الفصل الثالث": ["البحر المتوسط", "الشرق الأوسط", "إفريقيا"]
        }
    },
    "التربية المدنية": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["المواطنة", "الحقوق", "الدستور"],
            "الفصل الثاني": ["المؤسسات", "البلدية", "الولاية"],
            "الفصل الثالث": ["العدالة", "المحكمة", "القانون"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الديمقراطية", "الانتخابات", "الأحزاب"],            "الفصل الثاني": ["حقوق الإنسان", "الحرية", "المساواة"],
            "الفصل الثالث": ["السلام", "التسامح", "الحوار"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الاقتصاد", "الموارد", "التنمية"],
            "الفصل الثاني": ["البيئة", "التلوث", "الحماية"],
            "الفصل الثالث": ["العولمة", "التحديات", "الهوية"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["المواطنة الرقمية", "الأمن السيبراني", "المعلوماتية"],
            "الفصل الثاني": ["المشاركة", "التطوع", "المجتمع المدني"],
            "الفصل الثالث": ["الجزائر والعالم", "العلاقات", "الانفتاح"]
        }
    },
    "التربية الفنية التشكيلية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["الرسم الهندسي", "الأشكال", "التناظر"],
            "الفصل الثاني": ["الألوان", "الظل والنور", "التكوين"],
            "الفصل الثالث": ["الفن الجزائري", "الفن الأمازيغي", "الفن المعاصر"]
        }
    },
    "التربية الموسيقية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["المقامات", "البياتي", "الراست"],
            "الفصل الثاني": ["الإيقاع", "الأوزان", "الطبول"],
            "الفصل الثالث": ["الأغنية الجزائرية", "الشعبي", "الراي"]
        }
    },
    "التربية البدنية والرياضية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["الجري", "السباقات", "التحمل"],
            "الفصل الثاني": ["كرة القدم", "المهارات", "التكتيك"],
            "الفصل الثالث": ["الجمباز", "التوازن", "المرونة"]
        }
    },
    "الإعلام الآلي": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["مكونات الحاسوب", "نظام التشغيل", "معالجة النصوص"],
            "الفصل الثاني": ["الإنترنت", "البريد الإلكتروني", "أمن المعلومات"],
            "الفصل الثالث": ["البرمجة", "الخوارزميات", "المشاريع"]
        }
    }
}

VALID_SUBJECTS = list(CURRICULUM_DB.keys())
VALID_GRADES = ["السنة الأولى متوسط", "السنة الثانية متوسط", "السنة الثالثة متوسط", "السنة الرابعة متوسط"]
VALID_SEMESTERS = ["الفصل الأول", "الفصل الثاني", "الفصل الثالث"]

# ============================================================
# 3. بنك الأسئلة الذكي - مع نظام التنويع التلقائي# ============================================================
class QuestionBank:
    """بنك الأسئلة الذكي مع نظام التنويع والتوليد"""
    
    def __init__(self, bank_file: str = 'question_bank.json'):
        self.bank_file = bank_file
        self.questions = self._load_bank()
        
        # قوالب التنويع
        self.names = ["أحمد", "محمد", "علي", "عمر", "خالد", "يوسف", "كريم", "نور", "سامي", "رامي",
                      "فاطمة", "عائشة", "مريم", "ليلى", "سارة", "هدى", "رحمة", "زينب"]
        self.places = ["سوق", "مدرسة", "حديقة", "متجر", "ورشة", "مستشفى", "مكتبة", "مطعم", "ملعب", "مسجد"]
        self.professions = ["فلاح", "تاجر", "مهندس", "معلم", "طباخ", "نجار", "حداد", "خياط", "طبيب", "سائق"]
        self.cities = ["الجزائر", "وهران", "قسنطينة", "عنابة", "تلمسان", "سطيف", "البليدة", "باتنة", "بسكرة", "تيارت"]
        self.sports = ["كرة القدم", "كرة السلة", "السباحة", "الجري", "الدراجات", "الملاكمة", "التنس"]

    def _load_bank(self) -> List[Dict]:
        """تحميل بنك الأسئلة من الملف"""
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_bank(self):
        """حفظ بنك الأسئلة في الملف"""
        # الاحتفاظ بآخر 200 سؤال فقط
        if len(self.questions) > 200:
            self.questions = self.questions[-200:]
        with open(self.bank_file, 'w', encoding='utf-8') as f:
            json.dump(self.questions, f, ensure_ascii=False, indent=2)

    def add_question(self, question: Dict) -> str:
        """إضافة سؤال جديد للبنك"""
        question['id'] = f"Q-{random.randint(10000, 99999)}"
        question['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        question['usage_count'] = 0
        self.questions.append(question)
        self._save_bank()
        return question['id']

    def search(self, subject: str = None, grade: str = None, 
               semester: str = None, hint: str = None, 
               topic: str = None, difficulty: str = None) -> List[Dict]:
        """بحث ذكي متعدد المعايير"""
        results = []
        hint_lower = hint.lower() if hint else None
                for q in self.questions:
            # فلترة حسب المعايير
            if subject and q.get('subject') != subject: continue
            if grade and q.get('grade') != grade: continue
            if semester and q.get('semester') != semester: continue
            if difficulty and q.get('difficulty') != difficulty: continue
            
            # بحث بالتلميح
            if hint_lower:
                text = q.get('text', '').lower()
                context = q.get('context', '').lower()
                q_type = q.get('type', '').lower()
                q_topic = q.get('topic', '').lower()
                
                if not (hint_lower in text or hint_lower in context or 
                        hint_lower in q_type or hint_lower in q_topic):
                    continue
            
            # بحث بالموضوع
            if topic and topic.lower() not in q.get('topic', '').lower():
                continue
                
            results.append(q)
        
        # ترتيب عشوائي مع تفضيل الأسئلة الأقل استخداماً
        random.shuffle(results)
        return sorted(results, key=lambda x: x.get('usage_count', 0))[:20]

    def create_variation(self, question: Dict) -> Dict:
        """إنشاء تنويع ذكي للسؤال"""
        varied = question.copy()
        
        # تغيير الأرقام مع الحفاظ على المنطق
        if 'numbers' in question and question['numbers']:
            new_numbers = self._vary_numbers(question['numbers'])
            varied['numbers'] = new_numbers
            varied['text'] = self._replace_numbers(question['text'], question['numbers'], new_numbers)
            if 'solution' in question:
                varied['solution'] = self._replace_numbers(question['solution'], question['numbers'], new_numbers)
        
        # تغيير الأسماء والسياقات
        varied['text'] = self._replace_contexts(varied['text'])
        if 'solution' in varied:
            varied['solution'] = self._replace_contexts(varied['solution'])
        
        # تحديث البيانات الوصفية
        varied['variation_id'] = f"VAR-{random.randint(10000, 99999)}"
        varied['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        varied['is_variation'] = True
        varied['original_id'] = question.get('id', 'unknown')        varied['usage_count'] = 0
        
        return varied

    def _vary_numbers(self, numbers: List) -> List:
        """تغيير الأرقام بنسبة ±20% مع الحفاظ على الخصائص"""
        new_nums = []
        for n in numbers:
            if isinstance(n, (int, float)):
                if isinstance(n, int):
                    change = random.randint(-max(1, abs(n)//5), max(1, abs(n)//5))
                    new_n = n + change
                    if new_n == 0: new_n = 1
                else:
                    change = random.uniform(-0.5, 0.5)
                    new_n = round(n + change, 1)
                    if new_n <= 0: new_n = 0.5
                new_nums.append(new_n)
            else:
                new_nums.append(n)
        return new_nums

    def _replace_numbers(self, text: str, old_nums: List, new_nums: List) -> str:
        """استبدال الأرقام في النص"""
        result = text
        for old, new in zip(old_nums, new_nums):
            result = result.replace(str(old), str(new), 1)
        return result

    def _replace_contexts(self, text: str) -> str:
        """استبدال الأسماء والسياقات"""
        # استبدال الأسماء
        for name in self.names[:8]:
            if name in text and random.random() > 0.5:
                new_name = random.choice(self.names)
                text = text.replace(name, new_name, 1)
        
        # استبدال الأماكن والمهن
        contexts = {
            "فلاح": random.choice(["فلاح", "تاجر", "مهندس"]),
            "سوق": random.choice(["سوق", "متجر", "محل"]),
            "مدرسة": random.choice(["مدرسة", "معهد", "ثانوية"]),
            "مدينة": random.choice(self.cities)
        }
        for old, new in contexts.items():
            if old in text and random.random() > 0.5:
                text = text.replace(old, new, 1)
        
        return text
    def get_stats(self) -> Dict:
        """إحصائيات بنك الأسئلة"""
        stats = {'total': len(self.questions), 'by_subject': {}, 'by_grade': {}, 'by_difficulty': {}}
        
        for q in self.questions:
            # حسب المادة
            subj = q.get('subject', 'غير مصنف')
            stats['by_subject'][subj] = stats['by_subject'].get(subj, 0) + 1
            
            # حسب المستوى
            grade = q.get('grade', 'غير مصنف')
            stats['by_grade'][grade] = stats['by_grade'].get(grade, 0) + 1
            
            # حسب الصعوبة
            diff = q.get('difficulty', 'غير مصنف')
            stats['by_difficulty'][diff] = stats['by_difficulty'].get(diff, 0) + 1
        
        return stats

    def export_bank(self) -> Dict:
        """تصدير بنك الأسئلة"""
        return {'questions': self.questions, 'exported_at': datetime.now().isoformat()}

    def import_questions(self, questions: List[Dict]) -> int:
        """استيراد أسئلة جديدة"""
        count = 0
        for q in questions:
            if 'id' not in q:
                q['id'] = f"IMP-{random.randint(10000, 99999)}"
            if q['id'] not in [x['id'] for x in self.questions]:
                self.questions.append(q)
                count += 1
        if count > 0:
            self._save_bank()
        return count

# ============================================================
# 4. محرك التوليد الذكي
# ============================================================
class ExamGenerator:
    """محرك توليد الاختبارات الذكي"""
    
    def __init__(self, ai_client, question_bank: QuestionBank):
        self.ai = ai_client
        self.bank = question_bank
        self.ai_ratio = 0.3  # 30% توليد بالذكاء الاصطناعي، 70% من البنك

    def _get_exam_structure(self, subject: str) -> str:
        """هيكل الاختبار حسب المادة"""
        structures = {            "الرياضيات": "التمرين الأول (06ن): حساب/هندسة | التمرين الثاني (06ن): تطبيق | الوضعية (08ن): مسألة مركبة",
            "اللغة العربية": "النص القرائي (06ن) | القواعد والإملاء (06ن) | التعبير (08ن)",
            "اللغة الفرنسية": "Compréhension (06pts) | Langue (06pts) | Expression (08pts)",
            "اللغة الإنجليزية": "Reading (06pts) | Language (06pts) | Writing (08pts)",
            "العلوم الفيزيائية": "التمرين الأول (06ن): مفاهيم | التمرين الثاني (06ن): تحليل | الوضعية (08ن): مشكلة",
            "علوم الطبيعة والحياة": "التمرين الأول (06ن): معارف | التمرين الثاني (06ن): وثائق | الوضعية (08ن): مشكلة",
            "التاريخ والجغرافيا": "التاريخ (10ن): وثائق | الجغرافيا (10ن): دراسة حالة",
            "التربية الإسلامية": "القرآن والحديث (06ن) | العقيدة والفقه (06ن) | السيرة والتهذيب (08ن)",
            "التربية المدنية": "المفاهيم (08ن) | الحقوق (06ن) | الوضعية (06ن)"
        }
        return structures.get(subject, "الجزء الأول (12ن): أسئلة متنوعة | الجزء الثاني (08ن): وضعية إدماجية")

    def _build_ai_prompt(self, data: Dict) -> str:
        """بناء برومبت الذكاء الاصطناعي"""
        subject = data['subject']
        grade = data['grade']
        semester = data.get('semester', 'الفصل الأول')
        topic = data.get('topic', '')
        
        topics = CURRICULUM_DB.get(subject, {}).get(grade, {}).get(semester, [])
        topics_str = ", ".join(topics) if topics else "المنهاج العام"
        
        structure = self._get_exam_structure(subject)
        
        return f"""أنت مفتش تربوي جزائري خبير في مادة {subject}.
أنشئ اختباراً فصلياً احترافياً للمستوى: {grade} ({semester}).

=== البيانات ===
المواضيع: {topics_str}
الموضوع المحدد: {topic if topic else 'اختر من القائمة'}
العلامة: 20/20 | المدة: ساعتان

=== الهيكل المطلوب ===
{structure}

=== الشروط ===
1. المخرج: HTML فقط (بدون ```markdown)
2. الترويسة: الجمهورية الجزائرية، وزارة التربية، المؤسسة
3. اللغة: عربية فصحى (أو لغة المادة)
4. التنوع: غيّر الأرقام والأسماء والسياقات
5. الإجابة: ضع الإجابة النموذجية في <div class="answer-key">
6. المنهاج: التزم بمواضيع {grade}

ابدأ بكتابة كود HTML للاختبار:"""

    def generate_with_ai(self, data: Dict) -> Optional[str]:
        """توليد اختبار بالذكاء الاصطناعي"""
        if not self.ai:
            return None
                try:
            prompt = self._build_ai_prompt(data)
            completion = self.ai.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "أنت مولد اختبارات جزائري. تخرج HTML نظيف فقط."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, max_tokens=4000
            )
            
            html = completion.choices[0].message.content
            html = html.replace('```html', '').replace('```', '').strip()
            
            # إضافة الترويسة إذا لم تكن موجودة
            if "الجمهورية الجزائرية" not in html:
                html = f'''<div class="official-header" style="text-align:center;border-bottom:2px solid #000;padding-bottom:15px;margin-bottom:20px;">
                    <div style="font-weight:bold;font-size:1.1em;">الجمهورية الجزائرية الديمقراطية الشعبية</div>
                    <div>وزارة التربية الوطنية</div>
                    <div>مديرية التربية لولاية: {data.get('directorate', '...')}</div>
                    <div>متوسطة: {data.get('school', '...')}</div>
                </div>
                <div style="text-align:center;margin:20px 0;padding:10px;border:2px solid #000;">
                    <div style="font-size:1.4em;font-weight:bold;text-decoration:underline;">اختبار {data.get('semester', '')}</div>
                    <div>المادة: {data['subject']} | المستوى: {data['grade']} | المدة: {data.get('duration', 'ساعتان')}</div>
                </div>''' + html
            
            return html
        except Exception as e:
            print(f"❌ AI Error: {e}")
            return None

    def generate_from_bank(self, data: Dict) -> Optional[Dict]:
        """توليد اختبار من بنك الأسئلة"""
        subject = data['subject']
        grade = data['grade']
        semester = data.get('semester', 'الفصل الأول')
        topic = data.get('topic')
        
        # البحث عن أسئلة مناسبة
        questions = self.bank.search(subject=subject, grade=grade, semester=semester, topic=topic)
        if not questions:
            return None
        
        # إنشاء هيكل الاختبار
        exam = {
            'header': {
                'subject': subject, 'grade': grade, 'semester': semester,
                'school': data.get('school', '...'), 'directorate': data.get('directorate', '...'),
                'duration': data.get('duration', 'ساعتان'), 'year': data.get('schoolYear', '2024/2025')            },
            'exercises': [],
            'integration': None,
            'correction': []
        }
        
        # اختيار 3 تمارين + وضعية إدماجية
        selected = random.sample(questions, min(4, len(questions)))
        for i, q in enumerate(selected[:3]):
            # إنشاء تنويع
            varied = self.bank.create_variation(q)
            exam['exercises'].append({
                'number': i + 1,
                'points': 4 if i < 2 else 4,  # 4+4+4+8 = 20
                'topic': q.get('topic', ''),
                'question': varied['text'],
                'solution': varied.get('solution', ''),
                'rubric': varied.get('rubric', {}),
                'source': varied.get('source', 'بنك الأسئلة')
            })
            # تحديث عداد الاستخدام
            q['usage_count'] = q.get('usage_count', 0) + 1
        
        # الوضعية الإدماجية
        if len(selected) > 3:
            q = selected[3]
            varied = self.bank.create_variation(q)
            exam['integration'] = {
                'points': 8,
                'topic': q.get('topic', ''),
                'question': varied['text'],
                'solution': varied.get('solution', ''),
                'rubric': varied.get('rubric', {})
            }
        
        return exam

    def generate_exam(self, data: Dict, use_bank: bool = True) -> Dict:
        """توليد اختبار (بنك + ذكاء اصطناعي)"""
        # قرار: من البنك أم بالذكاء الاصطناعي؟
        use_ai = not use_bank or random.random() < self.ai_ratio
        
        if use_bank and not use_ai:
            # من البنك
            exam_data = self.generate_from_bank(data)
            if exam_data:
                html = self._exam_to_html(exam_data)
                return {'success': True, 'result': html, 'source': 'bank', 'data': exam_data}
        
        # بالذكاء الاصطناعي (كاحتياطي أو حسب النسبة)        html = self.generate_with_ai(data)
        if html:
            return {'success': True, 'result': html, 'source': 'ai'}
        
        return {'success': False, 'error': 'فشل التوليد من جميع المصادر'}

    def _exam_to_html(self, exam: Dict) -> str:
        """تحويل بيانات الاختبار إلى HTML"""
        h = exam['header']
        html = f'''<div style="font-family:'Traditional Arabic','Arial',sans-serif;direction:rtl;padding:20px;max-width:800px;margin:0 auto;">
        <div style="text-align:center;border-bottom:2px solid #000;padding-bottom:15px;margin-bottom:20px;">
            <div style="font-weight:bold;font-size:1.1em;">الجمهورية الجزائرية الديمقراطية الشعبية</div>
            <div>وزارة التربية الوطنية</div>
            <div>مديرية التربية لولاية: {h['directorate']}</div>
            <div>متوسطة: {h['school']}</div>
        </div>
        <div style="text-align:center;margin:20px 0;padding:10px;border:2px solid #000;">
            <div style="font-size:1.4em;font-weight:bold;text-decoration:underline;">اختبار {h['semester']}</div>
            <div>المادة: {h['subject']} | المستوى: {h['grade']} | المدة: {h['duration']} | السنة: {h['year']}</div>
        </div>
        <hr style="border:1px solid #000;margin:20px 0;">'''
        
        # التمارين
        for ex in exam['exercises']:
            html += f'''<div style="margin-bottom:25px;">
                <div style="font-weight:bold;font-size:1.1em;text-decoration:underline;margin-bottom:10px;">
                    التمرين {ex['number']}: ({ex['points']} نقاط) - {ex['topic']}
                </div>
                <div style="padding-right:20px;line-height:1.8;">{ex['question']}</div>
            </div>'''
        
        # الوضعية الإدماجية
        if exam['integration']:
            integ = exam['integration']
            html += f'''<div style="margin:30px 0;padding:15px;background:#fff9e6;border-right:4px solid #f39c12;">
                <div style="font-weight:bold;font-size:1.1em;text-decoration:underline;margin-bottom:10px;">
                    الوضعية الإدماجية: ({integ['points']} نقاط) - {integ['topic']}
                </div>
                <div style="padding-right:20px;line-height:1.8;">{integ['question']}</div>
            </div>'''
        
        # الإجابات
        html += '<hr style="border:2px dashed #000;margin:30px 0;"><div style="background:#f8f9fa;padding:20px;"><div style="font-weight:bold;font-size:1.2em;text-align:center;margin-bottom:15px;">الإجابة النموذجية وسلّم التنقيط</div>'
        for ex in exam['exercises']:
            if ex.get('solution'):
                html += f'<div style="margin-bottom:15px;"><strong>التمرين {ex["number"]}:</strong><br>{ex["solution"]}</div>'
        if exam['integration'] and exam['integration'].get('solution'):
            html += f'<div><strong>الوضعية الإدماجية:</strong><br>{exam["integration"]["solution"]}</div>'
        html += '</div></div>'
                return html

    def generate_smart_question(self, data: Dict) -> Optional[Dict]:
        """توليد سؤال واحد ذكي بالتلميح"""
        subject = data['subject']
        grade = data['grade']
        hint = data.get('hint', '')
        
        # محاولة من البنك أولاً
        questions = self.bank.search(subject=subject, grade=grade, hint=hint)
        if questions:
            base = random.choice(questions)
            varied = self.bank.create_variation(base)
            return {
                'success': True,
                'question': varied['text'],
                'answer': varied.get('solution', ''),
                'skills': varied.get('skills_tested', []),
                'variation': varied.get('variation_note', 'تم التنويع تلقائياً'),
                'source': 'bank'
            }
        
        # إذا فشل، نستخدم الذكاء الاصطناعي
        if self.ai:
            try:
                prompt = f"""أنت أستاذ خبير في {subject}. أنشئ سؤالاً واحداً فريداً للمستوى {grade}.
التلميح: {hint}.
أعد النتيجة بصيغة JSON فقط:
{{"question_text": "نص السؤال", "answer_key": "الإجابة", "skills_tested": ["مهارة1"], "variation_note": "كيف غيّرت السؤال"}}"""
                
                completion = self.ai.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "أنت خبير أسئلة. تجيب بـ JSON فقط."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.9
                )
                
                result = json.loads(completion.choices[0].message.content)
                
                # حفظ في البنك
                self.bank.add_question({
                    'subject': subject, 'grade': grade,
                    'text': result['question_text'],
                    'solution': result['answer_key'],
                    'skills_tested': result['skills_tested'],
                    'hint': hint,
                    'source': 'ai-generated'                })
                
                return {'success': True, **result, 'source': 'ai'}
            except Exception as e:
                print(f"❌ Smart Q Error: {e}")
        
        return None

# ============================================================
# 5. تهيئة المكونات
# ============================================================
question_bank = QuestionBank()
exam_generator = ExamGenerator(ai_client, question_bank)

# ============================================================
# 6. نقاط نهاية API
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    return jsonify({
        'success': True,
        'subjects': VALID_SUBJECTS,
        'grades': VALID_GRADES,
        'semesters': VALID_SEMESTERS
    })

@app.route('/api/topics', methods=['GET'])
def get_topics():
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    semester = request.args.get('semester')
    
    if not all([subject, grade]):
        return jsonify({'error': 'المادة والمستوى مطلوبان'}), 400
    
    topics = CURRICULUM_DB.get(subject, {}).get(grade, {}).get(semester if semester else '', [])
    return jsonify({'success': True, 'topics': topics})

@app.route('/api/generate', methods=['POST'])
def generate_exam():
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400
    
    try:
        data = request.json        use_bank = request.args.get('bank', 'true').lower() == 'true'
        
        result = exam_generator.generate_exam(data, use_bank=use_bank)
        
        if result['success']:
            return jsonify(result)
        return jsonify({'error': result.get('error', 'فشل التوليد')}), 500
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_smart', methods=['POST'])
def generate_smart():
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400
    
    try:
        data = request.json
        result = exam_generator.generate_smart_question(data)
        
        if result and result['success']:
            return jsonify(result)
        return jsonify({'error': 'لا توجد أسئلة متاحة'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bank/search', methods=['GET'])
def search_bank():
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    semester = request.args.get('semester')
    hint = request.args.get('hint')
    topic = request.args.get('topic')
    
    results = question_bank.search(
        subject=subject, grade=grade, semester=semester,
        hint=hint, topic=topic
    )
    return jsonify({'success': True, 'count': len(results), 'results': results})

@app.route('/api/bank/stats', methods=['GET'])
def bank_stats():
    return jsonify({'success': True, 'stats': question_bank.get_stats()})

@app.route('/api/bank/export', methods=['GET'])
def export_bank():
    return jsonify({'success': True, **question_bank.export_bank()})
@app.route('/api/bank/import', methods=['POST'])
def import_bank():
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400
    
    data = request.json
    questions = data.get('questions', [])
    count = question_bank.import_questions(questions)
    
    return jsonify({'success': True, 'imported': count})

@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({
        'status': '✅ النظام يعمل',
        'ai_available': ai_client is not None,
        'bank_size': len(question_bank.questions),
        'subjects': len(VALID_SUBJECTS),
        'version': '3.0.0 - Merged Pro',
        'developer': 'youcef .b'
    })

if __name__ == '__main__':
    print("🚀 تشغيل منصة الاختبارات الجزائرية المدمجة...")
    print(f"📊 بنك الأسئلة: {len(question_bank.questions)} سؤال")
    print(f"🧠 الذكاء الاصطناعي: {'✅ متصل' if ai_client else '❌ غير متصل'}")
    print(f"📚 المواد: {len(VALID_SUBJECTS)} | المستويات: {len(VALID_GRADES)}")
    print("🌐 الرابط: http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')
