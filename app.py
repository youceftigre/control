# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
import os
import traceback
import random
import json
import datetime

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
# بنك الأسئلة المحلي (Local Question Bank)
# ============================================================
# في البداية يكون فارغاً، ويمتلئ كلما ولدت أسئلة جديدة
QUESTION_BANK_FILE = 'question_bank.json'

def load_bank():
    if os.path.exists(QUESTION_BANK_FILE):
        with open(QUESTION_BANK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_to_bank(new_questions):
    bank = load_bank()
    # إضافة تاريخ التوليد لكل سؤال
    for q in new_questions:
        q['generated_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        q['id'] = random.randint(10000, 99999)
    bank.extend(new_questions)
    with open(QUESTION_BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)
    print(f"✅ تم حفظ {len(new_questions)} أسئلة جديدة في البنك.")

# ============================================================
# قاعدة البيانات المنهجية (نفس السابقة ولكن مختصرة للعرض)
# ============================================================
CURRICULUM_DB = {
    "الرياضيات": {        "السنة الرابعة متوسط": {
            "الفصل الأول": ["الأعداد الحقيقية", "الجذور", "المعادلات من الدرجة الثانية"],
            "الفصل الثاني": ["الدوال الخطية والتآلفية", "الإحصاء", "هندسة الفضاء"]
        }
    },
    "اللغة العربية": {
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["النص القرائي: القيم الإنسانية", "البلاغة: التشبيه والاستعارة", "النحو: المبتدأ والخبر"]
        }
    }
    # ... يمكن إضافة باقي المواد كما في الكود السابق
}

VALID_SUBJECTS = list(CURRICULUM_DB.keys())
VALID_GRADES = ["السنة الأولى متوسط", "السنة الثانية متوسط", "السنة الثالثة متوسط", "السنة الرابعة متوسط"]
VALID_SEMESTERS = ["الفصل الأول", "الفصل الثاني", "الفصل الثالث"]

# ============================================================
# محرك الذكاء الاصطناعي المحسن (The Expert Engine)
# ============================================================

def get_expert_prompt(subject, grade, semester, topic_hint, difficulty, exam_type):
    """
    هذا البرومبت مصمم ليحاكي عقل الأستاذ الخبير.
    يركز على تغيير الأرقام، الأسماء، والسياق لضمان عدم التكرار.
    """
    
    # تحديد سياق المادة بدقة
    subject_context = CURRICULUM_DB.get(subject, {}).get(grade, {}).get(semester, [])
    topics_str = ", ".join(subject_context) if subject_context else "المنهاج العام"

    prompt = f"""
أنت "الأستاذ الخبير" وعضو لجنة صياغة امتحانات شهادة التعليم المتوسط (BEM) في الجزائر. لديك خبرة 20 عاماً في وضع الفروض والاختبارات.

**المهمة:** إنشاء سؤال أو تمرين واحد فريد من نوعه لمادة: {subject}.
**المستوى:** {grade} | **الفصل:** {semester}.
**نوع الاختبار:** {exam_type}.
**مستوى الصعوبة:** {difficulty}.

**التوجيهات الذهبية (يجب الالتزام بها حرفياً):**
1. **محاكاة الواقع:** استرجع أنماط الأسئلة التي ترد في امتحانات السنوات الماضية (2010-2023) من مختلف الولايات (الجزائر العاصمة، وهران، قسنطينة...).
2. **التغيير الجذري:** إذا كان السؤال عن "حساب مساحة حديقة"، اجعله هذه المرة عن "حساب مساحة ملعب كرة قدم" أو "قطعة أرض فلاحية". غيّر الأرقام تماماً.
3. **التلميح المقدم:** المستخدم أعطى تلميحاً: "{topic_hint}". ركز السؤال حول هذا المفهوم ولكن بربطه بمفهوم آخر من المنهاج (تكامل المعارف).
4. **اللغة:** استخدم لغة عربية أكاديمية رصينة (أو اللغة المناسبة للمادة).
5. **التنسيق:** أعطني النتيجة بصيغة JSON فقط تحتوي على:
   - `question_text`: نص السؤال كاملاً.
   - `answer_key`: الإجابة النموذجية التفصيلية مع سلم التنقيط.
   - `skills_tested`: المهارات التي يقيسها السؤال (مثال: التحليل، التطبيق، الحفظ).
   - `variation_note`: ماذا غيرت في هذا السؤال مقارنة بالنمط التقليدي؟
**مثال على التغيير المطلوب:**
- النمط التقليدي: "احسب PGCD للعددين 120 و 80."
- نسختك الجديدة: "لدى تاجر 120 قلماً أحمر و 80 قلماً أزرق. يريد توزيعها في علب متساوية دون بقية. ما هو أكبر عدد من العلب يمكنه تحضيرها؟ وما محتوى كل علبة؟"

ابدأ الآن بتوليد السؤال بناءً على التلميح: "{topic_hint}"
"""
    return prompt

@app.route('/api/generate_smart_question', methods=['POST'])
def generate_smart_question():
    """توليد سؤال ذكي بناءً على تلميح وحفظه في البنك"""
    if not client:
        return jsonify({'error': 'API Key missing'}), 500

    data = request.json
    subject = data.get('subject')
    grade = data.get('grade')
    semester = data.get('semester')
    hint = data.get('hint', '') # التلميح
    difficulty = data.get('difficulty', 'متوسط')
    exam_type = data.get('exam_type', 'فرض')

    try:
        prompt = get_expert_prompt(subject, grade, semester, hint, difficulty, exam_type)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "أنت خبير تربوي جزائري. تجيب فقط بصيغة JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.9, # إبداع عالي
            response_format={"type": "json_object"} # إجبار النموذج على إخراج JSON
        )

        result_json = json.loads(chat_completion.choices[0].message.content)
        
        # إضافة معلومات إضافية للسؤال قبل الحفظ
        question_entry = {
            "subject": subject,
            "grade": grade,
            "semester": semester,
            "hint_used": hint,
            "data": result_json
        }

        # الحفظ في البنك
        save_to_bank([question_entry])

        return jsonify({            "success": True,
            "question": result_json
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/bank/search', methods=['GET'])
def search_bank():
    """البحث في بنك الأسئلة المتراكم"""
    query = request.args.get('q', '').lower()
    subject = request.args.get('subject', '')
    
    bank = load_bank()
    results = []
    
    for item in bank:
        # فلترة حسب المادة إذا وجدت
        if subject and item['subject'] != subject:
            continue
            
        # بحث في نص السؤال أو التلميح
        q_text = item['data'].get('question_text', '').lower()
        hint = item.get('hint_used', '').lower()
        
        if query in q_text or query in hint:
            results.append(item)
            
    # ترتيب عشوائي لإظهار تنوع النتائج
    random.shuffle(results)
    return jsonify({"count": len(results), "questions": results[:10]}) # نرجع آخر 10 نتائج مطابقة

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
