import React, { useMemo, useState } from "react";
import Button from "./Button";

function pad(value) {
  return value.toString().padStart(2, "0");
}

function formatDateForInput(date) {
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function buildDescription(answer, references) {
  const refLines =
    references && references.length > 0
      ? "\n\nNguồn tham khảo:\n" +
        references
          .map((ref) => {
            const docName = ref.document_filename || "Tài liệu";
            let refLabel = docName;
            if (ref.section) {
              refLabel += ` - ${ref.section}`;
            } else if (ref.page_number) {
              refLabel += ` - Trang ${ref.page_number}`;
            }
            return `• ${refLabel}`;
          })
          .join("\n")
      : "";
  return `${answer || ""}${refLines}`;
}

const DEFAULT_REMINDERS = [
  { method: "popup", minutes: 15 },
  { method: "email", minutes: 60 },
];

export default function CalendarModal({
  question,
  answer,
  references,
  onSubmit,
  onClose,
  submitting,
}) {
  const initialStart = useMemo(() => {
    const date = new Date();
    date.setMinutes(date.getMinutes() + 30);
    date.setSeconds(0, 0);
    return date;
  }, []);

  const initialEnd = useMemo(() => {
    const date = new Date(initialStart);
    date.setHours(date.getHours() + 1);
    return date;
  }, [initialStart]);

  const [summary, setSummary] = useState(
    question?.slice(0, 150) || "Buổi học mới"
  );
  const [description, setDescription] = useState(
    buildDescription(answer, references)
  );
  const [timezone, setTimezone] = useState("Asia/Ho_Chi_Minh");
  const [start, setStart] = useState(formatDateForInput(initialStart));
  const [end, setEnd] = useState(formatDateForInput(initialEnd));
  const [reminders, setReminders] = useState(DEFAULT_REMINDERS);
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    const startDate = new Date(start);
    const endDate = new Date(end);
    if (!(startDate instanceof Date) || isNaN(startDate.getTime())) {
      setError("Thời gian bắt đầu không hợp lệ.");
      return;
    }
    if (!(endDate instanceof Date) || isNaN(endDate.getTime())) {
      setError("Thời gian kết thúc không hợp lệ.");
      return;
    }
    if (endDate <= startDate) {
      setError("Thời gian kết thúc phải sau thời gian bắt đầu.");
      return;
    }

    onSubmit({
      summary: summary.trim() || "Buổi học mới",
      description: description?.trim(),
      timezone,
      start: new Date(startDate).toISOString(),
      end: new Date(endDate).toISOString(),
      reminders,
    });
  };

  const handleReminderChange = (index, key, value) => {
    setReminders((prev) =>
      prev.map((item, idx) =>
        idx === index
          ? {
              ...item,
              [key]: key === "minutes" ? Number(value) : value,
            }
          : item
      )
    );
  };

  const handleAddReminder = () => {
    setReminders((prev) => [...prev, { method: "popup", minutes: 5 }]);
  };

  const handleRemoveReminder = (index) => {
    setReminders((prev) => prev.filter((_, idx) => idx !== index));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 overflow-y-auto max-h-[90vh]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-800">
            Tạo lịch học từ câu trả lời
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
            type="button"
            disabled={submitting}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tiêu đề sự kiện
            </label>
            <input
              type="text"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              maxLength={200}
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bắt đầu
              </label>
              <input
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Kết thúc
              </label>
              <input
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Múi giờ
            </label>
            <input
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Ví dụ: Asia/Ho_Chi_Minh, UTC, Asia/Bangkok
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Mô tả
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Nhắc nhở
              </label>
              <button
                type="button"
                className="text-sm text-purple-600 hover:text-purple-700"
                onClick={handleAddReminder}
              >
                + Thêm nhắc nhở
              </button>
            </div>
            {reminders.length === 0 && (
              <p className="text-sm text-gray-500">
                Không có nhắc nhở nào. Sự kiện sẽ dùng mặc định của Google
                Calendar.
              </p>
            )}
            <div className="space-y-3">
              {reminders.map((reminder, idx) => (
                <div
                  key={`${reminder.method}-${idx}`}
                  className="flex items-center space-x-3"
                >
                  <select
                    value={reminder.method}
                    onChange={(e) =>
                      handleReminderChange(idx, "method", e.target.value)
                    }
                    className="rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    <option value="popup">Thông báo trên màn hình</option>
                    <option value="email">Email</option>
                  </select>
                  <input
                    type="number"
                    min={0}
                    max={40320}
                    value={reminder.minutes}
                    onChange={(e) =>
                      handleReminderChange(idx, "minutes", e.target.value)
                    }
                    className="w-24 rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  <span className="text-sm text-gray-600">phút trước</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveReminder(idx)}
                    className="text-sm text-red-500 hover:text-red-600"
                  >
                    Xóa
                  </button>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-gray-600 hover:text-gray-800 transition"
              disabled={submitting}
            >
              Hủy
            </button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Đang tạo..." : "Tạo sự kiện"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

