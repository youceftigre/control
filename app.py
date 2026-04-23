# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
from dotenv import load_dotenv
import os
import traceback

# تحميل متغيرات البيئة
load_dotenv()
api_key = os.getenv('DEEPSEEK_API_KEY') # استخدم اسم متغير جديد

# إعداد عميل OpenAI للعمل مع DeepSeek
if api_key:
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com" # نقطة نهاية DeepSeek
    )
    print("✅ تم إعداد عميل DeepSeek بنجاح.")
else:
    client = None
    print("❌ لم يتم العثور على DEEPSEEK_API_KEY في متغيرات البيئة.")

app = Flask(__name__, static_folder='.', static_url_path='')

def build_prompt(body: dict) -> str:
    # دالة بناء النص الموجه (prompt) تبقى كما هي تماماً
    """Build the prompt for DeepSeek."""
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
    if client is None:
        return jsonify({'error': 'لم يتم إعداد عميل DeepSeek. تأكد من مفتاح API.'}), 500
    try:
        body = request.get_json()
        prompt = build_prompt(body)
        
        print("🚀 إرسال الطلب إلى DeepSeek...")
        # استخدام واجهة OpenAI البرمجية مع نموذج DeepSeek
        response = client.chat.completions.create(
            model="deepseek-chat", # أو "deepseek-reasoner" للمهام المعقدة
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4096 # حد أقصى مناسب للاختبارات الطويلة
        )
        print("✅ تم استلام الرد من DeepSeek")
        
        generated_text = response.choices[0].message.content
        return jsonify({'result': generated_text})

    except Exception as e:
        error_details = traceback.format_exc()
        print("❌❌❌ خطأ في /api/generate:")
        print(error_details)
        return jsonify({'error': f'فشل التوليد: {str(e)}', 'details': error_details.split('\n')[-2]}), 500

@app.route('/', methods=['GET'])
def home():
    """عرض صفحة الواجهة الرئيسية."""
    return send_from_directory('.', 'index.html')

@app.route('/test')
def test():
    """مسار تشخيصي لاختبار اتصال DeepSeek"""
    if not api_key:
        return "❌ مفتاح API غير موجود (DEEPSEEK_API_KEY غير مضبوط في Render)", 500
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "قل مرحبا بالعربية"}
            ],
            max_tokens=100
        )
        return f"✅ الاتصال بـ DeepSeek يعمل بنجاح! الرد: {response.choices[0].message.content}"
    except Exception as e:
        return f"❌ فشل استدعاء DeepSeek:\n{str(e)}\n\nالتفاصيل:\n{traceback.format_exc()}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
