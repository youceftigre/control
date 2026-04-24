# -*- coding: utf-8 -*-
"""
مولّد الاختبارات التربوية - نظام محسّن
المنهاج الجزائري - التعليم المتوسط
Version 2.0 - Optimized & Enhanced
"""

from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
from functools import lru_cache, wraps
from typing import Dict, List, Tuple, Optional
import os
import traceback
import re
import time
import hashlib
import json

# ============================================================
# CONFIGURATION & INITIALIZATION
# ============================================================

load_dotenv()
api_key = os.getenv('GROQ_API_KEY')

if api_key:
    client = Groq(api_key=api_key)
    print("✅ Groq client initialized successfully")
else:
    client = None
    print("❌ GROQ_API_KEY not found in environment")

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['JSON_AS_ASCII'] = False  # دعم UTF-8

# Cache configuration
CACHE_TIMEOUT = 3600  # 1 hour
cache_store = {}

# ============================================================
# ENHANCED CURRICULUM DATABASE WITH COGNITIVE LEVELS
# ============================================================

CURRICULUM_DB = {
    "الرياضيات": {
        "السنة الأولى متوسط": {
            "الفصل الأول": {
                "topics": ["الأعداد الطبيعية والأعداد العشرية", "العمليات على الأعداد", "الأعداد الأولية والقاسم المشترك الأكبر"],
                "cognitive_levels": {
                    "معرفة": 30,  # نسبة مئوية
                    "فهم": 40,
                    "تطبيق": 20,
                    "تحليل": 10
                },
                "key_competencies": ["الحساب الذهني", "التفكير المنطقي", "حل المسائل"]
            },
            "الفصل الثاني": {
                "topics": ["الكسور", "النسبة والتناسب", "المعادلات من الدرجة الأولى"],
                "cognitive_levels": {"معرفة": 25, "فهم": 35, "تطبيق": 30, "تحليل": 10},
                "key_competencies": ["التناسبية", "المعادلات", "التمثيل البياني"]
            },
            "الفصل الثالث": {
                "topics": ["الزوايا والمستقيمات", "المثلثات", "الدوائر والأقواس"],
                "cognitive_levels": {"معرفة": 30, "فهم": 30, "تطبيق": 25, "تحليل": 15},
                "key_competencies": ["الهندسة المستوية", "البرهان", "الاستدلال الهندسي"]
            }
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": {
                "topics": ["الأعداد الصحيحة والنسبية", "القوى", "الجذور"],
                "cognitive_levels": {"معرفة": 25, "فهم": 35, "تطبيق": 30, "تحليل": 10},
                "key_competencies": ["الحساب على الأعداد النسبية", "القوى والجذور"]
            },
            "الفصل الثاني": {
                "topics": ["المعادلات والمتراجحات من الدرجة الأولى", "الدوال", "الإحصاء"],
                "cognitive_levels": {"معرفة": 20, "فهم": 30, "تطبيق": 35, "تحليل": 15},
                "key_competencies": ["حل المعادلات", "قراءة الجداول", "التمثيل البياني"]
            },
            "الفصل الثالث": {
                "topics": ["الزوايا المتقابلة والمتعامدة", "المتوازيات", "المثلثات المتشابهة", "مبرهنة طاليس"],
                "cognitive_levels": {"معرفة": 25, "فهم": 30, "تطبيق": 30, "تحليل": 15},
                "key_competencies": ["التشابه", "البرهان الهندسي", "طاليس"]
            }
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": {
                "topics": ["الأعداد النسبية", "العمليات على الأعداد النسبية", "الأعداد الحقيقية"],
                "cognitive_levels": {"معرفة": 20, "فهم": 30, "تطبيق": 35, "تحليل": 15},
                "key_competencies": ["الأعداد الحقيقية", "الجذور التربيعية"]
            },
            "الفصل الثاني": {
                "topics": ["المعادلات والمتراجحات", "الدوال التآلفية", "الإحصاء"],
                "cognitive_levels": {"معرفة": 20, "فهم": 30, "تطبيق": 35, "تحليل": 15},
                "key_competencies": ["الدوال", "الإحصاء الوصفي", "التمثيلات"]
            },
            "الفصل الثالث": {
                "topics": ["النسب المثلثية", "المتجهات", "الهندسة في الفضاء"],
                "cognitive_levels": {"معرفة": 25, "فهم": 30, "تطبيق": 30, "تحليل": 15},
                "key_competencies": ["المثلثات القائمة", "الفضاء الهندسي"]
            }
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": {
                "topics": ["الأعداد الحقيقية والمعادلات من الدرجة الثانية", "الدوال", "التغيرات"],
                "cognitive_levels": {"معرفة": 15, "فهم": 30, "تطبيق": 40, "تحليل": 15},
                "key_competencies": ["المعادلات التربيعية", "دراسة الدوال"]
            },
            "الفصل الثاني": {
                "topics": ["الإحصاء", "الدوال التآلفية والتآلفية العكسية", "الدوال التربيعية"],
                "cognitive_levels": {"معرفة": 15, "فهم": 25, "تطبيق": 40, "تحليل": 20},
                "key_competencies": ["الإحصاء المتقدم", "دراسة الدوال التربيعية"]
            },
            "الفصل الثالث": {
                "topics": ["الهندسة في الفضاء", "المساحات والحجوم", "التشابه والتكافؤ"],
                "cognitive_levels": {"معرفة": 20, "فهم": 25, "تطبيق": 35, "تحليل": 20},
                "key_competencies": ["الحساب في الفضاء", "المساحات والحجوم"]
            }
        }
    },
    # يمكن إضافة باقي المواد بنفس البنية المحسّنة
}

