from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import google.generativeai as genai

# تحميل متغيرات البيئة
load_dotenv()

# الحصول على مفتاح API
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

# تهيئة Gemini
if api_key:
    genai.configure(api_key=api_key)

# إنشاء تطبيق Flask
app = Flask(__name__, static_folder='.', static_url_path='')

def build_prompt(body: dict) -> str:
    """بناء الـprompt لـGemini."""
    return f"""أنت خبير تربوي في المنهاج الجزائري.
أنشئ {body.get('examType', 'اختبار')}اً كاملاً باللغة العربية مع الإجابة النموذجية.

المادة: {body.get('subject', 'غير محدد')}
المستوى: {body.get('grade', 'غير محدد')}
السنة الدراسية: {body.get('schoolYear', 'غير محدد')}
المدة: {body.get('duration', '60 دقيقة')}
العلامة: {body.get('mark', '20')}
الموضوع: {body.get('topic', 'غير محدد')}
أنواع الأسئلة: {body.get('types', 'متنوعة')}
مستوى الصعوبة: {body.get('difficulty', 'متوسط')}
تعليمات إضافية: {body.get('extra', 'لا توجد')}

الشروط:
- التزم بمعايير وزارة التربية الوطنية الجزائرية.
- نسّق الاختبار احترافياً (تمرين أول، ثاني، وضعية إدماجية).
- أضف الإجابة النموذجية وسلم التنقيط في النهاية.
- استخدم HTML بسيط (<h3> للعناوين، <br> للأسطر الجديدة).
"""

@app.route('/api/generate', methods=['POST'])
def generate():
    """توليد الاختبار."""
    if not request.is_json:
        return jsonify({'error': 'البيانات يجب أن تكون JSON'}), 400

    body = request.get_json(force=True) or {}
    
    if not api_key:
        return jsonify({'error': 'مفتاح API غير متوفر. أضفه في Render dashboard.'}), 500

    try:
        prompt = build_prompt(body)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return jsonify({'result': response.text})
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return jsonify({'error': 'خطأ في التوليد. تحقق من المفتاح.'}), 500

@app.route('/', methods=['GET'])
def home():
    """الصفحة الرئيسية."""
    try:
        return send_from_directory('.', 'index.html')
    except FileNotFoundError:
        return '''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>منشئ الاختبارات الجزائرية</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f7fa; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
                button { background: #0f9d58; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
                button:hover { background: #0d7a43; }
                #output { margin-top: 20px; padding: 20px; background: white; border-radius: 5px; white-space: pre-wrap; border: 1px solid #ddd; }
                h1 { text-align: center; color: #333; }
            </style>
        </head>
        <body>
            <h1>🧠 منشئ الاختبارات الجزائرية - Gemini</h1>
            <form id="examForm">
                <div class="form-group">
                    <label>المادة:</label>
                    <input type="text" id="subject" value="الرياضيات" required>
                </div>
                <div class="form-group">
                    <label>المستوى:</label>
                    <input type="text" id="grade" value="الثالثة متوسط" required>
                </div>
                <div class="form-group">
                    <label>الموضوع:</label>
                    <input type="text" id="topic" value="المعادلات" required>
                </div>
                <div class="form-group">
                    <label>نوع الاختبار:</label>
                    <input type="text" id="examType" value="اختبار" placeholder="اختبار، تقييم، وضعية...">
                </div>
                <div class="form-group">
                    <label>المدة:</label>
                    <input type="text" id="duration" value="60 دقيقة">
                </div>
                <div class="form-group">
                    <label>العلامة:</label>
                    <input type="text" id="mark" value="20">
                </div>
                <button type="button" onclick="generateExam()">توليد الاختبار</button>
            </form>
            <div id="output">اضغط "توليد الاختبار" للحصول على الاختبار مع الإجابات...</div>

            <script>
                async function generateExam() {
                    const payload = {
                        subject: document.getElementById('subject').value,
                        grade: document.getElementById('grade').value,
                        topic: document.getElementById('topic').value,
                        examType: document.getElementById('examType').value,
                        duration: document.getElementById('duration').value,
                        mark: document.getElementById('mark').value
                    };
                    const output = document.getElementById('output');
                    output.innerHTML = 'جاري التوليد...';
                    try {
                        const response = await fetch('/api/generate', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(payload)
                        });
                        const data = await response.json();
                        if (data.result) {
                            output.innerHTML = data.result;
                        } else {
                            output.innerHTML = 'خطأ: ' + JSON.stringify(data.error);
                        }
                    } catch (e) {
                        output.innerHTML = 'خطأ في الاتصال: ' + e.message;
                    }
                }
            </script>
        </body>
        </html>
        ''', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
