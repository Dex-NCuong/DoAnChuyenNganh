import React, { useState, useEffect } from "react";
import { getHistory, deleteHistory, listDocuments } from "../services/api";
import Card from "../components/Card";
import Button from "../components/Button";

export default function History() {
  const [histories, setHistories] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    loadHistory();
  }, [selectedDoc]);

  const loadDocuments = async () => {
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const loadHistory = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getHistory(selectedDoc || null, 50);
      setHistories(data);
    } catch (err) {
      setError("Không thể tải lịch sử");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (historyId) => {
    if (!confirm("Bạn có chắc muốn xóa bản ghi này?")) return;

    try {
      await deleteHistory(historyId);
      await loadHistory();
    } catch (err) {
      setError("Xóa thất bại");
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Đang tải...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">📚</span>
          <h2 className="text-4xl font-bold text-gray-800">Lịch sử Hỏi - Đáp</h2>
        </div>
        <p className="text-gray-600 ml-12">Xem lại các câu hỏi và câu trả lời trước đó</p>
      </div>

      <Card className="mb-6 border-2 border-purple-100">
        <div className="mb-4">
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            <span className="text-lg">🔍</span> Lọc theo tài liệu:
          </label>
          <select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            className="w-full max-w-md px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all bg-white"
          >
            <option value="">Tất cả</option>
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
          {error}
        </div>
      )}

      {histories.length === 0 ? (
        <Card>
          <p className="text-gray-600 text-center py-12">Chưa có lịch sử hỏi đáp nào.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {histories.map((history) => (
            <Card key={history.id} className="hover:shadow-xl transition-all duration-300 border-2 border-gray-100 hover:border-purple-200">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-500">
                    {new Date(history.created_at).toLocaleString("vi-VN", {
                      timeZone: "Asia/Ho_Chi_Minh",
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                  {history.references && history.references.length > 0 && (
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                      {history.references.length} nguồn
                    </span>
                  )}
                </div>
                <Button
                  onClick={() => handleDelete(history.id)}
                  variant="danger"
                  className="text-sm py-1 px-3"
                >
                  Xóa
                </Button>
              </div>
              <div className="mb-3">
                <div className="flex items-start">
                  <span className="font-semibold text-blue-600 mr-2">Q:</span>
                  <p className="text-gray-800 flex-1">{history.question}</p>
                </div>
              </div>
              <div>
                <div className="flex items-start">
                  <span className="font-semibold text-green-600 mr-2">A:</span>
                  <div className="text-gray-700 whitespace-pre-wrap flex-1 leading-relaxed">
                    {history.answer}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

