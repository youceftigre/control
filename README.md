# منصة الامتحانات الجزائرية - نسخة Render (الإنتاج)

تطبيق Flask لتوليد اختبارات وفق المنهاج الجزائري الرسمي عبر LLM (Groq) مع دعم
بنية الاختبار الجزائرية، الكفاءات الختامية، الوضعية الإدماجية، وتصدير إلى
Aiken/GIFT/PDF لاستيراد مباشر في Moodle.

## المميزات الرئيسية

- **محاذاة كاملة مع المنهاج الجزائري**: كتالوج مُسجَّل في
  `data/algeria_curriculum.json` يصف الأطوار الثلاثة (ابتدائي/متوسط/ثانوي)،
  المواد، الشُّعب (علوم/آداب)، المعاملات، أنواع الاختبارات الرسمية.
- **بنية اختبار رسمية**: الجزء الأول (تمارين) + الجزء الثاني (وضعية إدماجية)
  للمتوسط والثانوي، مع نمط البكالوريا التجريبية.
- **سُلّم تنقيط معياري**: 20 نقطة للمتوسط/الثانوي، 10 نقاط للابتدائي.
- **تحقق صارم من إخراج LLM**: تطابق `model_answers` مع `questions`، تفرّد
  خيارات MCQ، إعادة حساب `total_points` تلقائياً.
- **تصدير Moodle**: Aiken (للـ MCQ) + GIFT (للـ MCQ و True/False) + PDF عربي
  RTL عبر WeasyPrint.

## النشر على Render

نشر التطبيق على Render.com مجاناً.

## النشر السريع

### الطريقة الأولى: ربط GitHub (موصى بها)

1. ادفع هذه الملفات إلى ريبو GitHub خاص بك (أو استعمل ريبو موجود).
2. اذهب إلى https://dashboard.render.com → **New +** → **Web Service**.
3. اختر الريبو والـ branch.
4. Render سيقرأ `render.yaml` تلقائياً ويضبط:
   - `Build Command: pip install -r requirements.txt`
   - `Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2`
   - Disk mount على `/data` بحجم 1GB
5. **مهم**: أضف `GROQ_API_KEY` في **Environment** يدوياً (هو في render.yaml كـ `sync: false`):
   - Key: `GROQ_API_KEY`
   - Value: `gsk_your_real_key`
6. اضغط **Create Web Service**.
7. انتظر 2-3 دقائق للنشر الأول.
8. افتح URL الذي أعطاك Render (مثلاً `https://control-yc3p.onrender.com`).

### الطريقة الثانية: نشر يدوي (بدون render.yaml)

في Render dashboard:
- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2`
- **Environment Variables**: أضف `GROQ_API_KEY`
- **Disk** (اختياري لكن موصى به):
  - Name: `data`
  - Mount Path: `/data`
  - Size: 1 GB

## الملفات الأساسية

```
render-version/
├── app.py                          # الخادم Flask (لا يعتمد على متغيرات OS-specific)
├── requirements.txt                # اعتمادات Python (متوافقة مع Render)
├── render.yaml                     # تكوين Render تلقائي
├── Procfile                        # احتياط (Render يفضل render.yaml)
├── templates/index.html            # الواجهة
├── data/
│   ├── questions_full_bank.json    # 388 سؤال
│   └── subjects_config.json
└── tests/                          # اختبارات اختيارية
```

## بعد النشر

### تأكد من نجاح النشر

```bash
# فحص الصحة
curl https://control-yc3p.onrender.com/health
# ← {"status":"healthy",...}

