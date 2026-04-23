from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# الحصول على مفتاح API
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY غير موجود في ملف .env')

# تهيئة مكتبة Gemini
genai.configure(api_key=api_key)

# إنشاء تطبيق Flask
app = Flask(__name__)


def build_prompt(body: dict) -> str:
    """
    بناء النص الموجه (prompt) لإرساله إلى نموذج Gemini.
    """
    return f"""أنت خبير تربوي.
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
- اجعل الأسئلة مناسبة للمنهاج الجزائري.
- لا تخرج عن مستوى التلاميذ.
- أضف الإجابات الصحيحة في النهاية.
- أضف التصحيح النموذجي لكل سؤال."""


@app.route('/api/generate', methods=['POST'])
def generate():
    """
    نقطة نهاية لإنشاء اختبار باستخدام Gemini.
    تتوقع JSON يحتوي على معلومات الاختبار.
    """
    # التحقق من أن الطلب يرسل JSON صحيحاً
    if not request.is_json:
        return jsonify({'error': 'يجب إرسال البيانات بصيغة JSON'}), 400

    try:
        body = request.get_json()
        if not body:
            return jsonify({'error': 'جسم الطلب فارغ'}), 400

        # بناء الموجه
        prompt = build_prompt(body)

        # استدعاء نموذج Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)

        return jsonify({'result': response.text})

    except Exception as e:
        # تسجيل الخطأ في وحدة التحكم (لأغراض التطوير)
        print(f"❌ خطأ أثناء إنشاء المحتوى: {str(e)}")
        return jsonify({'error': 'حدث خطأ أثناء معالجة الطلب. الرجاء المحاولة لاحقاً.'}), 500


@app.route('/', methods=['GET'])
def home():
    import os
    from flask import send_from_directory
    directory = os.path.dirname(os.path.abspath(__file__))
return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    # تشغيل التطبيق في وضع التطوير
    app.run(debug=True)
