# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from dotenv import load_dotenv
import os
import traceback
import random

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
# قاعدة بيانات المنهاج الجزائري
# ============================================================

CURRICULUM_DB = {
    "الرياضيات": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["الأعداد الطبيعية", "الأعداد العشرية", "العمليات"],
            "الفصل الثاني": ["الكسور", "النسبة والتناسب", "المعادلات"],
            "الفصل الثالث": ["الزوايا", "المثلثات", "الدوائر"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الأعداد الصحيحة", "القوى", "الجذور"],
            "الفصل الثاني": ["المعادلات", "الدوال", "الإحصاء"],
            "الفصل الثالث": ["الزوايا المتقابلة", "المتوازيات", "المثلثات المتشابهة"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الأعداد النسبية", "العمليات", "الأعداد الحقيقية"],
            "الفصل الثاني": ["المعادلات والمتراجحات", "الدوال التآلفية", "الإحصاء"],
            "الفصل الثالث": ["النسب المثلثية", "المتجهات", "الهندسة في الفضاء"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["المعادلات من الدرجة الثانية", "الدوال", "التغيرات"],
            "الفصل الثاني": ["الإحصاء", "الدوال التآلفية", "الدوال التربيعية"],
            "الفصل الثالث": ["الهندسة في الفضاء", "المساحات والحجوم", "التشابه"]
        }
    },
    "اللغة العربية": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثاني": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثالث": ["النص القرائي", "الإملاء", "البلاغة"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثاني": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثالث": ["النص القرائي", "الإملاء", "الضمائر"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثاني": ["النص القرائي", "الإملاء", "النحو"],
            "الفصل الثالث": ["النص القرائي", "الإملاء", "البلاغة"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["النص القرائي", "الإملاء", "البلاغة"],
            "الفصل الثاني": ["النص القرائي", "الإملاء", "البلاغة"],
            "الفصل الثالث": ["النص القرائي", "الإملاء", "البلاغة"]
        }
    },
    "العلوم الفيزيائية والتكنولوجيا": {
        "السنة الأولى متوسط": {
            "الفصل الأول": ["الضوء", "المرآة", "العدسات"],
            "الفصل الثاني": ["الكهرباء", "الدوائر", "الموصلات"],
            "الفصل الثالث": ["المادة", "التحولات", "الخلائط"]
        },
        "السنة الثانية متوسط": {
            "الفصل الأول": ["الحركة", "القوى", "التوازن"],
            "الفصل الثاني": ["الضغط", "الطفو", "الضغط الجوي"],
            "الفصل الثالث": ["الطاقة", "أشكال الطاقة", "تحولات الطاقة"]
        },
        "السنة الثالثة متوسط": {
            "الفصل الأول": ["الكهرباء", "القانون العام", "القدرة"],
            "الفصل الثاني": ["الحركة", "العمل", "الآلات"],
            "الفصل الثالث": ["الضوء", "العدسات", "العين"]
        },
        "السنة الرابعة متوسط": {
            "الفصل الأول": ["الكهرباء المتردد", "المحولات", "التوزيع"],
            "الفصل الثاني": ["الحركة الدائرية", "القمر الصناعي", "الجاذبية"],
            "الفصل الثالث": ["الطاقة النووية", "التفاعلات", "الاستخدامات"]
        }
    }
}

VALID_SUBJECTS = list(CURRICULUM_DB.keys())
VALID_GRADES = ["السنة الأولى متوسط", "السنة الثانية متوسط", "السنة الثالثة متوسط", "السنة الرابعة متوسط"]
VALID_SEMESTERS = ["الفصل الأول", "الفصل الثاني", "الفصل الثالث"]

def validate_request(body):
    required_fields = ['subject', 'grade', 'schoolYear', 'duration', 'examType', 'semester']
    missing = [f for f in required_fields if not body.get(f)]
    if missing:
        return False, f"الحقول المفقودة: {', '.join(missing)}"

    subject = body.get('subject')
    if subject not in VALID_SUBJECTS:
        return False, f"المادة غير معروفة"

    grade = body.get('grade')
    if grade not in VALID_GRADES:
        return False, f"المستوى غير صالح"

    return True, "صالح"

def build_prompt(body):
    subject = body.get('subject')
    grade = body.get('grade')
    semester = body.get('semester')
    topic = body.get('topic', '')
    difficulty = body.get('difficulty', 'متوسط')
    school = body.get('school', 'مدرسة')

    prompt = f"""أنت مفتش تعليم جزائري متخصص في {subject}. أنشئ {body.get('examType', 'اختبار')} بالتنسيق الرسمي الجزائري.

المعلومات:
- المؤسسة: {school}
- المادة: {subject}
- المستوى: {grade}
- الفصل: {semester}
- السنة الدراسية: {body.get('schoolYear')}
- المدة: {body.get('duration')}
- العلامة: 20/20
- الصعوبة: {difficulty}
- الموضوع: {topic or 'غير محدد'}

=== التنسيق المطلوب (HTML دقيق) ===

يجب أن يكون الاختبار على صفحتين:

**الصفحة 1: ورقة الأسئلة**

<div style="font-family: 'Traditional Arabic', 'Arial', sans-serif; direction: rtl; padding: 20px; max-width: 800px; margin: 0 auto;">

<!-- الترويسة -->
<div style="text-align: center; margin-bottom: 20px;">
    <div style="font-size: 14px; font-weight: bold;">الجمهورية الجزائرية الديمقراطية الشعبية</div>
    <div style="font-size: 13px;">وزارة التربية الوطنية</div>
    <div style="margin-top: 10px; font-size: 12px;">
        المؤسسة: {school} | السنة الدراسية: {body.get('schoolYear')} | المدة: {body.get('duration')}
    </div>
    <div style="margin-top: 5px; font-size: 14px; font-weight: bold;">
        اختبار الفصل {semester.replace('الفصل ', '')} في مادة {subject}
    </div>
    <div style="font-size: 13px;">المستوى: {grade}</div>
</div>

<hr style="border: 1px solid black; margin: 15px 0;">

<!-- الجزء الأول -->
<div style="margin-bottom: 20px;">
    <div style="font-weight: bold; text-decoration: underline; margin-bottom: 15px;">
        الجزء الأول (12 نقطة)
    </div>

    <!-- التمرين الأول -->
    <div style="margin-bottom: 20px;">
        <div style="font-weight: bold; text-decoration: underline;">
            التمرين الأول: (03 نقاط)
        </div>
        <div style="margin-top: 10px; padding-right: 20px;">
            [أسئلة التمرين الأول هنا]
        </div>
    </div>

    <!-- التمرين الثاني -->
    <div style="margin-bottom: 20px;">
        <div style="font-weight: bold; text-decoration: underline;">
            التمرين الثاني: (03 نقاط)
        </div>
        <div style="margin-top: 10px; padding-right: 20px;">
            [أسئلة التمرين الثاني هنا]
        </div>
    </div>

    <!-- التمرين الثالث -->
    <div style="margin-bottom: 20px;">
        <div style="font-weight: bold; text-decoration: underline;">
            التمرين الثالث: (03 نقاط)
        </div>
        <div style="margin-top: 10px; padding-right: 20px;">
            [أسئلة التمرين الثالث هنا]
        </div>
    </div>

    <!-- التمرين الرابع -->
    <div style="margin-bottom: 20px;">
        <div style="font-weight: bold; text-decoration: underline;">
            التمرين الرابع: (03 نقاط)
        </div>
        <div style="margin-top: 10px; padding-right: 20px;">
            [أسئلة التمرين الرابع هنا]
        </div>
    </div>
</div>

<!-- الجزء الثاني -->
<div style="margin-bottom: 20px;">
    <div style="font-weight: bold; text-decoration: underline; margin-bottom: 15px;">
        الجزء الثاني (08 نقاط)
    </div>

    <div style="font-weight: bold; text-decoration: underline;">
        الوضعية الإدماجية:
    </div>
    <div style="margin-top: 10px; padding-right: 20px;">
        [نص الوضعية الإدماجية هنا]
    </div>
</div>

</div>

**الصفحة 2: التصحيح النموذجي وسلم التنقيط**

<div style="font-family: 'Traditional Arabic', 'Arial', sans-serif; direction: rtl; padding: 20px; max-width: 800px; margin: 0 auto;">

<div style="text-align: center; font-weight: bold; font-size: 16px; margin-bottom: 20px; text-decoration: underline;">
    التصحيح النموذجي وسلم التنقيط
</div>

<table style="width: 100%; border-collapse: collapse; border: 2px solid black;">
    <tr style="background-color: #f0f0f0;">
        <th style="border: 1px solid black; padding: 8px; width: 15%;">نقطة</th>
        <th style="border: 1px solid black; padding: 8px; width: 15%;">المجموع</th>
        <th style="border: 1px solid black; padding: 8px;">التصحيح النموذجي (سلم التنقيط)</th>
    </tr>
    <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">03</td>
        <td style="border: 1px solid black; padding: 8px; text-align: center;" rowspan="4">12</td>
        <td style="border: 1px solid black; padding: 8px;">
            <strong>حل التمرين الأول:</strong><br>
            [الإجابة النموذجية مع توزيع النقاط]
        </td>
    </tr>
    <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">03</td>
        <td style="border: 1px solid black; padding: 8px;">
            <strong>حل التمرين الثاني:</strong><br>
            [الإجابة النموذجية مع توزيع النقاط]
        </td>
    </tr>
    <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">03</td>
        <td style="border: 1px solid black; padding: 8px;">
            <strong>حل التمرين الثالث:</strong><br>
            [الإجابة النموذجية مع توزيع النقاط]
        </td>
    </tr>
    <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">03</td>
        <td style="border: 1px solid black; padding: 8px;">
            <strong>حل التمرين الرابع:</strong><br>
            [الإجابة النموذجية مع توزيع النقاط]
        </td>
    </tr>
    <tr>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">08</td>
        <td style="border: 1px solid black; padding: 8px; text-align: center;">08</td>
        <td style="border: 1px solid black; padding: 8px;">
            <strong>حل الوضعية الإدماجية:</strong><br>
            [الإجابة النموذجية مع توزيع النقاط التفصيلي]
        </td>
    </tr>
</table>

</div>

=== شروط صارمة ===
1. استخدم HTML فقط، لا Markdown
2. لا تستخدم <input> أو <button> أو <script>
3. اجعل التنسيق مطابقاً للصورة تماماً
4. التمرين = 03 نقاط، الوضعية = 08 نقاط
5. المجموع = 20 نقطة
6. ممنوع أي مادة أخرى غير {subject}
"""
    return prompt

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    return jsonify({'subjects': VALID_SUBJECTS, 'grades': VALID_GRADES, 'semesters': VALID_SEMESTERS})

@app.route('/api/topics', methods=['GET'])
def get_topics():
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    semester = request.args.get('semester')

    if not subject or not grade:
        return jsonify({'error': 'المادة والمستوى مطلوبان'}), 400

    grade_data = CURRICULUM_DB.get(subject, {}).get(grade, {})
    if semester:
        topics = grade_data.get(semester, [])
        return jsonify({'semester': semester, 'topics': topics})
    return jsonify({'grade': grade, 'semesters': grade_data})

@app.route('/api/generate', methods=['POST'])
def generate():
    if not request.is_json:
        return jsonify({'error': 'JSON مطلوب'}), 400
    if not api_key:
        return jsonify({'error': 'مفتاح Groq API غير موجود'}), 500

    try:
        body = request.get_json()
        is_valid, message = validate_request(body)
        if not is_valid:
            return jsonify({'error': message}), 400

        subject = body.get('subject')
        prompt = build_prompt(body)

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"أنت مفتش تعليم جزائري في {subject} فقط. أنشئ اختبارات بتنسيق رسمي."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=4000,
            top_p=0.95
        )

        result = chat_completion.choices[0].message.content
        return jsonify({'success': True, 'result': result})

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
            messages=[{"role": "user", "content": "قل مرحبا"}],
            model="llama-3.1-8b-instant",
            max_tokens=50
        )
        return f"✅ Groq يعمل"
    except Exception as e:
        return f"❌ فشل: {traceback.format_exc()}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
