import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getQuiz, submitQuiz } from "../services/quizApi";
import QuizCard from "../components/QuizCard";
import QuizResult from "../components/QuizResult";
import Button from "../components/Button";

export default function QuizPractice() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswers, setUserAnswers] = useState({});
  const [showExplanation, setShowExplanation] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadQuiz();
  }, [quizId]);

  const loadQuiz = async () => {
    setLoading(true);
    setError("");
    
    try {
      const data = await getQuiz(quizId);
      setQuiz(data);
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Không thể tải quiz"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = (answer) => {
    if (showExplanation) return; // Already answered this question

    const currentQuestion = quiz.questions[currentIndex];
    const isCorrect = answer === currentQuestion.correct_answer;

    setUserAnswers({
      ...userAnswers,
      [currentIndex]: {
        user_answer: answer,
        is_correct: isCorrect,
      },
    });

    // Show explanation immediately in practice mode
    setShowExplanation(true);
  };

  const handleNext = () => {
    if (currentIndex < quiz.questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowExplanation(false);
    } else {
      // Finished all questions
      finishQuiz();
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setShowExplanation(!!userAnswers[currentIndex - 1]);
    }
  };

  const finishQuiz = async () => {
    // Convert userAnswers to array format
    const answersArray = quiz.questions.map((q, idx) => ({
      question_index: idx,
      user_answer: userAnswers[idx]?.user_answer || "",
      is_correct: userAnswers[idx]?.is_correct || false,
    }));

    const score = answersArray.filter((a) => a.is_correct).length;
    const percentage = (score / quiz.total_questions) * 100;

    try {
      // Submit to backend
      const result = await submitQuiz(quizId, "practice", answersArray);
      setResult(result);
      setCompleted(true);
    } catch (err) {
      console.error("Failed to submit quiz", err);
      // Still show result even if submit fails
      setResult({
        score,
        total_questions: quiz.total_questions,
        percentage,
      });
      setCompleted(true);
    }
  };

  const handleRetry = () => {
    setCurrentIndex(0);
    setUserAnswers({});
    setShowExplanation(false);
    setCompleted(false);
    setResult(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-100 via-pink-50 to-orange-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-spin">🎯</div>
          <p className="text-xl font-bold text-gray-700">Đang tải quiz...</p>
        </div>
      </div>
    );
  }

  if (error || !quiz) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-100 via-pink-50 to-orange-50 flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">😔</div>
          <h2 className="text-2xl font-bold text-gray-800 mb-4">
            {error || "Quiz không tồn tại"}
          </h2>
          <Button onClick={() => navigate("/quiz")} className="mt-4">
            Về trang Quiz
          </Button>
        </div>
      </div>
    );
  }

  if (completed && result) {
    return (
      <QuizResult
        score={result.score}
        totalQuestions={result.total_questions}
        percentage={result.percentage}
        timeTaken={result.time_taken}
        mode="practice"
        quizId={quizId}
        onRetry={handleRetry}
      />
    );
  }

  const currentQuestion = quiz.questions[currentIndex];
  const currentAnswer = userAnswers[currentIndex];
  const progress = ((currentIndex + 1) / quiz.total_questions) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-100 via-pink-50 to-orange-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              💡 Chế độ Practice
            </h1>
            <p className="text-gray-600">
              {quiz.document_filename}
            </p>
          </div>
          <button
            onClick={() => navigate("/quiz")}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
          >
            ✕ Thoát
          </button>
        </div>

        {/* Progress Bar */}
        <div className="mb-6 bg-white rounded-full h-4 shadow-inner overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-500 transition-all duration-500 rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Score Summary */}
        <div className="mb-6 flex items-center justify-center gap-6 text-lg font-bold">
          <span className="flex items-center text-green-600">
            <span className="text-2xl mr-2">✅</span>
            {Object.values(userAnswers).filter((a) => a.is_correct).length} đúng
          </span>
          <span className="flex items-center text-red-600">
            <span className="text-2xl mr-2">❌</span>
            {Object.values(userAnswers).filter((a) => !a.is_correct).length} sai
          </span>
        </div>

        {/* Quiz Card */}
        <QuizCard
          question={currentQuestion}
          questionIndex={currentIndex}
          totalQuestions={quiz.total_questions}
          userAnswer={currentAnswer?.user_answer}
          onAnswer={handleAnswer}
          showResult={showExplanation}
          disabled={showExplanation}
        />

        {/* Navigation */}
        <div className="mt-6 flex gap-3">
          <Button
            onClick={handlePrevious}
            disabled={currentIndex === 0}
            className="px-6 py-3 bg-gray-600 hover:bg-gray-700"
          >
            ← Câu trước
          </Button>
          
          {currentIndex < quiz.questions.length - 1 ? (
            <Button
              onClick={handleNext}
              disabled={!showExplanation}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
            >
              Câu tiếp theo →
            </Button>
          ) : (
            <Button
              onClick={finishQuiz}
              disabled={Object.keys(userAnswers).length !== quiz.total_questions}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-lg font-bold"
            >
              🏁 Hoàn thành Quiz
            </Button>
          )}
        </div>

        {/* Hint */}
        {!showExplanation && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800 text-center">
            💡 Chọn đáp án để xem giải thích ngay lập tức
          </div>
        )}
      </div>
    </div>
  );
}

