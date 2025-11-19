import React from "react";

// QuizCard component for displaying a single question
export default function QuizCard({
  question,
  questionIndex,
  totalQuestions,
  userAnswer,
  onAnswer,
  showResult = false,
  disabled = false,
}) {
  const isMultipleChoice = question.question_type === "multiple_choice";
  const isTrueFalse = question.question_type === "true_false";

  const getOptionColor = (option) => {
    if (!showResult) {
      // Before answering or showing result
      if (userAnswer === option) {
        return "bg-gradient-to-r from-purple-600 to-pink-600 text-white border-purple-600 transform scale-105 shadow-lg";
      }
      return "bg-white border-gray-300 text-gray-800 hover:border-purple-400 hover:shadow-md";
    }

    // After showing result
    const isCorrect = option === question.correct_answer;
    const isUserAnswer = option === userAnswer;

    if (isCorrect) {
      return "bg-gradient-to-r from-green-500 to-emerald-600 text-white border-green-600 shadow-lg";
    }
    if (isUserAnswer && !isCorrect) {
      return "bg-gradient-to-r from-red-500 to-rose-600 text-white border-red-600 shadow-lg";
    }
    return "bg-white border-gray-200 text-gray-600";
  };

  const getOptionIcon = (option) => {
    if (!showResult) {
      return userAnswer === option ? "●" : "○";
    }

    const isCorrect = option === question.correct_answer;
    const isUserAnswer = option === userAnswer;

    if (isCorrect) return "✅";
    if (isUserAnswer && !isCorrect) return "❌";
    return "○";
  };

  return (
    <div className="bg-gradient-to-br from-white to-purple-50 rounded-2xl p-6 md:p-8 shadow-xl border-2 border-purple-200">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <span className="text-3xl mr-3">
            {isMultipleChoice ? "🎯" : "✓✗"}
          </span>
          <span className="text-lg font-bold text-gray-600">
            Câu {questionIndex + 1} / {totalQuestions}
          </span>
        </div>
        <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-bold">
          {isMultipleChoice ? "Trắc nghiệm" : "Đúng/Sai"}
        </span>
      </div>

      {/* Question */}
      <div className="mb-6">
        <h3 className="text-2xl font-bold text-gray-800 leading-relaxed">
          {question.question_text}
        </h3>
        {question.section && (
          <p className="text-sm text-gray-500 mt-2">
            📚 {question.section}
          </p>
        )}
      </div>

      {/* Options */}
      <div className="space-y-3">
        {question.options.map((option, idx) => {
          const optionLetter = isMultipleChoice
            ? String.fromCharCode(65 + idx)
            : null;

          return (
            <button
              key={idx}
              type="button"
              onClick={() => !disabled && onAnswer(option)}
              disabled={disabled}
              className={`w-full text-left px-6 py-4 rounded-xl border-2 font-medium text-lg transition-all transform hover:scale-102 ${getOptionColor(
                option
              )} ${disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer"}`}
            >
              <div className="flex items-center">
                <span className="mr-4 text-xl font-bold">
                  {getOptionIcon(option)}
                </span>
                {isMultipleChoice && (
                  <span className="mr-3 font-bold">{optionLetter})</span>
                )}
                <span className="flex-1">{option}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Explanation (shown after answer in practice mode) */}
      {showResult && (
        <div className="mt-6 p-5 bg-blue-50 border-2 border-blue-300 rounded-xl">
          <h4 className="font-bold text-blue-800 mb-2 flex items-center">
            <span className="text-xl mr-2">💡</span>
            Giải thích:
          </h4>
          <p className="text-blue-900 leading-relaxed">
            {question.explanation}
          </p>
        </div>
      )}
    </div>
  );
}

