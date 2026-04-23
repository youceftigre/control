from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import traceback
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

app = Flask(__name__, static_folder='.', static_url_path='')

def build_prompt(body=None):
    body = body or {}
    exam_type = body.get('examType', 'اختبار')
    return f"""أنت خبير تربوي في المنهاج الجزائري.
أنشئ {exam_type}اً كاملاً باللغة العربية مع الإجابة النموذجية.

المادة: {body.get('subject', 'غير محدد')}
المستوى: {body.get('grade', 'غير محدد')}
السنة الدراسية: {body.get('schoolYear', 'غير محدد')}
المدة: {body.get('duration', 'غير محدد')}
العلامة: {body.get('mark', 'غير محدد')}
الموضوع: {body.get('topic', 'غير محدد')}
أنواع الأسئلة: {body.get('types', 'غير محدد')}
مستوى الصعوبة: {body.get('difficulty', 'غير محدد')}
تعليمات إضافية: {body.get('extra', 'لا توجد')}

الشروط:
- التزم بمعايير وزارة التربية الوطنية الجزائرية.
- نسق الاختبار بشكل احترافي.
- أضف الإجابة النموذجية وسلم التنقيط في النهاية.
- استخدم HTML بسيط.
"""

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        if not request.is_json:
            return jsonify({'error': 'يجب إرسال البيانات بصيغة JSON'}), 400

        body = request.get_json(silent=True) or {}

        if not client:
            return jsonify({'error': 'مفتاح API غير متوفر'}), 500

        prompt = build_prompt(body)

        resp = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )

        text = getattr(resp, 'text', None)
        if not text:
            return jsonify({'error': 'لم يتم استلام نص من Gemini'}), 500

        return jsonify({'result': text})

    except Exception as e:
        print('GEN_ERROR:', str(e))
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'api_key_loaded': bool(api_key)})

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
