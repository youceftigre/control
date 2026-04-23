# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import traceback
import google.generativeai as genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

# طباعة أول 6 أحرف من المفتاح للتأكد من أنه محمل (آمن)
if api_key:
    print(f"✅ تم تحميل المفتاح: {api_key[:6]}...")
    genai.configure(api_key=api_key)
else:
    print("❌ لم يتم العثور على GEMINI_API_KEY في متغيرات البيئة")

app = Flask(__name__, static_folder='.', static_url_path='')

# اختيار النموذج بشكل آمن
def load_model():
    try:
        # استخدام اسم النموذج الكامل من الصورة السابقة
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        print("✅ تم تحميل النموذج بنجاح")
        return model
    except Exception as e:
        print(f"❌ فشل تحميل النموذج: {e}")
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
        return jsonify({'error': '🔑 مفتاح API غير موجود. أضف GEMINI_API_KEY في إعدادات Render.'}), 500

    if model is None:
        return jsonify({'error': '🧠 فشل تحميل نموذج الذكاء الاصطناعي. راجع السجلات.'}), 500

    try:
        body = request.get_json()
        prompt = build_prompt(body)

        print("🚀 إرسال الطلب إلى Gemini...")
        response = model.generate_content(prompt)
        print("✅ تم استلام الرد من Gemini")

        return jsonify({'result': response.text})

    except Exception as e:
        # تجميع تفاصيل الخطأ لعرضها للمستخدم
        error_details = traceback.format_exc()
        print("❌❌❌ خطأ في /api/generate:")
        print(error_details)

        # إرسال الخطأ للمتصفح ليساعد في التشخيص
        return jsonify({
            'error': f'فشل التوليد: {str(e)}',
            'details': error_details.split('\n')[-2]  # آخر سطر مفيد
        }), 500

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