# Simplified structure for other subjects (يمكن توسيعها)
CURRICULUM_DB.update({
    "اللغة العربية": {
        "السنة الأولى متوسط": {
            "الفصل الأول": {
                "topics": ["النص القرائي: الوطن والمواطنة", "الإملاء والتعبير", "النحو: المبتدأ والخبر"],
                "cognitive_levels": {"معرفة": 30, "فهم": 40, "تطبيق": 20, "إبداع": 10},
                "key_competencies": ["القراءة الواعية", "التحليل اللغوي", "التعبير الكتابي"]
            }
        }
    }
})

# ============================================================
# VALIDATION & CONSTANTS
# ============================================================

VALID_SUBJECTS = list(CURRICULUM_DB.keys())
VALID_GRADES = ["السنة الأولى متوسط", "السنة الثانية متوسط", "السنة الثالثة متوسط", "السنة الرابعة متوسط"]
VALID_SEMESTERS = ["الفصل الأول", "الفصل الثاني", "الفصل الثالث"]

# Enhanced question types with cognitive levels
QUESTION_TYPES_TAXONOMY = {
    "الرياضيات": {
        "معرفة": ["تعريف", "تذكر قاعدة", "تحديد خاصية"],
        "فهم": ["شرح", "تفسير", "إعطاء مثال"],
        "تطبيق": ["حساب", "حل معادلة", "إنجاز بناء هندسي"],
        "تحليل": ["مقارنة", "تصنيف", "استنتاج"],
        "تركيب": ["وضعية إدماجية", "حل مشكلة مركبة"]
    }
}

# Mark distribution templates
MARK_DISTRIBUTION_TEMPLATES = {
    "standard": {"تمرين1": 6, "تمرين2": 6, "وضعية_إدماجية": 8},
    "advanced": {"تمرين1": 5, "تمرين2": 5, "تمرين3": 4, "وضعية_إدماجية": 6}
}

# ============================================================
# CACHING & PERFORMANCE UTILITIES
# ============================================================

