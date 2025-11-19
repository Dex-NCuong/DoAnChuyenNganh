import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getQuiz, submitQuiz } from "../services/quizApi";
import QuizCard from "../components/QuizCard";
import QuizResult from "../components/QuizResult";
import Button from "../components/Button";

export default function QuizTest() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswers, setUserAnswers] = useState({});
  const [completed, setCompleted] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  
  // Timer state
  const [timeLeft, setTimeLeft] = useState(0);
  const [totalTime, setTotalTime] = useState(0);
  const timerIntervalRef = useRef(null);

  useEffect(() => {
    loadQuiz();
    return () => {
      // Cleanup timer on unmount
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [quizId]);

  const loadQuiz = async () => {
    setLoading(true);
    setError("");
    
    try {
      const data = await getQuiz(quizId);
      setQuiz(data);
      
      // Calculate time: 1 minute per question (60s * num_questions)
      const calculatedTime = data.total_questions * 60;
      setTimeLeft(calculatedTime);
      setTotalTime(calculatedTime);
      
      // Start timer
      startTimer(calculatedTime);
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Không thể tải quiz"
      );
    } finally {
      setLoading(false);
    }
  };

  const startTimer = (initialTime) => {
    let time = initialTime;
    
    timerIntervalRef.current = setInterval(() => {
      time -= 1;
      setTimeLeft(time);
      
      if (time <= 0) {
        clearInterval(timerIntervalRef.current);
        // Auto submit when time's up
        finishQuiz(true);
      }
    }, 1000);
  };

  const handleAnswer = (answer) => {
    const currentQuestion = quiz.questions[currentIndex];
    const isCorrect = answer === currentQuestion.correct_answer;

    setUserAnswers({
      ...userAnswers,
      [currentIndex]: {
        user_answer: answer,
        is_correct: isCorrect,
      },
    });
  };

  const handleNext = () => {
    if (currentIndex < quiz.questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const finishQuiz = async (timeUp = false) => {
    // Stop timer
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
    }

    // Convert userAnswers to array format
    const answersArray = quiz.questions.map((q, idx) => ({
      question_index: idx,
      user_answer: userAnswers[idx]?.user_answer || "",
      is_correct: userAnswers[idx]?.is_correct || false,
    }));

    const score = answersArray.filter((a) => a.is_correct).length;
    const timeTaken = totalTime - timeLeft;

    try {
      // Submit to backend
      const result = await submitQuiz(quizId, "test", answersArray, timeTaken);
      setResult(result);
      setCompleted(true);
    } catch (err) {
      console.error("Failed to submit quiz", err);
      // Still show result even if submit fails
      setResult({
        score,
        total_questions: quiz.total_questions,
        percentage: (score / quiz.total_questions) * 100,
        time_taken: timeTaken,
      });
      setCompleted(true);
    }
  };

  const handleRetry = () => {
    // Reload quiz to restart
    setCurrentIndex(0);
    setUserAnswers({});
    setCompleted(false);
    setResult(null);
    loadQuiz();
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const getTimerColor = () => {
    const percentLeft = (timeLeft / totalTime) * 100;
    if (percentLeft > 50) return "text-green-600";
    if (percentLeft > 20) return "text-yellow-600";
    return "text-red-600 animate-pulse";
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-100 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4 animate-spin">⏱️</div>
          <p className="text-xl font-bold text-gray-700">Đang chuẩn bị bài test...</p>
        </div>
      </div>
    );
  }

  if (error || !quiz) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-100 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
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
        mode="test"
        quizId={quizId}
        onRetry={handleRetry}
      />
    );
  }

  const currentQuestion = quiz.questions[currentIndex];
  const currentAnswer = userAnswers[currentIndex];
  const progress = ((currentIndex + 1) / quiz.total_questions) * 100;
  const answeredCount = Object.keys(userAnswers).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-100 via-indigo-50 to-purple-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header with Timer */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              ⏱️ Chế độ Test
            </h1>
            <p className="text-gray-600">
              {quiz.document_filename}
            </p>
          </div>
          <div className="text-center">
            <div className={`text-5xl font-bold ${getTimerColor()}`}>
              {formatTime(timeLeft)}
            </div>
            <div className="text-sm text-gray-600 mt-1">
              Thời gian còn lại
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-6 bg-white rounded-full h-4 shadow-inner overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 transition-all duration-500 rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Answered Count */}
        <div className="mb-6 text-center">
          <span className="text-lg font-bold text-gray-700">
            Đã trả lời: {answeredCount} / {quiz.total_questions}
          </span>
        </div>

        {/* Quiz Card - No explanation shown in test mode */}
        <QuizCard
          question={currentQuestion}
          questionIndex={currentIndex}
          totalQuestions={quiz.total_questions}
          userAnswer={currentAnswer?.user_answer}
          onAnswer={handleAnswer}
          showResult={false}
          disabled={false}
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
              className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
            >
              Câu tiếp theo →
            </Button>
          ) : (
            <Button
              onClick={() => finishQuiz(false)}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-lg font-bold"
            >
              🏁 Nộp bài
            </Button>
          )}
        </div>

        {/* Warning if time low */}
        {timeLeft <= 60 && timeLeft > 0 && (
          <div className="mt-4 p-4 bg-red-50 border-2 border-red-300 rounded-xl text-red-800 text-center font-bold animate-pulse">
            ⚠️ Chỉ còn {timeLeft} giây!
          </div>
        )}

        {/* Info */}
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800 text-center">
          ⏱️ Chế độ Test: Làm hết mới chấm điểm. Không xem giải thích.
        </div>
      </div>
    </div>
  );
}

