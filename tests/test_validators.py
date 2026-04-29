"""اختبارات Pydantic validators للأسئلة و الاختبار الكامل."""

import pytest
from pydantic import ValidationError

from app import (
    FullGeneratedExam,
    MCQQuestion,
    ModelAnswer,
    QuestionType,
    TrueFalseQuestion,
)


# ---------------------- MCQ ----------------------


def test_mcq_valid():
    q = MCQQuestion(
        difficulty=1,
        text="ما هي عاصمة الجزائر؟ اختر الإجابة الصحيحة",
        points=1.5,
        options=["الجزائر", "وهران", "قسنطينة", "عنابة"],
        answer="الجزائر",
    )
    assert q.type == QuestionType.MCQ
    assert q.answer in q.options


def test_mcq_duplicate_options_rejected():
    with pytest.raises(ValidationError) as excinfo:
        MCQQuestion(
            difficulty=1,
            text="سؤال يحتوي على خيارات مكررة عمداً",
            points=1.0,
            options=["باريس", "باريس", "لندن", "روما"],
            answer="باريس",
        )
    assert "متميّز" in str(excinfo.value) or "متميز" in str(excinfo.value)


def test_mcq_empty_option_rejected():
    with pytest.raises(ValidationError):
        MCQQuestion(
            difficulty=1,
            text="سؤال يحتوي على خيار فارغ غير صالح",
            points=1.0,
            options=["باريس", "", "لندن"],
            answer="باريس",
        )


def test_mcq_options_are_stripped():
    q = MCQQuestion(
        difficulty=1,
        text="سؤال يستعمل خيارات بفراغات حول النص",
        points=1.0,
        options=["  باريس  ", " لندن", "روما "],
        answer="باريس",
    )
    assert q.options == ["باريس", "لندن", "روما"]


def test_mcq_answer_must_be_in_options():
    with pytest.raises(ValidationError):
        MCQQuestion(
            difficulty=1,
            text="سؤال إجابته ليست ضمن الخيارات المعروضة",
            points=1.0,
            options=["باريس", "لندن", "روما"],
            answer="مدريد",
        )


# ------------------ FullGeneratedExam ------------------


def _make_questions(n: int):
    return [
        TrueFalseQuestion(
            difficulty=1,
            text=f"السؤال رقم {i + 1}: هل العبارة صحيحة؟",
            points=1.0,
            answer=True,
        ).model_dump()
        for i in range(n)
    ]


def _make_answers(n: int):
    return [
        ModelAnswer(
            question_index=i,
            question_text=f"السؤال رقم {i + 1}",
            correct_answer=True,
            detailed_solution="شرح الحل",
        ).model_dump()
        for i in range(n)
    ]


def test_full_exam_total_points_recomputed():
    exam = FullGeneratedExam(
        questions=_make_questions(3),
        model_answers=_make_answers(3),
        total_points=999.0,  # قيمة خاطئة من الـ LLM
    )
    # validator يجب أن يعيد الحساب
    assert exam.total_points == 3.0


def test_full_exam_mismatched_lengths_rejected():
    with pytest.raises(ValidationError) as excinfo:
        FullGeneratedExam(
            questions=_make_questions(3),
            model_answers=_make_answers(2),  # ناقص واحد
        )
    assert "model_answers" in str(excinfo.value) or "التصحيحات" in str(excinfo.value)


def test_full_exam_duplicate_indices_rejected():
    answers = _make_answers(3)
    answers[1]["question_index"] = 0  # تكرار 0
    with pytest.raises(ValidationError):
        FullGeneratedExam(
            questions=_make_questions(3),
            model_answers=answers,
        )


def test_full_exam_index_out_of_range_rejected():
    answers = _make_answers(3)
    answers[2]["question_index"] = 10  # خارج النطاق
    with pytest.raises(ValidationError):
        FullGeneratedExam(
            questions=_make_questions(3),
            model_answers=answers,
        )
