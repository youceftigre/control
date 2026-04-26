import os
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# ========== إعدادات Groq ==========
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ========== تحميل بنك الأسئلة ==========
QUESTION_BANK_PATH = os.environ.get("QUESTION_BANK_PATH", "questions.json")

def load_question_bank():
    try:
        with open(QUESTION_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ خطأ في تحميل البنك: {e}")
        return {}

# ========== التحقق من صحة السؤال ==========
def validate_question(q):
    """التحقق من صحة بنية السؤال وتوافقه مع المعايير"""
    errors = []

    if not isinstance(q, dict):
        return ["السؤال ليس كائن JSON صالح"]

    required_fields = ["type", "difficulty", "text", "points"]
    for field in required_fields:
        if field not in q:
            errors.append(f"الحقل المطلوب '{field}' مفقود")

    if q.get("type") == "mcq":
        if "options" not in q or not isinstance(q["options"], list) or len(q["options"]) < 2:
            errors.append("أسئلة الاختيار من متعدد تتطلب خيارين على الأقل")
        if "answer" not in q:
            errors.append("أسئلة MCQ تتطلب إجابة صحيحة")

    if q.get("type") == "truefalse":
        if "answer" not in q or not isinstance(q["answer"], bool):
            errors.append("أسئلة صح/خطأ تتطلب إجابة بوليانية")

    diff = q.get("difficulty")
    if diff not in [1, 2, 3]:
        errors.append("مستوى الصعوبة يجب أن يكون 1 أو 2 أو 3")

    text = q.get("text", "")
    if len(text) < 10:
        errors.append("نص السؤال قصير جداً")

    return errors

# ========== تصنيف الأسئلة حسب المعايير ==========
def classify_question_difficulty(text, q_type):
    """تصنيف تلقائي لصعوبة السؤال بناءً على تحليل النص"""
    text_lower = text.lower()

    # كلمات مفتاحية للصعوبة
    hard_indicators = ["برهن", "ناقش", "قارن", "حلل", "اقترح", "استنتج", "أثبت", "أوجد", "احسب", "تطبيقي"]
    medium_indicators = ["اشرح", "وضح", "عرف", "اذكر", "صحح", "استخرج"]

    hard_count = sum(1 for word in hard_indicators if word in text_lower)
    medium_count = sum(1 for word in medium_indicators if word in text_lower)

    if hard_count >= 2 or q_type in ["application", "problem"]:
        return 3
    elif medium_count >= 1 or q_type == "essay":
        return 2
    return 1

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/questions")
def get_questions():
    bank = load_question_bank()
    return jsonify(bank)

@app.route("/validate", methods=["POST"])
def validate_exam():
    """نقطة نهاية للتحقق من صحة مجموعة أسئلة"""
    data = request.get_json()
    questions = data.get("questions", [])

    report = {
        "total": len(questions),
        "valid": 0,
        "invalid": 0,
        "by_type": {},
        "by_difficulty": {1: 0, 2: 0, 3: 0},
        "errors": [],
        "recommendations": []
    }

    for i, q in enumerate(questions):
        errors = validate_question(q)
        q_type = q.get("type", "unknown")
        diff = q.get("difficulty", 2)

        report["by_type"][q_type] = report["by_type"].get(q_type, 0) + 1
        report["by_difficulty"][diff] = report["by_difficulty"].get(diff, 0) + 1

        if errors:
            report["invalid"] += 1
            report["errors"].append({"index": i, "text": q.get("text", "")[:50], "errors": errors})
        else:
            report["valid"] += 1

    # توصيات
    total = len(questions)
    if total > 0:
        easy_pct = report["by_difficulty"].get(1, 0) / total
        hard_pct = report["by_difficulty"].get(3, 0) / total

        if easy_pct > 0.5:
            report["recommendations"].append("نسبة الأسئلة السهلة مرتفعة (>{:.0%}). يُنصح بزيادة الأسئلة المتوسطة والصعبة.".format(easy_pct))
        if hard_pct < 0.15:
            report["recommendations"].append("نسبة الأسئلة الصعبة منخفضة (<15%). يُنصح بإضافة أسئلة تطبيقية وتحليلية.")
        if report["by_type"].get("mcq", 0) / total > 0.6:
            report["recommendations"].append("نسبة أسئلة الاختيار من متعدد مرتفعة. يُنصح بتنويع أنواع الأسئلة.")

    return jsonify(report)

# ========== توليد الأسئلة بالذكاء الاصطناعي (محسّن) ==========
@app.route("/generate", methods=["POST"])
def generate_ai():
    data = request.get_json()
    subject = data.get("subject", "")
    grade = data.get("grade", "")
    semester = data.get("semester", "")
    exam_type = data.get("examType", "اختبار فصلي")
    topic = data.get("topic", "")
    difficulty = data.get("difficulty", "متوسط")

    # اختيار النموذج حسب تعقيد المادة
    model = "llama-3.3-70b-versatile" if subject in ["رياضيات", "فيزياء وكيمياء", "علوم"] else "llama-3.1-8b-instant"

    # بناء الموجه المحسّن (Prompt Engineering)
    prompt = f"""أنت أستاذ جزائري خبير ملتزم بالمناهج الرسمية (الجيل الثاني) ومعتمد من وزارة التربية الوطنية.

المهمة: إنشاء {exam_type} في مادة "{subject}"، المستوى "{grade}"، الفصل "{semester}".
الموضوع المحدد: "{topic}". مستوى الصعوبة العام: "{difficulty}".

=== قواعد صارمة ===
1. عدد الأسئلة: بالضبط 5 أسئلة.
2. توزيع أنواع الأسئلة:
   - سؤال 1: اختيار من متعدد (mcq) - 4 خيارات
   - سؤال 2: صح أو خطأ (truefalse)
   - سؤال 3: مقالي قصير (essay) - يتطلب شرحاً
   - سؤال 4: تطبيقي (application) - يتطلب حل مشكلة واقعية
   - سؤال 5: تطبيقي/مشكلة (application/problem) - يتطلب تفكيراً نقدياً

3. توزيع الصعوبة:
   - سؤال 1: سهل (difficulty: 1, points: 1)
   - سؤال 2: سهل (difficulty: 1, points: 0.5)
   - سؤال 3: متوسط (difficulty: 2, points: 2 أو 2.5)
   - سؤال 4: متوسط (difficulty: 2, points: 3 أو 3.5)
   - سؤال 5: صعب (difficulty: 3, points: 4)

4. متطلبات الجودة:
   - اربط السؤال التطبيقي بالسياق الجزائري (مدن، مناطق، تاريخ، اقتصاد).
   - استخدم لغة عربية فصحى دقيقة.
   - للرياضيات والفيزياء: استخدم ترميز LaTeX بين \( و \).
   - تأكد من صحة المعلومات العلمية والتاريخية.
   - لا تكرر نفس الفكرة في سؤالين.

5. صيغة الإخراج (JSON فقط، بدون أي نص إضافي):
{{
  "questions": [
    {{
      "type": "mcq",
      "difficulty": 1,
      "text": "نص السؤال بالعربية الفصحى",
      "options": ["الخيار أ", "الخيار ب", "الخيار ج", "الخيار د"],
      "answer": "الخيار الصحيح بالضبط كما ورد في options",
      "points": 1
    }},
    {{
      "type": "truefalse",
      "difficulty": 1,
      "text": "عبارة صحيحة أو خاطئة",
      "answer": true أو false,
      "points": 0.5
    }},
    {{
      "type": "essay",
      "difficulty": 2,
      "text": "سؤال يتطلب شرحاً أو إعراباً أو تحليلاً",
      "points": 2.5
    }},
    {{
      "type": "application",
      "difficulty": 2,
      "text": "سؤال تطبيقي مرتبط بالواقع الجزائري",
      "points": 3.5
    }},
    {{
      "type": "application",
      "difficulty": 3,
      "text": "سؤال تطبيقي صعب يتطلب تفكيراً نقدياً وحل مشكلة",
      "points": 4
    }}
  ],
  "total_points": 11.5,
  "metadata": {{
    "subject": "{subject}",
    "grade": "{grade}",
    "semester": "{semester}",
    "topic": "{topic}",
    "generated_at": "{datetime.now().isoformat()}"
  }}
}}

=== مثال على سؤال تطبيقي جيد ===
"مزرعة في ولاية البليدة تنتج 500 كغ من البرتقال يومياً. إذا زاد الإنتاج بنسبة 15% شهرياً، احسب الإنتاج بعد 3 أشهر."

=== تذكير ===
- أعد الإجابة بصيغة JSON صالحة فقط.
- لا تضف أي نص قبل أو بعد JSON.
- تأكد من أن جميع الحقول موجودة.
"""

    try:
        chat_completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "أنت مساعد تعليمي جزائري متخصص في إعداد الاختبارات. ترد دائماً بصيغة JSON صالحة فقط بدون أي تعليقات أو شرح."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,  # أقل عشوائية لضمان الدقة
            max_tokens=2000,
            response_format={"type": "json_object"}  # فرض صيغة JSON
        )

        content = chat_completion.choices[0].message.content.strip()

        # تنظيف JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        ai_questions = json.loads(content)

        # التحقق والتصحيح التلقائي
        if "questions" not in ai_questions:
            ai_questions = {"questions": []}

        validated_questions = []
        for q in ai_questions["questions"]:
            q.setdefault("type", "essay")
            q.setdefault("difficulty", 2)
            q.setdefault("points", 2)

            if q["type"] == "mcq":
                q.setdefault("options", ["خيار 1", "خيار 2", "خيار 3", "خيار 4"])
                if "answer" not in q:
                    q["answer"] = q["options"][0] if q["options"] else ""

            if q["type"] == "truefalse":
                if "answer" not in q:
                    q["answer"] = True

            # التحقق من الأخطاء
            errors = validate_question(q)
            if errors:
                print(f"⚠️ تحذير: سؤال به أخطاء: {errors}")

            validated_questions.append(q)

        ai_questions["questions"] = validated_questions
        ai_questions["validation"] = {
            "checked_at": datetime.now().isoformat(),
            "total_questions": len(validated_questions),
            "warnings": []
        }

        return jsonify(ai_questions)

    except json.JSONDecodeError as e:
        return jsonify({
            "error": "لم يتمكن النموذج من إرجاع JSON صالح. حاول مرة أخرى.",
            "details": str(e)
        }), 500
    except Exception as e:
        return jsonify({
            "error": f"فشل الاتصال بـ Groq: {str(e)}",
            "suggestion": "تحقق من مفتاح API أو حاول لاحقاً"
        }), 500

# ========== نقطة نهاية للإحصائيات ==========
@app.route("/stats")
def get_stats():
    bank = load_question_bank()
    stats = {
        "subjects": list(bank.keys()),
        "total_subjects": len(bank),
        "grades_covered": set(),
        "total_questions": 0,
        "by_type": {},
        "by_difficulty": {1: 0, 2: 0, 3: 0},
        "last_updated": datetime.now().isoformat()
    }

    for subject, grades in bank.items():
        for grade, chapters in grades.items():
            stats["grades_covered"].add(grade)
            for chapter, questions in chapters.items():
                stats["total_questions"] += len(questions)
                for q in questions:
                    q_type = q.get("type", "unknown")
                    stats["by_type"][q_type] = stats["by_type"].get(q_type, 0) + 1
                    diff = q.get("difficulty", 2)
                    stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

    stats["grades_covered"] = list(stats["grades_covered"])
    return jsonify(stats)

if __name__ == "__main__":
    app.run(debug=True)