def cache_key(*args, **kwargs) -> str:
    """Generate unique cache key from arguments"""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def timed_cache(timeout: int = CACHE_TIMEOUT):
    """Decorator for caching with timeout"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            if key in cache_store:
                cached_value, timestamp = cache_store[key]
                if time.time() - timestamp < timeout:
                    return cached_value
            
            result = func(*args, **kwargs)
            cache_store[key] = (result, time.time())
            return result
        return wrapper
    return decorator

# ============================================================
# ENHANCED VALIDATION FUNCTIONS
# ============================================================

class ValidationError(Exception):
    """Custom validation error"""
    pass

def validate_request(body: Dict) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    Enhanced validation with detailed feedback
    Returns: (is_valid, error_message, warnings)
    """
    errors = []
    warnings = []
    
    # Required fields
    required_fields = ['subject', 'grade', 'semester', 'schoolYear', 'duration', 'examType']
    missing = [f for f in required_fields if not body.get(f)]
    
    if missing:
        return False, f"الحقول المفقودة: {', '.join(missing)}", None
    
    # Subject validation
    subject = body.get('subject')
    if subject not in VALID_SUBJECTS:
        return False, f"المادة '{subject}' غير صالحة. المواد المتاحة: {', '.join(VALID_SUBJECTS)}", None
    
    # Grade validation
    grade = body.get('grade')
    if grade not in VALID_GRADES:
        return False, f"المستوى '{grade}' غير صالح", None
    
    # Semester validation
    semester = body.get('semester')
    if semester not in VALID_SEMESTERS:
        return False, f"الفصل '{semester}' غير صالح", None
    
    # Check if curriculum data exists
    if subject not in CURRICULUM_DB:
        return False, f"بيانات المنهاج غير متوفرة للمادة: {subject}", None
    
    if grade not in CURRICULUM_DB[subject]:
        return False, f"بيانات المنهاج غير متوفرة للمستوى: {grade}", None
    
    if semester not in CURRICULUM_DB[subject][grade]:
        warnings.append(f"بيانات الفصل {semester} محدودة، سيتم استخدام البيانات العامة")
    
    # Mark validation
    mark = str(body.get('mark', '20'))
    if mark != '20':
        warnings.append("العلامة المعيارية في الجزائر هي 20/20")
    
    # Types validation
    types = body.get('types', '')
    if isinstance(types, str):
        types = [t.strip() for t in types.split(',') if t.strip()]
    
    # Check for integration task
    has_integration = any('إدماج' in str(t) or 'intégration' in str(t).lower() 
                         or 'integration' in str(t).lower() for t in types)
    
    if not has_integration:
        warnings.append("يُنصح بتضمين وضعية إدماجية لتقييم الكفاءات")
    
    return True, None, warnings if warnings else None

# ============================================================
# CURRICULUM CONTEXT BUILDER (OPTIMIZED)
# ============================================================

@lru_cache(maxsize=128)
def get_curriculum_context(subject: str, grade: str, semester: str = None, topic: str = None) -> str:
    """
    Optimized curriculum context builder with caching
    """
    if subject not in CURRICULUM_DB or grade not in CURRICULUM_DB[subject]:
        return f"⚠️ بيانات غير متوفرة للمادة {subject} - المستوى {grade}"
    
    grade_data = CURRICULUM_DB[subject][grade]
    
    context = f"""
═══════════════════════════════════════════════════════
📚 المادة: {subject} | 📖 المستوى: {grade}
═══════════════════════════════════════════════════════
"""
    
    if semester and semester in grade_data:
        semester_data = grade_data[semester]
        topics = semester_data.get('topics', [])
        cognitive = semester_data.get('cognitive_levels', {})
        competencies = semester_data.get('key_competencies', [])
        
        context += f"""
📅 الفصل الدراسي: {semester}

🎯 المواضيع المقررة:
{chr(10).join(f'   • {topic}' for topic in topics)}

🧠 المستويات المعرفية المستهدفة:
{chr(10).join(f'   • {level}: {percent}%' for level, percent in cognitive.items())}

💡 الكفاءات الأساسية:
{chr(10).join(f'   • {comp}' for comp in competencies)}
"""
    else:
        context += f"\n🗂️ جميع فصول {grade}:\n"
        for sem, data in grade_data.items():
            topics = data.get('topics', [])
            context += f"\n{sem}:\n" + "\n".join(f"   • {t}" for t in topics) + "\n"
    
    if topic:
        context += f"\n🎯 الموضوع المحدد: {topic}\n"
    
    # Subject-specific instructions
    context += f"\n{'═' * 55}\n"
    context += f"⚠️ تعليمات صارمة خاصة بمادة {subject}:\n"
    context += f"{'═' * 55}\n"
    
    subject_rules = {
        "الرياضيات": [
            "✓ أسئلة رياضية بحتة فقط (حساب، جبر، هندسة)",
            "✗ ممنوع أي سياق فيزيائي أو علمي",
            "✓ استخدام رموز رياضية صحيحة",
            "✓ خطوات الحل واضحة ومرقمة"
        ],
        "اللغة العربية": [
            "✓ نصوص عربية فصحى فقط",
            "✗ ممنوع خلط العامية أو لغات أخرى",
            "✓ تركيز على النحو والبلاغة والتعبير",
            "✓ معايير تقييم واضحة للتعبير الكتابي"
        ],
        "اللغة الفرنسية": [
            "✓ Textes en français standard uniquement",
            "✗ Pas d'arabe dans les questions",
            "✓ Grammaire, vocabulaire, expression écrite",
            "✓ Critères d'évaluation clairs"
        ],
        "اللغة الإنجليزية": [
            "✓ Standard English only",
            "✗ No Arabic or French in questions",
            "✓ Focus on grammar, vocabulary, writing",
            "✓ Clear rubrics for marking"
        ]
    }
    
    rules = subject_rules.get(subject, ["✓ التزام صارم بالمنهاج الجزائري"])
    context += "\n".join(rules) + "\n"
    
    return context

