import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { listDocuments } from "../services/api";
import { generateQuiz, listQuizzes, deleteQuiz } from "../services/quizApi";
import Card from "../components/Card";
import Button from "../components/Button";

export default function Quiz() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [quizzes, setQuizzes] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState("");
  const [numQuestions, setNumQuestions] = useState(3);
  const [difficulty, setDifficulty] = useState("medium");
  const [questionTypes, setQuestionTypes] = useState([
    "multiple_choice",
    "true_false",
  ]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadDocuments();
    loadQuizzes();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const loadQuizzes = async () => {
    try {
      const data = await listQuizzes(null, 50);
      setQuizzes(data);
    } catch (err) {
      console.error("Failed to load quizzes", err);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    
    if (!selectedDoc) {
      setError("Vui lòng chọn tài liệu");
      return;
    }

    if (questionTypes.length === 0) {
      setError("Vui lòng chọn ít nhất một loại câu hỏi");
      return;
    }

    // Validate số câu hỏi từ 1-3
    if (numQuestions < 1 || numQuestions > 3) {
      setError("Số câu hỏi phải từ 1 đến 3 câu");
      return;
    }

    setGenerating(true);
    setError("");
    setSuccess("");

    try {
      const quiz = await generateQuiz(
        selectedDoc,
        numQuestions,
        difficulty,
        questionTypes
      );
      
      setSuccess(`✅ Đã tạo quiz với ${quiz.total_questions} câu hỏi!`);
      await loadQuizzes();
      
      // Auto navigate to practice mode after 2 seconds
      setTimeout(() => {
        navigate(`/quiz/practice/${quiz.id}`);
      }, 2000);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "Không thể tạo quiz. Vui lòng thử lại."
      );
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (quizId) => {
    if (!confirm("Bạn có chắc muốn xóa quiz này?")) return;

    try {
      await deleteQuiz(quizId);
      await loadQuizzes();
      setSuccess("Đã xóa quiz");
    } catch (err) {
      setError("Xóa thất bại");
    }
  };

  const toggleQuestionType = (type) => {
    if (questionTypes.includes(type)) {
      setQuestionTypes(questionTypes.filter((t) => t !== type));
    } else {
      setQuestionTypes([...questionTypes, type]);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">🎯</span>
          <h2 className="text-4xl font-bold text-gray-800">Tạo Quiz Ôn Tập</h2>
        </div>
        <p className="text-gray-600 ml-12">
          AI tự động tạo câu hỏi trắc nghiệm từ tài liệu của bạn
        </p>
      </div>

      {/* Quiz Generator Card - Kahoot style */}
      <Card className="mb-8 border-2 border-purple-300 bg-gradient-to-br from-purple-100 via-pink-50 to-orange-50 shadow-xl">
        <form onSubmit={handleGenerate}>
          {/* Select Document */}
          <div className="mb-6">
            <label className="block text-lg font-bold text-gray-800 mb-3">
              <span className="text-2xl mr-2">📚</span> Chọn tài liệu:
            </label>
            <select
              value={selectedDoc}
              onChange={(e) => setSelectedDoc(e.target.value)}
              className="w-full px-4 py-3 border-2 border-purple-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all bg-white text-lg font-medium"
              required
            >
              <option value="">-- Chọn file để tạo quiz --</option>
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
          </div>

          {/* Number of Questions - 1 to 3 for optimal AI generation */}
          <div className="mb-6">
            <label className="block text-lg font-bold text-gray-800 mb-3">
              <span className="text-2xl mr-2">🔢</span> Số câu hỏi (1-3 câu):
            </label>
            <select
              value={numQuestions}
              onChange={(e) => setNumQuestions(parseInt(e.target.value))}
              className="w-full px-4 py-3 border-2 border-purple-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all bg-white text-lg font-medium"
              required
            >
              <option value={1}>1 câu</option>
              <option value={2}>2 câu</option>
              <option value={3}>3 câu</option>
            </select>
            <p className="text-sm text-gray-600 mt-2">
              Số câu hỏi tối ưu để AI tạo quiz chất lượng cao (bắt buộc từ 1-3 câu)
            </p>
          </div>

          {/* Difficulty */}
          <div className="mb-6">
            <label className="block text-lg font-bold text-gray-800 mb-3">
              <span className="text-2xl mr-2">📊</span> Độ khó:
            </label>
            <div className="flex gap-3">
              {[
                { value: "easy", label: "Dễ", color: "from-green-500 to-emerald-500", icon: "😊" },
                { value: "medium", label: "Trung bình", color: "from-yellow-500 to-orange-500", icon: "🤔" },
                { value: "hard", label: "Khó", color: "from-red-500 to-rose-600", icon: "😤" },
              ].map((diff) => (
                <button
                  key={diff.value}
                  type="button"
                  onClick={() => setDifficulty(diff.value)}
                  className={`flex-1 px-6 py-4 rounded-xl font-bold text-lg transition-all transform hover:scale-105 ${
                    difficulty === diff.value
                      ? `bg-gradient-to-r ${diff.color} text-white shadow-lg scale-105`
                      : "bg-white border-2 border-gray-300 text-gray-700 hover:border-purple-400"
                  }`}
                >
                  <span className="text-2xl mr-2">{diff.icon}</span>
                  {diff.label}
                </button>
              ))}
            </div>
          </div>

          {/* Question Types */}
          <div className="mb-6">
            <label className="block text-lg font-bold text-gray-800 mb-3">
              <span className="text-2xl mr-2">📝</span> Loại câu hỏi:
            </label>
            <div className="space-y-3">
              <label className="flex items-center p-4 bg-white rounded-xl border-2 border-gray-300 cursor-pointer hover:border-purple-400 transition-all">
                <input
                  type="checkbox"
                  checked={questionTypes.includes("multiple_choice")}
                  onChange={() => toggleQuestionType("multiple_choice")}
                  className="w-6 h-6 text-purple-600 rounded focus:ring-purple-500"
                />
                <span className="ml-3 text-lg font-medium text-gray-800">
                  <span className="text-xl mr-2">🎯</span>
                  Trắc nghiệm (2 đáp án A, B)
                </span>
              </label>
              <label className="flex items-center p-4 bg-white rounded-xl border-2 border-gray-300 cursor-pointer hover:border-purple-400 transition-all">
                <input
                  type="checkbox"
                  checked={questionTypes.includes("true_false")}
                  onChange={() => toggleQuestionType("true_false")}
                  className="w-6 h-6 text-purple-600 rounded focus:ring-purple-500"
                />
                <span className="ml-3 text-lg font-medium text-gray-800">
                  <span className="text-xl mr-2">✓✗</span>
                  Đúng / Sai
                </span>
              </label>
            </div>
          </div>

          {/* Errors & Success */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border-2 border-red-300 text-red-700 rounded-xl text-sm font-medium">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-4 p-4 bg-green-50 border-2 border-green-300 text-green-700 rounded-xl text-sm font-medium">
              {success}
            </div>
          )}

          {/* Generate Button */}
          <Button
            type="submit"
            disabled={generating || !selectedDoc}
            className="w-full bg-gradient-to-r from-purple-600 via-pink-600 to-orange-500 hover:from-purple-700 hover:via-pink-700 hover:to-orange-600 shadow-xl text-xl py-4 transform hover:scale-105 transition-all"
          >
            {generating ? (
              <span className="flex items-center justify-center">
                <span className="animate-spin mr-3 text-2xl">🎲</span>
                Đang tạo quiz bằng AI...
              </span>
            ) : (
              <span className="flex items-center justify-center">
                <span className="mr-3 text-2xl">🎲</span>
                Tạo Quiz Ngay!
              </span>
            )}
          </Button>
        </form>
      </Card>

      {/* Quiz List */}
      <div className="flex items-center mb-6">
        <span className="text-3xl mr-2">📋</span>
        <h3 className="text-2xl font-semibold text-gray-800">
          Quiz đã tạo ({quizzes.length})
        </h3>
      </div>

      {quizzes.length === 0 ? (
        <Card className="bg-gradient-to-br from-gray-50 to-gray-100">
          <p className="text-gray-600 text-center py-8">
            Chưa có quiz nào. Hãy tạo quiz đầu tiên!
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {quizzes.map((quiz) => (
            <Card
              key={quiz.id}
              className="border-2 border-purple-200 bg-gradient-to-br from-white to-purple-50 hover:shadow-xl transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h4 className="text-lg font-bold text-gray-800 mb-1">
                    📄 {quiz.document_filename}
                  </h4>
                  <div className="flex items-center gap-3 text-sm text-gray-600">
                    <span className="flex items-center">
                      <span className="mr-1">🔢</span>
                      {quiz.total_questions} câu
                    </span>
                    <span className="flex items-center">
                      <span className="mr-1">
                        {quiz.difficulty === "easy"
                          ? "😊"
                          : quiz.difficulty === "hard"
                          ? "😤"
                          : "🤔"}
                      </span>
                      {quiz.difficulty === "easy"
                        ? "Dễ"
                        : quiz.difficulty === "hard"
                        ? "Khó"
                        : "TB"}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    {new Date(quiz.created_at).toLocaleString("vi-VN")}
                  </p>
                </div>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => navigate(`/quiz/practice/${quiz.id}`)}
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white rounded-lg font-medium transition-all transform hover:scale-105 shadow-md"
                >
                  <span className="mr-2">💡</span>
                  Practice
                </button>
                <button
                  onClick={() => navigate(`/quiz/test/${quiz.id}`)}
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-lg font-medium transition-all transform hover:scale-105 shadow-md"
                >
                  <span className="mr-2">⏱️</span>
                  Test
                </button>
                <button
                  onClick={() => handleDelete(quiz.id)}
                  className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-all"
                  title="Xóa quiz"
                >
                  🗑️
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

