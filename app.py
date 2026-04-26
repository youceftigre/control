import os
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# ========== إعدادات Groq ==========
# استخدم متغير البيئة للمفتاح (أمان تام)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ========== تحميل بنك الأسئلة من ملف JSON ==========
def load_question_bank():
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def home():
    return render_template("index.html")

# ========== تزويد الواجهة بالأسئلة (قابلة للتحديث) ==========
@app.route("/questions")
def get_questions():
    bank = load_question_bank()
    return jsonify(bank)

# ========== توليد الأسئلة بالذكاء الاصطناعي (Groq) ==========
@app.route("/generate", methods=["POST"])
def generate_ai():
    data = request.get_json()
    subject = data.get("subject", "")
    grade = data.get("grade", "")
    semester = data.get("semester", "")
    exam_type = data.get("examType", "اختبار فصلي")
    topic = data.get("topic", "")
    difficulty = data.get("difficulty", "متوسط")

    # بناء الموجه (Prompt) المحسن
    prompt = f"""
    أنت أستاذ جزائري خبير ملتزم بالمناهج الرسمية (الجيل الثاني).
    قم بإنشاء {exam_type} في مادة "{subject}"، المستوى "{grade}"، الفصل "{semester}".
    الموضوع الإضافي: "{topic}". مستوى الصعوبة العام: "{difficulty}".

    المتطلبات:
    - عدد الأسئلة: 4 إلى 6.
    - أنواع الأسئلة: اختيار من متعدد (mcq)، صح وخطأ (truefalse)، مقالي قصير (essay)، وتطبيقي (application).
    - تدرج الصعوبة: 20% سهل (1)، 50% متوسط (2)، 30% صعب (3).
    - اربط الأسئلة بالسياق الجزائري (مثلاً الحياة اليومية، التاريخ، الجغرافيا، الاقتصاد).
    - الدقة اللغوية والعلمية.
    - أعد الإجابة بصيغة JSON حصراً بدون أي نص إضافي:

    {{
      "questions": [
        {{
          "type": "mcq|truefalse|essay|application",
          "difficulty": 1|2|3,
          "text": "نص السؤال",
          "options": ["خيار1","خيار2","خيار3","خيار4"],   // فقط لـ MCQ
          "answer": "الإجابة الصحيحة",                  // لـ MCQ و truefalse
          "points": 2
        }}
      ],
      "total_points": 20
    }}
    """

    try:
        # استدعاء Groq API
        chat_completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # نموذج سريع ومناسب للغات (يدعم العربية)
            messages=[
                {"role": "system", "content": "أنت مساعد يرد بصيغة JSON حصراً."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        content = chat_completion.choices[0].message.content.strip()

        # تنظيف JSON من علامات Markdown المحتملة
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        ai_questions = json.loads(content)

        # التأكد من وجود المفتاح "questions"
        if "questions" not in ai_questions:
            ai_questions = {"questions": []}

        # ضبط القيم الافتراضية لكل سؤال
        for q in ai_questions["questions"]:
            q.setdefault("type", "essay")
            q.setdefault("difficulty", 2)
            q.setdefault("points", 2)
            if q["type"] == "mcq" and "options" not in q:
                q["options"] = []

        return jsonify(ai_questions)

    except json.JSONDecodeError:
        return jsonify({"error": "لم يتمكن النموذج من إرجاع JSON صالح. حاول مرة أخرى."}), 500
    except Exception as e:
        return jsonify({"error": f"فشل الاتصال بـ Groq: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