# ============================================================
# EXAM STRUCTURE BUILDER (ENHANCED)
# ============================================================

@lru_cache(maxsize=32)
def get_exam_structure(subject: str, difficulty: str = "متوسط") -> str:
    """
    Enhanced exam structure with difficulty adaptation
    """
    
    difficulty_multipliers = {
        "سهل": {"steps": 2, "complexity": "بسيطة"},
        "متوسط": {"steps": 3, "complexity": "متوسطة"},
        "صعب": {"steps": 4, "complexity": "مركبة"}
    }
    
    diff_config = difficulty_multipliers.get(difficulty, difficulty_multipliers["متوسط"])
    
    structures = {
        "الرياضيات": f"""
┌─────────────────────────────────────────────────────┐
│         هيكل الاختبار - الرياضيات ({difficulty})         │
└─────────────────────────────────────────────────────┘

📝 **التمرين الأول: المعرفة والفهم (06 نقاط)**    ├─ سؤال 1: تطبيق مباشر لقاعدة (03 نقاط)
   │  • مثال: حساب، تبسيط، تحويل
   │  • التنقيط: 1.5 + 1.5 نقطة
   └─ سؤال 2: فهم وتفسير (03 نقاط)
      • مثال: شرح، برهان بسيط، تعليل
      • التنقيط: 1.5 + 1.5 نقطة

📐 **التمرين الثاني: التطبيق والتحليل (06 نقاط)**    ├─ مسألة {diff_config['complexity']} ({diff_config['steps']} خطوات)
   │  • سياق رياضي واضح
   │  • التنقيط: {' + '.join(['2'] * 3)} نقاط
   └─ يجب أن يدمج مفهومين على الأقل

🎯 **الوضعية الإدماجية: الإبداع والحل (08 نقاط)**    ├─ مشكلة حياتية/تطبيقية
   │  • السياق (1 نقطة)
   │  • الفهم والتحليل (2 نقطة)
   │  • الحل المنطقي ({diff_config['steps']}-{diff_config['steps']+1} خطوات) (4 نقاط)
   └─ العرض والاستنتاج (1 نقطة)

📊 **توزيع الدرجات حسب المستويات المعرفية:**    • المعرفة والتذكر: 20%
   • الفهم والتطبيق: 50%
   • التحليل والتركيب: 30%
""",
        
        "اللغة العربية": f"""
┌─────────────────────────────────────────────────────┐
│        هيكل الاختبار - اللغة العربية ({difficulty})        │
└─────────────────────────────────────────────────────┘

📖 **النص القرائي (06 نقاط)**    ├─ الفهم العام (02 نقطة)
   │  • الفكرة العامة، العنوان المناسب
   ├─ الفهم التفصيلي (02 نقطة)
   │  • استخراج معلومات، شرح كلمات
   └─ الفهم النقدي (02 نقطة)
      • رأي شخصي، استنتاج، تقييم

✍️ **القواعد اللغوية (06 نقاط)**    ├─ النحو (03 نقاط)
   │  • إعراب، تحويل، تصحيح
   ├─ الصرف والإملاء (02 نقطة)
   └─ البلاغة (01 نقطة)

📝 **التعبير الكتابي - الوضعية الإدماجية (08 نقاط)**    ├─ المحتوى والأفكار (03 نقاط)
   ├─ التنظيم والترابط (02 نقطة)
   ├─ اللغة والأسلوب (02 نقطة)
   └─ الإملاء والخط (01 نقطة)

المعايير:
• الالتزام بالموضوع
• تنوع الأفكار وترابطها
• سلامة اللغة والتعبير
• جودة العرض
""",
        
        "اللغة الفرنسية": f"""
┌─────────────────────────────────────────────────────┐
│       Structure - Langue Française ({difficulty})      │
└─────────────────────────────────────────────────────┘

📖 **Compréhension de l'écrit (06 points)**    ├─ Compréhension globale (02 points)
   │  • Idée générale, titre approprié
   ├─ Compréhension détaillée (02 points)
   │  • Informations spécifiques, vocabulaire
   └─ Compréhension critique (02 points)
      • Avis personnel, déduction

✍️ **Fonctionnement de la langue (06 points)**    ├─ Grammaire (03 points)
   │  • Conjugaison, transformation, accord
   ├─ Vocabulaire (02 points)
   └─ Orthographe (01 point)

📝 **Production écrite - Situation d'intégration (08 points)**    ├─ Pertinence et contenu (03 points)
   ├─ Organisation et cohérence (02 points)
   ├─ Correction linguistique (02 points)
   └─ Présentation (01 point)

Critères d'évaluation:
• Respect de la consigne
• Richesse du contenu
• Correction de la langue
• Cohérence textuelle
"""
    }
    
    return structures.get(subject, structures["الرياضيات"])

