import React, { useState, useEffect } from "react";
import { uploadDocument, listDocuments, deleteDocument } from "../services/api";
import Card from "../components/Card";
import Button from "../components/Button";
import CalendarModal from "../components/CalendarModal";
import ConnectCalendarModal from "../components/ConnectCalendarModal";
import {
  createCalendarEvent,
  fetchCalendarStatus,
} from "../services/calendarApi";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  
  // Calendar states
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarSubmitting, setCalendarSubmitting] = useState(false);
  const [calendarFeedback, setCalendarFeedback] = useState("");

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

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Vui lòng chọn file");
      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    try {
      const result = await uploadDocument(file);
      setSuccess(
        `Upload thành công! File: ${result.filename}, Embedding: ${
          result.is_embedded ? "Đã embed" : "Chưa embed"
        }`
      );
      setFile(null);
      document.querySelector('input[type="file"]').value = "";
      await loadDocuments();
    } catch (err) {
      setError(err?.response?.data?.detail || "Upload thất bại");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (documentId) => {
    if (!confirm("Bạn có chắc muốn xóa tài liệu này?")) return;

    try {
      await deleteDocument(documentId);
      await loadDocuments();
      setSuccess("Đã xóa tài liệu");
    } catch (err) {
      setError("Xóa thất bại");
    }
  };

  // Calendar handlers
  const handleAddToCalendar = async (doc) => {
    setSelectedDocument(doc);
    setCalendarLoading(true);
    setCalendarFeedback("");
    
    try {
      const status = await fetchCalendarStatus();
      if (status?.connected) {
        setShowCalendarModal(true);
      } else {
        setShowConnectModal(true);
      }
    } catch (err) {
      setCalendarFeedback(
        err?.response?.data?.detail ||
          "Không thể kiểm tra trạng thái Google Calendar."
      );
    } finally {
      setCalendarLoading(false);
    }
  };

  const handleCreateEvent = async (payload) => {
    if (!selectedDocument) return;
    
    setCalendarSubmitting(true);
    setCalendarFeedback("");
    
    try {
      // Create event with document information
      const event = await createCalendarEvent({
        ...payload,
        event_type: "study_document",
        document_ids: [selectedDocument.id],
      });
      
      setShowCalendarModal(false);
      setCalendarFeedback(`✅ Đã thêm "${selectedDocument.filename}" vào lịch học tập!`);
      setSelectedDocument(null);
      
      // Clear feedback after 5 seconds
      setTimeout(() => setCalendarFeedback(""), 5000);
    } catch (err) {
      setCalendarFeedback(
        err?.response?.data?.detail ||
          "Không thể tạo sự kiện Google Calendar. Vui lòng thử lại."
      );
    } finally {
      setCalendarSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">📤</span>
          <h2 className="text-4xl font-bold text-gray-800">Upload Tài liệu</h2>
        </div>
        <p className="text-gray-600 ml-12">
          Tải lên và quản lý tài liệu học tập của bạn
        </p>
      </div>

      <Card className="mb-8 border-2 border-dashed border-purple-200 bg-gradient-to-br from-purple-50 to-blue-50">
        <form onSubmit={handleUpload}>
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              <span className="text-lg">📄</span> Chọn file (PDF, DOCX, MD,
              TXT):
            </label>
            <div className="relative">
              <input
                type="file"
                accept=".pdf,.docx,.doc,.md,.txt"
                onChange={(e) => setFile(e.target.files[0])}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all bg-white"
              />
              {file && (
                <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span className="text-sm text-green-800 font-medium">
                    {file.name}
                  </span>
                </div>
              )}
            </div>
          </div>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
              {success}
            </div>
          )}
          <Button
            type="submit"
            disabled={uploading || !file}
            variant="success"
            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 shadow-lg text-lg py-3"
          >
            {uploading ? (
              <span className="flex items-center justify-center">
                <span className="animate-spin mr-2">⏳</span>
                Đang upload và xử lý...
              </span>
            ) : (
              "📤 Upload Tài liệu"
            )}
          </Button>
        </form>
      </Card>

      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <span className="text-3xl mr-2">📚</span>
          <h3 className="text-2xl font-semibold text-gray-800">
            Danh sách tài liệu của bạn
          </h3>
        </div>
        {calendarFeedback && (
          <div className="px-4 py-2 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">
            {calendarFeedback}
          </div>
        )}
      </div>
      {documents.length === 0 ? (
        <Card>
          <p className="text-gray-600 text-center py-8">
            Chưa có tài liệu nào. Hãy upload tài liệu đầu tiên!
          </p>
        </Card>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full bg-white rounded-lg shadow-md overflow-hidden">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  File
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Loại
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Kích thước
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Chunks
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Embedded
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Ngày upload
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {doc.filename}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium uppercase">
                      {doc.file_type}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {(doc.file_size / (1024 * 1024)).toFixed(2)} MB
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 text-center">
                    {doc.chunk_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    {doc.is_embedded ? (
                      <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                        ✓ Đã embed
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs font-medium">
                        ✗ Chưa embed
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {new Date(doc.upload_date).toLocaleString("vi-VN", {
                      timeZone: "Asia/Ho_Chi_Minh",
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => handleAddToCalendar(doc)}
                        disabled={calendarLoading}
                        className="inline-flex items-center px-3 py-1.5 text-sm border border-purple-200 text-purple-600 hover:bg-purple-50 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Thêm file này vào lịch học tập"
                      >
                        <span className="mr-1">📅</span>
                        {calendarLoading ? "..." : "Lịch"}
                      </button>
                      <Button
                        onClick={() => handleDelete(doc.id)}
                        variant="danger"
                        className="text-sm py-1 px-3"
                      >
                        Xóa
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Calendar Modals */}
      {showConnectModal && (
        <ConnectCalendarModal onClose={() => setShowConnectModal(false)} />
      )}
      {showCalendarModal && selectedDocument && (
        <CalendarModal
          question={`Học tập tài liệu: ${selectedDocument.filename}`}
          answer={`Nội dung học: ${selectedDocument.filename}\nLoại file: ${selectedDocument.file_type}\nSố chunks: ${selectedDocument.chunk_count}\n\nĐây là tài liệu học tập được tải lên vào ${new Date(selectedDocument.upload_date).toLocaleString("vi-VN")}.`}
          references={[]}
          submitting={calendarSubmitting}
          onSubmit={handleCreateEvent}
          onClose={() => {
            setShowCalendarModal(false);
            setSelectedDocument(null);
          }}
        />
      )}
    </div>
  );
}