# تأكد من البنك
curl https://control-yc3p.onrender.com/questions | python -c "import json,sys; d=json.load(sys.stdin); print('subjects:', len(d))"
# ← subjects: 10
```

### إذا ظهر خطأ "Service unavailable"

Render Free Plan **يُفعّل النوم بعد 15 دقيقة عدم نشاط**. أول طلب بعد النوم يأخذ 30-50 ثانية. هذا طبيعي.

### مراقبة السجلات

في Render dashboard → خدمتك → **Logs**. السجلات منظمة JSON من `structlog`. ابحث عن:
- `event="exam_generation_started"` → بدء توليد اختبار
- `event="exam_generation_completed"` → نجاح
- `event="exam_generation_failed"` → فشل (مع `request_id` للتتبع)

## استكشاف الأخطاء

### الواجهة 404 على `/`
- تأكد أن `templates/index.html` في المستودع.
- تأكد أن `app.py` يحوي route `@app.route("/")` (موجود في النسخة الجديدة).

### `groq.AuthenticationError: Invalid API Key`
- تأكد من ضبط `GROQ_API_KEY` بقيمة صحيحة (يبدأ بـ `gsk_`).
- ابحث عن خطأ نسخ/لصق (مسافات، حروف زائدة).

### `Application failed to respond`
- راجع Render logs.
- تأكد أن `Start Command` يحوي `--bind 0.0.0.0:$PORT`.
- تأكد أن `app:app` صحيح (`app.py` يحوي متغير `app = Flask(__name__)`).

### قاعدة البيانات تختفي بعد إعادة النشر
- تأكد من إضافة Disk mount على `/data` (مذكور في render.yaml).
- بدون Disk mount، SQLite يُحفظ على القرص المؤقت ويُمسح مع كل إعادة نشر.

## الترقية إلى Pro

Free Plan له قيود:
- يدخل النوم بعد 15 دقيقة عدم نشاط
- 750 ساعة/شهر
- لا يمكن تخصيص نطاق محلي

للإنتاج الجدي: قم بترقية إلى Starter ($7/شهر) لإلغاء النوم.

## واجهات API

### `GET /curriculum`
أعِد كتالوج المنهاج الكامل. يستعمله الـ frontend لتعبئة قوائم الاختيار.

```bash
curl https://control-yc3p.onrender.com/curriculum | jq '.stages | keys'
# ["middle","primary","secondary"]
```

### `POST /curriculum/validate`
تحقّق سريع من توليفة (subject, grade) قبل التوليد.

```bash
curl -X POST https://control-yc3p.onrender.com/curriculum/validate \
     -H "Content-Type: application/json" \
     -d '{"subject":"الرياضيات","grade":"السنة 3 علوم"}'
# {"is_exact": true, "stage": "secondary", "exam_total": 20.0,
#  "coefficient": 5, "subject_canonical": "رياضيات", "warnings": []}
```

### `POST /generate`
ينشئ اختباراً جديداً ويحفظه في DB. مثال للسنة الثالثة ثانوي علوم تجريبية:

```bash
curl -X POST https://control-yc3p.onrender.com/generate \
     -H "Content-Type: application/json" \
     -d '{
       "subject": "الرياضيات",
       "grade": "السنة 3 علوم",
       "branch": "علوم تجريبية",
       "semester": "الفصل الثاني",
       "examType": "اختبار فصلي",
       "topic": "الدوال اللوغاريتمية",
       "difficulty": "متوسط",
       "num_questions": 6
     }'
```

الاستجابة:
```json
{
  "success": true,
  "db_id": 42,
  "questions": [...],
  "total_points": 20.0,
  "metadata": {
    "stage": "secondary",
    "coefficient": 5,
    "exam_total_official": 20.0,
    ...
  }
}
```

### `POST /generate_full_exam`
نفس `/generate` لكن يُرجع التصحيح النموذجي و الحلول المفصّلة كذلك.

### `GET /exam/<id>`
يجلب اختباراً محفوظاً مع الأسئلة والتصحيح والـ metadata.

### `GET /export/aiken/<id>` / `GET /export/gift/<id>`
يُصدّر الاختبار بصيغة Aiken (MCQ فقط) أو GIFT (يدعم MCQ + True/False) لاستيراده
مباشرة في بنك أسئلة Moodle.

### `GET /export/pdf/<id>?teacher=true`
يُنتج PDF عربياً RTL. عند `teacher=true` يُضمَّن التصحيح النموذجي.

## التطوير المحلي

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=gsk_xxx
python app.py
# يستمع على http://localhost:5000
```

### تشغيل الاختبارات
```bash
pip install pytest ruff
pytest tests/ -v
ruff check .
```

## بنية المشروع

```
.
├── app.py                          # خادم Flask (التوليد + التصدير + DB)
├── curriculum.py                   # كتالوج المنهاج + validators
├── data/
│   ├── algeria_curriculum.json     # الكتالوج الرسمي (مراحل، شُعب، مواد، معاملات)
│   ├── questions_full_bank.json    # بنك أسئلة جاهز
│   └── subjects_config.json
├── templates/index.html
├── tests/                          # 54 اختبار وحدة + تكامل
└── render.yaml
```
