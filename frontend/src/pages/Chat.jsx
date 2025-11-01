import React, { useState, useEffect } from "react";
import { askQuestion, listDocuments } from "../services/api";
import Card from "../components/Card";
import Button from "../components/Button";

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [selectedDoc, setSelectedDoc] = useState("");
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [references, setReferences] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (err) {
      setError("Không thể tải danh sách tài liệu");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setReferences([]);

    try {
      const result = await askQuestion(
        question,
        selectedDoc || null
      );
      setAnswer(result.answer);
      setReferences(result.references || []);
      setQuestion("");
    } catch (err) {
      setError(err?.response?.data?.detail || "Gửi câu hỏi thất bại");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">💬</span>
          <h2 className="text-4xl font-bold text-gray-800">Chat với AI</h2>
        </div>
        <p className="text-gray-600 ml-12">Đặt câu hỏi và nhận câu trả lời thông minh từ tài liệu của bạn</p>
      </div>

      <Card className="mb-6 border-2 border-purple-100 bg-gradient-to-br from-white to-purple-50">
        <div className="mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            <span className="text-lg">📚</span> Chọn tài liệu (tùy chọn):
          </label>
          <select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all bg-white"
          >
            <option value="">Tất cả tài liệu</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              <span className="text-lg">❓</span> Câu hỏi của bạn:
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ví dụ: Tóm tắt nội dung chính của tài liệu này? Hoặc giải thích về..."
              rows={5}
              className="w-full px-4 py-4 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none resize-none transition-all text-base"
              required
            />
          </div>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}
          <Button 
            type="submit" 
            disabled={loading || !question.trim()} 
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 shadow-lg text-lg py-3"
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <span className="animate-spin mr-2">⏳</span>
                Đang xử lý với AI...
              </span>
            ) : (
              "🚀 Gửi câu hỏi"
            )}
          </Button>
        </form>
      </Card>

      {answer && (
        <Card className="mb-6 border-2 border-green-200 bg-gradient-to-br from-green-50 to-blue-50">
          <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
            <span className="text-2xl mr-2">✨</span>
            Câu trả lời từ AI:
          </h3>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 whitespace-pre-wrap text-gray-700 leading-relaxed text-base">
            {answer}
          </div>
        </Card>
      )}

      {references.length > 0 && (
        <Card className="border-2 border-blue-100 bg-gradient-to-br from-white to-blue-50">
          <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
            <span className="text-2xl mr-2">🔍</span>
            Nguồn tham khảo ({references.length} chunk)
          </h3>
          <div className="space-y-3">
            {references.map((ref, idx) => (
              <div
                key={idx}
                className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-600">
                    Chunk #{ref.chunk_index || idx + 1}
                  </span>
                  <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full">
                    {(ref.score * 100).toFixed(1)}% tương đồng
                  </span>
                </div>
                <div className="text-sm text-gray-600 line-clamp-3">
                  {ref.content_preview
                    ? ref.content_preview.substring(0, 200) + "..."
                    : "Nội dung không khả dụng"}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

