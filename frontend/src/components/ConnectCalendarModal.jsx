import React, { useState } from "react";
import Button from "./Button";
import { getCalendarConnectUrl } from "../services/calendarApi";

export default function ConnectCalendarModal({ onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleConnect = async () => {
    setLoading(true);
    setError("");
    try {
      const url = await getCalendarConnectUrl();
      if (!url) {
        setError("Không lấy được liên kết kết nối Google Calendar.");
        return;
      }
      window.location.href = url;
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "Không thể kết nối Google Calendar. Vui lòng thử lại."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-800">
            Kết nối Google Calendar
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            ✕
          </button>
        </div>
        <p className="text-sm text-gray-600 mb-4 leading-relaxed">
          Bạn cần liên kết tài khoản Google để tạo lịch học trực tiếp từ câu
          trả lời. Chúng tôi chỉ yêu cầu quyền tạo và chỉnh sửa sự kiện trong
          lịch của bạn.
        </p>
        <ul className="text-sm text-gray-600 space-y-2 mb-5 list-disc list-inside">
          <li>Tạo nhắc nhở học tập từ câu trả lời hiện tại.</li>
          <li>Tự động điền tiêu đề, mô tả và nguồn tài liệu.</li>
          <li>Bạn có thể ngắt kết nối bất cứ lúc nào.</li>
        </ul>
        {error && (
          <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex items-center justify-end space-x-3">
          <button
            onClick={onClose}
            className="text-sm text-gray-600 hover:text-gray-800 transition"
            disabled={loading}
          >
            Hủy
          </button>
          <Button onClick={handleConnect} disabled={loading}>
            {loading ? "Đang mở Google..." : "Kết nối Google Calendar"}
          </Button>
        </div>
      </div>
    </div>
  );
}

