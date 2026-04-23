# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import traceback
import google.generativeai as genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

print(f"🔑 API Key loaded: {bool(api_key)}")
if api_key:
    genai.configure(api_key=api_key)

app = Flask(__name__, static_folder='.', static_url_path='')

def load_model():
    try:
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        print("✅ Model loaded")
        return model
    except Exception as e:
        print(f"❌ Model load failed: {e}")
        return None

model = load_model()

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
        return jsonify({'error': 'مفتاح API غير موجود'}), 500
    if model is None:
        return jsonify({'error': 'فشل تحميل النموذج'}), 500
    try:
        body = request.get_json()
        prompt = build_prompt(body)
        response = model.generate_content(prompt)
        return jsonify({'result': response.text})
    except Exception as e:
        error_details = traceback.format_exc()
        print(error_details)
        return jsonify({'error': f'فشل التوليد: {str(e)}', 'details': error_details.split('\n')[-2]}), 500

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# 🩺 نقطة الفحص الجديدة
@app.route('/test')
def test():
    """مسار تشخيصي يعرض سبب فشل Gemini API في نص مباشر"""
    if not api_key:
        return "❌ مفتاح API غير موجود (GEMINI_API_KEY غير مضبوط في Render)", 500
    if model is None:
        return "❌ فشل تحميل نموذج Gemini (model is None)", 500
    try:
        response = model.generate_content("قل مرحبا بالعربية")
        return f"✅ النموذج يعمل بنجاح! الرد: {response.text}"
    except Exception as e:
        return f"❌ فشل استدعاء Gemini:\n{str(e)}\n\nالتفاصيل:\n{traceback.format_exc()}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
