# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
import os
import traceback

load_dotenv()
api_key = os.getenv('GROQ_API_KEY')

if api_key:
    client = Groq(api_key=api_key)
    print("✅ Groq client ready")
else:
    client = None

app = Flask(__name__, static_folder='.', static_url_path='')

def build_prompt(body: dict) -> str:
    return f"""أنت خبير تربوي في المنهاج الجزائري لتوليد اختبارات الرياضيات. قم بإنشاء {body.get('examType', 'اختبار')} كامل واحترافي باللغة العربية مع **الإجابة النموذجية وسلّم التنقيط** في نهاية الاختبار.

المادة: {body.get('subject')}
المستوى: {body.get('grade')}
السنة الدراسية: {body.get('schoolYear')}
المدة: {body.get('duration')}
العلامة: {body.get('mark')}
الموضوع: {body.get('topic') or 'غير محدد'}
أنواع الأسئلة: {body.get('types')}
مستوى الصعوبة: {body.get('difficulty')}
تعليمات إضافية: {body.get('extra') or 'لا توجد'}

**الهيكل المطلوب (يجب الالتزام به):**
1. **الترويسة**: "الجمهورية الجزائرية الديمقراطية الشعبية" بخط كبير، ثم "وزارة التربية الوطنية" متبوعة بالمستوى والمادة.
2. **التمرين الأول (06 نقاط)**: سؤال أو سؤالين حسابيين مع توزيع النقاط الجزئية.
3. **التمرين الثاني (06 نقاط)**: مسألة رياضية بسيطة مع توزيع نقاط.
4. **الوضعية الإدماجية (08 نقاط)**: مسألة حياتية مركبة تتطلب خطوات.
5. **الإجابة النموذجية وسلّم التنقيط**: اذكر الإجابة الصحيحة لكل سؤال مع توزيع الدرجات.

**شروط التنسيق المهمة جداً:**
- استخدم HTML فقط. لا تضع الكود داخل ```html أو أي علامات markdown.
- لا تستخدم <input>, <button>, <form>, <script>.
- استخدم <div class="header"> للترويسة، <h2> للعناوين، <p> للفقرات، <ol>/<li> للتمارين.
- ضع الدرجات بين قوسين بعد كل فقرة، مثال: <p><strong>1. أحسب ما يلي</strong> (03 نقاط)</p>
- استخدم تصميم احترافي بألوان هادئة (خلفية بيضاء، نص داكن، خط كبير).
"""

@app.route('/api/generate', methods=['POST'])
def generate():
    if not request.is_json:
        return jsonify({'error': 'يجب إرسال البيانات بصيغة JSON'}), 400
    if not api_key:
        return jsonify({'error': 'مفتاح Groq API غير موجود'}), 500
    try:
        body = request.get_json()
        prompt = build_prompt(body)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=4096
        )
        result = chat_completion.choices[0].message.content
        return jsonify({'result': result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'فشل التوليد: {str(e)}'}), 500

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/test')
def test():
    if not api_key:
        return "❌ مفتاح Groq API غير موجود", 500
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "قل مرحبا بالعربية"}],
            model="llama-3.1-8b-instant",
            max_tokens=50
        )
        return f"✅ Groq يعمل: {chat_completion.choices[0].message.content}"
    except Exception as e:
        return f"❌ فشل: {traceback.format_exc()}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
