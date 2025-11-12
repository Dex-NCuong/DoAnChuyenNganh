import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import Card from "../components/Card";
import Button from "../components/Button";
import ConnectCalendarModal from "../components/ConnectCalendarModal";
import {
  fetchCalendarStatus,
  getCalendarConnectUrl,
  disconnectCalendar,
} from "../services/calendarApi";

export default function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [calendarStatus, setCalendarStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadCalendarStatus();

    // Check for OAuth callback
    const calendarParam = searchParams.get("calendar");
    if (calendarParam === "connected") {
      setMessage("Đã kết nối Google Calendar thành công!");
      setSearchParams({});
      loadCalendarStatus();
    } else if (calendarParam === "error") {
      const reason = searchParams.get("reason");
      setMessage(
        `Kết nối Google Calendar thất bại: ${reason || "Lỗi không xác định"}`
      );
      setSearchParams({});
    }
  }, [searchParams, setSearchParams]);

  const loadCalendarStatus = async () => {
    setLoading(true);
    try {
      const status = await fetchCalendarStatus();
      setCalendarStatus(status);
    } catch (err) {
      console.error("Failed to load calendar status:", err);
      setCalendarStatus({ connected: false });
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    setShowConnectModal(true);
  };

  const handleDisconnect = async () => {
    if (
      !confirm(
        "Bạn có chắc muốn ngắt kết nối Google Calendar? Bạn sẽ không thể tạo lịch học từ câu trả lời nữa."
      )
    ) {
      return;
    }

    setDisconnecting(true);
    try {
      await disconnectCalendar();
      setMessage("Đã ngắt kết nối Google Calendar thành công!");
      await loadCalendarStatus();
    } catch (err) {
      setMessage(
        err?.response?.data?.detail ||
          "Không thể ngắt kết nối. Vui lòng thử lại."
      );
    } finally {
      setDisconnecting(false);
    }
  };

  const handleChangeAccount = async () => {
    // Disconnect first, then connect again
    if (
      !confirm(
        "Bạn muốn thay đổi tài khoản Google Calendar? Tài khoản hiện tại sẽ bị ngắt kết nối."
      )
    ) {
      return;
    }

    setDisconnecting(true);
    try {
      await disconnectCalendar();
      setMessage("Đã ngắt kết nối. Vui lòng kết nối tài khoản mới.");
      await loadCalendarStatus();
      setShowConnectModal(true);
    } catch (err) {
      setMessage(
        err?.response?.data?.detail ||
          "Không thể ngắt kết nối. Vui lòng thử lại."
      );
    } finally {
      setDisconnecting(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-8">
        <div className="flex items-center mb-2">
          <span className="text-4xl mr-3">⚙️</span>
          <h2 className="text-4xl font-bold text-gray-800">Cài đặt</h2>
        </div>
        <p className="text-gray-600 ml-12">
          Quản lý các tùy chọn và tích hợp của tài khoản
        </p>
      </div>

      {message && (
        <div
          className={`mb-6 p-4 rounded-lg border ${
            message.includes("thành công")
              ? "bg-green-50 border-green-200 text-green-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          <div className="flex items-center justify-between">
            <span>{message}</span>
            <button
              onClick={() => setMessage("")}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <Card className="mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-xl font-semibold text-gray-800 mb-2 flex items-center">
              <span className="mr-2">📅</span>
              Google Calendar
            </h3>
            <p className="text-sm text-gray-600">
              Kết nối Google Calendar để tạo lịch học từ câu trả lời
            </p>
          </div>
        </div>

        {loading ? (
          <div className="py-4 text-center text-gray-500">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <div className="font-medium text-gray-800 mb-1">
                  Trạng thái kết nối:
                </div>
                <div className="flex items-center space-x-2">
                  {calendarStatus?.connected ? (
                    <>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        ✓ Đã kết nối
                      </span>
                      {calendarStatus?.connected_at && (
                        <span className="text-xs text-gray-500">
                          Kết nối lúc: {formatDate(calendarStatus.connected_at)}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      Chưa kết nối
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              {calendarStatus?.connected ? (
                <>
                  <Button
                    onClick={handleDisconnect}
                    disabled={disconnecting}
                    variant="danger"
                    className="text-sm"
                  >
                    {disconnecting ? "Đang ngắt kết nối..." : "Ngắt kết nối"}
                  </Button>
                  <Button
                    onClick={handleChangeAccount}
                    disabled={disconnecting}
                    variant="secondary"
                    className="text-sm"
                  >
                    Thay đổi tài khoản
                  </Button>
                </>
              ) : (
                <Button onClick={handleConnect} className="text-sm">
                  Kết nối Google Calendar
                </Button>
              )}
            </div>

            {calendarStatus?.connected && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Lưu ý:</strong> Bạn có thể thay đổi tài khoản Google
                  Calendar bất cứ lúc nào bằng cách nhấn "Thay đổi tài khoản".
                  Tài khoản hiện tại sẽ bị ngắt kết nối và bạn sẽ được yêu cầu
                  đăng nhập với tài khoản mới.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

      {showConnectModal && (
        <ConnectCalendarModal
          onClose={() => {
            setShowConnectModal(false);
            loadCalendarStatus();
          }}
        />
      )}
    </div>
  );
}