# ============================================================
# ENHANCED PROMPT BUILDER
# ============================================================

def build_enhanced_prompt(body: Dict) -> str:
    """
    Build optimized prompt with educational standards
    """
    subject = body.get('subject')
    grade = body.get('grade')
    semester = body.get('semester')
    topic = body.get('topic')
    difficulty = body.get('difficulty', 'متوسط')
    exam_type = body.get('examType', 'اختبار')
    
    curriculum_context = get_curriculum_context(subject, grade, semester, topic)
    exam_structure = get_exam_structure(subject, difficulty)
    
    difficulty_instructions = {
        "سهل": "أسئلة مباشرة، خطوات واضحة، سياقات مألوفة",
        "متوسط": "أسئلة تتطلب تفكيراً، خطوات متعددة، سياقات متنوعة",
        "صعب": "أسئلة مركبة، تحليل عميق، سياقات جديدة تتطلب إبداعاً"
    }
    
    # Language-specific instructions
    lang_instructions = {
        "اللغة الفرنسية": {
            "content_lang": "français",
            "instruction": "Toutes les questions DOIVENT être en français",
            "forbidden": "INTERDIT: utiliser l'arabe dans les questions"
        },
        "اللغة الإنجليزية": {
            "content_lang": "English",
            "instruction": "All questions MUST be in English",
            "forbidden": "FORBIDDEN: use of Arabic or French"
        }
    }.get(subject, {
        "content_lang": "العربية الفصحى",
        "instruction": "جميع الأسئلة بالعربية الفصحى",
        "forbidden": "ممنوع: استخدام العامية أو لغات أخرى"
    })
    
    prompt = f"""
╔══════════════════════════════════════════════════════════════╗
║  أنت خبير تربوي ومفتش تعليم جزائري متخصص في {subject}      ║
║  مهمتك: إنشاء {exam_type} احترافي معياري                    ║
╚══════════════════════════════════════════════════════════════╝

{curriculum_context}

═══════════════════════════════════════════════════════════════
📋 معلومات الاختبار
═══════════════════════════════════════════════════════════════
• نوع الاختبار: {exam_type}
• المدة الزمنية: {body.get('duration')}
• السنة الدراسية: {body.get('schoolYear')}
• مستوى الصعوبة: {difficulty} - {difficulty_instructions[difficulty]}
• العلامة الكاملة: 20/20 (معيار ثابت)
• الموضوع المحدد: {topic or 'حسب المنهاج'}
• تعليمات خاصة: {body.get('extra') or 'لا توجد'}

═══════════════════════════════════════════════════════════════
🎯 هيكل الاختبار الإلزامي
═══════════════════════════════════════════════════════════════
{exam_structure}

═══════════════════════════════════════════════════════════════
🚫 محظورات صارمة
═══════════════════════════════════════════════════════════════
1. **ممنوع منعاً باتاً** : ذكر أي مادة دراسية أخرى غير {subject}
2. **ممنوع** : أسئلة خارج المنهاج المحدد أعلاه
3. **ممنوع** : خلط مواضيع من مستويات أو فصول أخرى
4. **ممنوع** : وضع الكود في ```html أو أي markdown
5. **ممنوع** : عناصر HTML تفاعلية: <input>, <button>, <form>, <script>
6. **ممنوع** : {lang_instructions['forbidden'
