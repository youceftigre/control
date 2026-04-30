"""
إعدادات pytest المشتركة.

يضبط متغيرات البيئة قبل استيراد ``app`` كي:
- لا يحاول الاتصال بـ Groq.
- يستعمل قاعدة بيانات SQLite في الذاكرة (لا يلوّث القرص).
"""
import os
import sys

# أضف جذر المشروع إلى sys.path حتى يعمل ``import app``/``import curriculum``
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_STORAGE", "memory://")
# لا نضبط GROQ_API_KEY عمداً: التطبيق يجب أن يبدأ بدونها ويعطي خطأ واضح.
