from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import google.generativeai as genai

# تحميل متغيرات البيئة من ملف .env (سيعمل محلياً، أما في Render أضف المفتاح في الإعدادات)
load_dotenv()

# الحصول على مفتاح API
api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')

# تهيئة مكتبة Gemini
if api_key:
    genai.configure(api_key=api_key)

# إنشاء تطبيق Flask
# جعلنا template_folder هو المجلد الحالي لسهولة الوصول لملف index.html
app = Flask(__name__, static_folder='.', static_url_path='')


def build_prompt(body: dict) -> str:
    """بناء النص الموجه (prompt) لنموذج Gemini."""
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
- نسق الاختبار بشكل احترافي (تمرين أول، تمرين ثاني، وضعية إدماجية).
- أضف الإجابة النموذجية وسلم التنقيط في نهاية الملف.
- استخدم تنسيق HTML بسيط (مثل <h3> للعناوين و <br> للسطر الجديد) لضمان العرض الجميل.
"""

@app.route('/api/generate', methods=['POST'])
def generate():
    """نقطة نهاية لإنشاء الاختبار."""
    if not request.is_json:
        return jsonify({'error': 'يجب إرسال البيانات بصيغة JSON'}), 400

    if not api_key:
        return jsonify({'error': 'مفتاح API غير متوفر. تأكد من إعداده في Render'}), 500

    try:
        body = request.get_json()
        prompt = build_prompt(body)

        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)

        return jsonify({'result': response.text})

    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        return jsonify({'error': 'حدث خطأ أثناء معالجة الطلب.'}), 500

@app.route('/', methods=['GET'])
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>مولّد الاختبارات التربوية – المنهاج الجزائري</title>
        <style>
            * { box-sizing: border-box; margin: 0; font-family: 'Segoe UI', Tahoma, sans-serif; }
            body { background: #f5f7fa; padding: 20px; color: #1e2b3c; }
            .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 24px; box-shadow: 0 12px 30px rgba(0,0,0,0.08); padding: 28px 32px; }
            .developer-signature { text-align: left; margin-bottom: 10px; font-size: 0.9rem; color: #4a6572; border-bottom: 1px dashed #cbd5e1; padding-bottom: 10px; display: flex; justify-content: space-between; }
            .signature-name { background: #e9f2f0; padding: 6px 16px; border-radius: 40px; font-weight: 600; color: #0b3b5c; }
            h1 { font-size: 2.2rem; font-weight: 600; color: #0b3b5c; margin-bottom: 10px; border-right: 6px solid #2a9d8f; padding-right: 20px; }
            .subtitle { color: #4a6572; margin-bottom: 30px; }
            .form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 18px 24px; background: #fafbfc; padding: 24px; border-radius: 20px; margin-bottom: 30px; }
            .field-group { display: flex; flex-direction: column; gap: 6px; }
            .field-group.full-width { grid-column: 1 / -1; }
            label { font-weight: 600; font-size: 0.9rem; color: #1e3a5f; }
            input, select, textarea { padding: 12px 14px; border: 1.5px solid #d9e2ec; border-radius: 14px; font-size: 0.95rem; background: white; }
            .btn-green { background: #0b3b5c; color: white; border: none; padding: 16px 28px; font-size: 1.2rem; font-weight: bold; border-radius: 48px; cursor: pointer; width: 100%; max-width: 300px; margin: 10px 0; }
            .btn-green:disabled { background: #b0c4d9; cursor: not-allowed; }
            .status-area { display: flex; align-items: center; gap: 18px; margin: 20px 0; }
            #status { background: #eef3f7; padding: 8px 20px; border-radius: 40px; }
            .output-card { background: white; border: 1px solid #e2e9f0; border-radius: 24px; padding: 28px; margin-top: 20px; }
            footer { text-align: center; margin-top: 30px; color: #7a8f9f; }
        </style>
    </head>
    <body>
    <div class="container">
        <div class="developer-signature">
            <span>⚙️ تطوير: <span class="signature-name">Benhamida Youcef</span></span>
        </div>
        <h1>📋 مولّد الاختبارات التربوية</h1>
        <div class="subtitle">المنهاج الجزائري · إعداد احترافي مع الإجابة النموذجية</div>
        <div class="form-grid">
            <div class="field-group">
                <label>📚 المادة</label>
                <select id="subject">
                    <option value="الرياضيات" selected>الرياضيات</option>
                    <option value="اللغة العربية">اللغة العربية</option>
                    <option value="اللغة الفرنسية">اللغة الفرنسية</option>
                    <option value="اللغة الإنجليزية">اللغة الإنجليزية</option>
                    <option value="العلوم الفيزيائية">العلوم الفيزيائية</option>
                    <option value="علوم الطبيعة والحياة">علوم الطبيعة والحياة</option>
                    <option value="التاريخ والجغرافيا">التاريخ والجغرافيا</option>
                    <option value="التربية الإسلامية">التربية الإسلامية</option>
                    <option value="التربية المدنية">التربية المدنية</option>
                    <option value="الإعلام الآلي">الإعلام الآلي</option>
                </select>
            </div>
            <div class="field-group">
                <label>🎓 المستوى الدراسي</label>
                <select id="grade">
                    <option value="الأولى ابتدائي">الأولى ابتدائي</option>
                    <option value="الثانية ابتدائي">الثانية ابتدائي</option>
                    <option value="الثالثة ابتدائي">الثالثة ابتدائي</option>
                    <option value="الرابعة ابتدائي">الرابعة ابتدائي</option>
                    <option value="الخامسة ابتدائي">الخامسة ابتدائي</option>
                    <option value="الأولى متوسط">الأولى متوسط</option>
                    <option value="الثانية متوسط">الثانية متوسط</option>
                    <option value="الثالثة متوسط" selected>الثالثة متوسط</option>
                    <option value="الرابعة متوسط">الرابعة متوسط</option>
                    <option value="الأولى ثانوي">الأولى ثانوي</option>
                    <option value="الثانية ثانوي">الثانية ثانوي</option>
                    <option value="الثالثة ثانوي">الثالثة ثانوي</option>
                </select>
            </div>
            <div class="field-group">
                <label>📝 نوع الفرض</label>
                <select id="examType">
                    <option value="اختبار" selected>اختبار</option>
                    <option value="فرض">فرض</option>
                    <option value="امتحان">امتحان</option>
                </select>
            </div>
            <div class="field-group">
                <label>📅 السنة الدراسية</label>
                <input type="text" id="schoolYear" value="2025-2026">
            </div>
            <div class="field-group">
                <label>⏱️ المدة</label>
                <input type="text" id="duration" value="ساعتان">
            </div>
            <div class="field-group">
                <label>💯 العلامة الكاملة</label>
                <input type="text" id="mark" value="20">
            </div>
            <div class="field-group full-width">
                <label>🔖 الموضوع / المحور</label>
                <input type="text" id="topic" value="المعادلات والمتراجحات">
            </div>
            <div class="field-group">
                <label>🧩 أنواع الأسئلة</label>
                <input type="text" id="types" value="أسئلة موضوعية + تمارين">
            </div>
            <div class="field-group">
                <label>⚖️ مستوى الصعوبة</label>
                <select id="difficulty">
                    <option value="سهل">سهل</option>
                    <option value="متوسط" selected>متوسط</option>
                    <option value="صعب">صعب</option>
                </select>
            </div>
            <div class="field-group full-width">
                <label>📌 تعليمات إضافية</label>
                <textarea id="extra" rows="2"></textarea>
            </div>
        </div>
        <div style="display: flex; justify-content: center;">
            <button class="btn-green">✨ توليد الاختبار بالذكاء الاصطناعي</button>
        </div>
        <div class="status-area">
            <span id="status">⏳ جاهز</span>
        </div>
        <div class="output-card">
            <div id="output">
                <h2>📄 ورقة الاختبار</h2>
                <div class="meta">الرياضيات - الثالثة متوسط - اختبار</div>
                <hr>
                <p>جاهز للبدء. املأ الحقول ثم اضغط على الزر.</p>
            </div>
        </div>
        <footer>⚡ يستخدم Gemini API · Benhamida Youcef</footer>
    </div>
    <script>
        const API_URL = '/api/generate';
        function getField(id) { return document.getElementById(id).value; }
        function buildPayload() {
            return {
                subject: getField('subject'), grade: getField('grade'), examType: getField('examType'),
                schoolYear: getField('schoolYear'), duration: getField('duration'), mark: getField('mark'),
                topic: getField('topic'), types: getField('types'), difficulty: getField('difficulty'),
                extra: getField('extra')
            };
        }
        function renderResult(html) { document.getElementById('output').innerHTML = html; }
        async function generateExam() {
            const statusEl = document.getElementById('status');
            const btn = document.querySelector('.btn-green');
            const payload = buildPayload();
            btn.disabled = true;
            statusEl.textContent = '⏳ جاري الاتصال بـ Gemini...';
            renderResult('<p>⏳ يُرجى الانتظار...</p>');
            try {
                const res = await fetch(API_URL, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
                if (!res.ok) throw new Error('خطأ في الخادم');
                const data = await res.json();
                const safeHtml = (data.result || '').replace(/</g,'&lt;').replace(/\n/g,'<br>');
                renderResult('<div>'+safeHtml+'</div>');
                statusEl.textContent = '✅ تم بنجاح';
            } catch(e) {
                statusEl.textContent = '⚠️ خطأ: '+e.message;
                renderResult('<div style="color:red;">تعذر توليد الاختبار</div>');
            } finally { btn.disabled = false; }
        }
        document.addEventListener('DOMContentLoaded', () => {
            document.querySelector('.btn-green').addEventListener('click', generateExam);
        });
    </script>
    </body>
    </html>
    """
