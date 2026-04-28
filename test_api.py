#!/usr/bin/env python3
"""
اختبار سريع للتطبيق
استخدام: python test_api.py
"""

import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:5000/api"

def test_health():
    """فحص صحة التطبيق"""
    print("=" * 70)
    print("🔍 فحص صحة التطبيق...")
    print("=" * 70)
    try:
        response = requests.get("http://localhost:5000/health")
        pprint(response.json())
        print("✅ التطبيق يعمل!\n")
    except Exception as e:
        print(f"❌ خطأ: {e}\n")

def test_get_questions():
    """الحصول على بنك الأسئلة"""
    print("=" * 70)
    print("📚 الحصول على بنك الأسئلة...")
    print("=" * 70)
    try:
        response = requests.get(f"{BASE_URL}/questions")
        data = response.json()
        print(f"✅ تم تحميل {len(data)} مادة")
        print(f"المواد: {list(data.keys())}\n")
    except Exception as e:
        print(f"❌ خطأ: {e}\n")

def test_get_stats():
    """احصائيات بنك الأسئلة"""
    print("=" * 70)
    print("📊 احصائيات بنك الأسئلة...")
    print("=" * 70)
    try:
        response = requests.get(f"{BASE_URL}/stats")
        stats = response.json()
        print(f"إجمالي الأسئلة: {stats['total_questions']}")
        print(f"الأطوار: {list(stats['by_level'].keys())}")
        print(f"الأنواع: {list(stats['by_type'].keys())}")
        print(f"الصعوبات: {stats['by_difficulty']}\n")
    except Exception as e:
        print(f"❌ خطأ: {e}\n")

def test_generate_exam():
    """توليد اختبار بـ AI"""
    print("=" * 70)
    print("🤖 توليد اختبار باستخدام Groq AI...")
    print("=" * 70)
    
    payload = {
        "subject": "رياضيات",
        "grade": "السنة الأولى متوسط",
        "semester": "الفصل الأول",
        "examType": "اختبار فصلي",
        "topic": "",
        "difficulty": "متوسط"
    }
    
    print(f"البيانات المرسلة: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")
    
    try:
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        data = response.json()
        
        if "error" in data:
            print(f"❌ خطأ: {data['error']}\n")
        else:
            questions = data.get('questions', [])
            print(f"✅ تم توليد {len(questions)} أسئلة")
            if questions:
                print(f"\nالسؤال الأول:\n{questions[0]['text']}\n")
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}\n")
        print("💡 تأكد من أن التطبيق يعمل: python app.py\n")

def test_filter_bank():
    """تصفية بنك الأسئلة"""
    print("=" * 70)
    print("🔍 تصفية بنك الأسئلة...")
    print("=" * 70)
    
    payload = {
        "subject": "رياضيات",
        "grade": "السنة الأولى متوسط",
        "topic": ""
    }
    
    try:
        response = requests.post(f"{BASE_URL}/filter-bank", json=payload)
        data = response.json()
        questions = data.get('questions', [])
        print(f"✅ تم العثور على {len(questions)} سؤال من الفلاتر المحددة\n")
    except Exception as e:
        print(f"❌ خطأ: {e}\n")

def main():
    """تشغيل جميع الاختبارات"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🎓 اختبار منصة الامتحانات الجزائرية".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # اختبار الاتصال الأول
    test_health()
    
    # باقي الاختبارات
    test_get_questions()
    test_get_stats()
    test_filter_bank()
    test_generate_exam()
    
    print("=" * 70)
    print("✨ انتهت الاختبارات!")
    print("=" * 70)

if __name__ == "__main__":
    main()
