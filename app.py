# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import google.generativeai as genai      # ✅ هذا هو الصحيح

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if api_key:
    genai.configure(api_key=api_key)

app = Flask(__name__, static_folder='.', static_url_path='')

def build_prompt(body: dict) -> str:
    return f"""أنت خبير تربوي في المنهاج الجزائري.
أنشئ {body.get('examType', 'اختبار')}اً كاملاً باللغة العربية مع الإجابة النموذجية.

المادة: {body.get('subject')}
المستوى: {body.get('grade')}
السنة الدراسية: {body.get('schoolYear')}
المدة: {body.get('duration')}
العلامة: {body.get('mark')}
الموضوع: {body.get('topic') or 'غير محدد'}
أنواع الأسئلة: {body.get('types')}
مستوى الصعوبة: {body.get('difficulty')}
تعليمات إضافية: {body.get('extra') or 'لا توجد'}

الشروط:
- التزم بمعايير وزارة التربية الوطنية الجزائرية.
- نسق الاختبار بشكل احترافي (تمرين أول, تمرين ثاني, وضعية إدماجية).
- أضف الإجابة النموذجية وسلم التنقيط في نهاية الملف.
- استخدم تنسيق HTML بسيط (مثل <h3> للعناوين و <br> للسطر الجديد) لضمان العرض الجميل.
"""

@app.route('/api/generate', methods=['POST'])
def generate():
    if not request.is_json:
        return jsonify({'error': 'يجب إرسال البيانات بصيغة JSON'}), 400
    if not api_key:
        return jsonify({'error': 'مفتاح API غير متوفر'}), 500
    try:
        body = request.get_json()
        prompt = build_prompt(body)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return jsonify({'result': response.text})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'خطأ في الخادم'}), 500

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
