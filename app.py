"""
تطبيق منصة الامتحانات الجزائرية الشاملة
Flask + Groq AI
"""

import os
import json
import logging
from flask import Flask, render_template, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from groq import Groq
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== FLASK APP INIT ==========
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# تحديد المعدل
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# ========== GROQ CLIENT INIT ==========
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None
    logger.warning("⚠️ GROQ_API_KEY غير معرف")

# ========== DATA LOADER ==========
class DataManager:
    """مدير البيانات - تحميل وتخزين البنك"""
    
    def __init__(self):
        self.question_bank = {}
        self.subjects_config = []
        self.load_data()
    
    def load_data(self):
        """تحميل بنك الأسئلة والمواد"""
        try:
            # تحميل بنك الأسئلة
            if os.path.exists('data/questions_full_bank.json'):
                with open('data/questions_full_bank.json', 'r', encoding='utf-8') as f:
                    self.question_bank = json.load(f)
                logger.info(f"✅ تم تحميل {len(self.question_bank)} مادة")
            else:
                logger.warning("⚠️ ملف بنك الأسئلة غير موجود")
            
            # تحميل إعدادات المواد
            if os.path.exists('data/subjects_config.json'):
                with open('data/subjects_config.json', 'r', encoding='utf-8') as f:
                    self.subjects_config = json.load(f)
                logger.info(f"✅ تم تحميل {len(self.subjects_config)} مادة")
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل البيانات: {e}")
    
    def get_questions_by_filter(self, subject, grade, topic=None, difficulty=None, limit=5):
        """اختيار أسئلة من البنك بناءً على المعايير"""
        questions = []
        
        if subject not in self.question_bank:
            return questions
        
        if grade not in self.question_bank[subject]:
            return questions
        
        # جمع الأسئلة من جميع الفصول
        for chapter, chapter_questions in self.question_bank[subject][grade].items():
            if topic and topic not in chapter:
                continue
            
            for q in chapter_questions:
                if difficulty and q.get('difficulty') != difficulty:
                    continue
                questions.append(q)
        
        # اختيار تنوعي من الأنواع
        selected = []
        types = ['mcq', 'truefalse', 'essay', 'application', 'problem']
        
        for qtype in types:
            matching = [q for q in questions if q.get('type') == qtype]
            if matching:
                selected.append(matching[0])
        
        # إضافة أسئلة إضافية إذا لزم الأمر
        while len(selected) < limit and questions:
            q = questions.pop(0)
            if q not in selected:
                selected.append(q)
        
        return selected[:limit]

# ========== GROQ GENERATOR ==========
class ExamGenerator:
    """مولد الأسئلة باستخدام Groq AI"""
    
    def __init__(self, client):
        self.client = client
    
    def generate_questions(self, subject, grade, semester, exam_type, topic, difficulty, count=5):
        """توليد أسئلة باستخدام Groq AI"""
        
        if not self.client:
            return {
                'error': 'خدمة الذكاء الاصطناعي غير متاحة حالياً'
            }
        
        prompt = f"""
أنت معلم جزائري متخصص في {subject} للمستوى {grade}.
قم بإنشاء {count} أسئلة امتحان بمستوى صعوبة {difficulty} للفصل {semester}.

المتطلبات:
- الموضوع: {topic if topic else 'جميع وحدات المادة'}
- نوع الامتحان: {exam_type}
- اللغة: اللغة العربية الفصحى
- الصيغة: JSON بالضبط

الصيغة المطلوبة (JSON):
{{
  "questions": [
    {{
      "id": 1,
      "type": "mcq|truefalse|essay|application",
      "text": "نص السؤال",
      "points": 2,
      "difficulty": 1|2|3,
      "options": ["خيار أ", "خيار ب", "خيار ج", "خيار د"],
      "answer": "الإجابة الصحيحة"
    }}
  ]
}}

أنشئ الأسئلة الآن:
"""
        
        try:
            response = self.client.messages.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2048
            )
            
            # استخراج JSON من الإجابة
            content = response.content[0].text
            
            # محاولة استخراج JSON
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    return data
                else:
                    # إذا لم يجد JSON، أرجع الخطأ
                    return {'error': 'لم يتمكن من توليد أسئلة صحيحة'}
            except json.JSONDecodeError:
                return {'error': 'خطأ في صيغة JSON من الـ AI'}
        
        except Exception as e:
            logger.error(f"❌ خطأ في Groq: {e}")
            return {'error': str(e)}

# ========== INIT MANAGERS ==========
data_manager = DataManager()
exam_generator = ExamGenerator(groq_client)

# ========== ROUTES ==========

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/api/questions')
def get_questions():
    """API - الحصول على بنك الأسئلة"""
    return jsonify(data_manager.question_bank)

@app.route('/api/generate', methods=['POST'])
@limiter.limit("10 per hour")
def generate_exam():
    """API - توليد اختبار باستخدام AI"""
    try:
        data = request.get_json()
        
        # التحقق من المدخلات
        required = ['subject', 'grade', 'semester']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        subject = data.get('subject')
        grade = data.get('grade')
        semester = data.get('semester')
        exam_type = data.get('examType', 'اختبار فصلي')
        topic = data.get('topic', '')
        difficulty = data.get('difficulty', 'متوسط')
        count = 5
        
        # توليد الأسئلة
        result = exam_generator.generate_questions(
            subject, grade, semester, exam_type, topic, difficulty, count
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"❌ خطأ في التوليد: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/filter-bank', methods=['POST'])
def filter_bank():
    """API - تصفية بنك الأسئلة"""
    try:
        filters = request.get_json()
        
        subject = filters.get('subject')
        grade = filters.get('grade')
        topic = filters.get('topic')
        
        questions = data_manager.get_questions_by_filter(
            subject, grade, topic, limit=10
        )
        
        return jsonify({'questions': questions})
    
    except Exception as e:
        logger.error(f"❌ خطأ في التصفية: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """API - احصائيات بنك الأسئلة"""
    try:
        stats = {
            'total_questions': 0,
            'by_subject': {},
            'by_level': {},
            'by_type': {},
            'by_difficulty': {1: 0, 2: 0, 3: 0}
        }
        
        for subject, grades in data_manager.question_bank.items():
            stats['by_subject'][subject] = 0
            
            for grade, chapters in grades.items():
                # تحديد المرحلة
                if 'ابتدائي' in grade:
                    level = 'ابتدائي'
                elif 'متوسط' in grade:
                    level = 'متوسط'
                else:
                    level = 'ثانوي'
                
                stats['by_level'][level] = stats['by_level'].get(level, 0)
                
                for chapter, questions in chapters.items():
                    for q in questions:
                        stats['total_questions'] += 1
                        stats['by_subject'][subject] += 1
                        stats['by_level'][level] += 1
                        
                        qtype = q.get('type', 'mcq')
                        stats['by_type'][qtype] = stats['by_type'].get(qtype, 0) + 1
                        
                        diff = q.get('difficulty', 2)
                        if diff in stats['by_difficulty']:
                            stats['by_difficulty'][diff] += 1
        
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"❌ خطأ في الإحصائيات: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """فحص صحة التطبيق"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'groq_available': groq_client is not None,
        'questions_loaded': len(data_manager.question_bank) > 0
    })

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Too many requests'}), 429

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ========== MAIN ==========

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 بدء التطبيق على المنفذ {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
