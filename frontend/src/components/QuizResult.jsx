import React from "react";
import { useNavigate } from "react-router-dom";
import Card from "./Card";
import Button from "./Button";

export default function QuizResult({
  score,
  totalQuestions,
  percentage,
  timeTaken = null,
  mode = "practice",
  quizId,
  onRetry,
}) {
  const navigate = useNavigate();

  const getGrade = () => {
    if (percentage >= 90) return { text: "Xuất sắc!", emoji: "🏆", color: "from-yellow-400 to-orange-500" };
    if (percentage >= 80) return { text: "Giỏi lắm!", emoji: "⭐", color: "from-green-400 to-emerald-500" };
    if (percentage >= 70) return { text: "Khá tốt!", emoji: "👍", color: "from-blue-400 to-cyan-500" };
    if (percentage >= 60) return { text: "Đạt yêu cầu", emoji: "✓", color: "from-purple-400 to-pink-500" };
    return { text: "Cần cố gắng thêm", emoji: "💪", color: "from-gray-400 to-gray-500" };
  };

  const grade = getGrade();

  const formatTime = (seconds) => {
    if (!seconds) return null;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-100 via-pink-50 to-orange-50 flex items-center justify-center p-4">
      <Card className="max-w-2xl w-full border-4 border-purple-300 shadow-2xl">
        {/* Confetti Animation */}
        <div className="text-center mb-6">
          <div className="text-8xl mb-4 animate-bounce">{grade.emoji}</div>
          <h2 className={`text-4xl font-bold bg-gradient-to-r ${grade.color} bg-clip-text text-transparent mb-2`}>
            {grade.text}
          </h2>
          <p className="text-gray-600 text-lg">
            Bạn đã hoàn thành quiz!
          </p>
        </div>

        {/* Score Card */}
        <div className={`bg-gradient-to-r ${grade.color} rounded-2xl p-8 text-white text-center mb-6 shadow-xl`}>
          <div className="text-6xl font-bold mb-2">
            {score}/{totalQuestions}
          </div>
          <div className="text-2xl font-semibold">
            {percentage.toFixed(1)}%
          </div>
          {timeTaken && (
            <div className="mt-4 text-lg">
              ⏱️ Thời gian: {formatTime(timeTaken)}
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center p-4 bg-green-50 rounded-xl border-2 border-green-200">
            <div className="text-3xl font-bold text-green-600">{score}</div>
            <div className="text-sm text-green-800 font-medium">✅ Đúng</div>
          </div>
          <div className="text-center p-4 bg-red-50 rounded-xl border-2 border-red-200">
            <div className="text-3xl font-bold text-red-600">
              {totalQuestions - score}
            </div>
            <div className="text-sm text-red-800 font-medium">❌ Sai</div>
          </div>
          <div className="text-center p-4 bg-purple-50 rounded-xl border-2 border-purple-200">
            <div className="text-3xl font-bold text-purple-600">
              {totalQuestions}
            </div>
            <div className="text-sm text-purple-800 font-medium">📝 Tổng</div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <Button
            onClick={onRetry}
            className="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 py-3 text-lg"
          >
            <span className="mr-2">🔄</span>
            Làm lại
          </Button>
          <Button
            onClick={() => navigate("/quiz")}
            className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 py-3 text-lg"
          >
            <span className="mr-2">📋</span>
            Về trang Quiz
          </Button>
        </div>

        {/* Tips */}
        {percentage < 70 && (
          <div className="mt-6 p-4 bg-yellow-50 border-2 border-yellow-300 rounded-xl">
            <p className="text-yellow-800 text-sm">
              <span className="font-bold">💡 Gợi ý:</span> Hãy xem lại tài liệu và thử lại để đạt kết quả tốt hơn!
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

