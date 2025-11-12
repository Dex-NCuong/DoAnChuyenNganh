import React, { useMemo, useState } from "react";
import CalendarModal from "./CalendarModal";
import ConnectCalendarModal from "./ConnectCalendarModal";
import {
  createCalendarEvent,
  fetchCalendarStatus,
} from "../services/calendarApi";

function buildReferenceMetadata(references = []) {
  const uniqueDocs = new Map();
  references.forEach((ref) => {
    if (!ref.document_id) return;
    if (!uniqueDocs.has(ref.document_id)) {
      uniqueDocs.set(ref.document_id, ref.document_filename || "Tài liệu");
    }
  });
  const docIds = Array.from(uniqueDocs.keys());
  const summary =
    uniqueDocs.size === 0
      ? ""
      : Array.from(uniqueDocs.values()).join(", ");
  return { summary, docIds };
}

export default function CalendarButton({
  question,
  answer,
  references,
  onSuccess,
}) {
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState("");

  const referenceInfo = useMemo(
    () => buildReferenceMetadata(references),
    [references]
  );

  const handleOpen = async () => {
    setLoading(true);
    setFeedback("");
    try {
      const status = await fetchCalendarStatus();
      if (status?.connected) {
        setShowCalendarModal(true);
      } else {
        setShowConnectModal(true);
      }
    } catch (err) {
      setFeedback(
        err?.response?.data?.detail ||
          "Không thể kiểm tra trạng thái Google Calendar."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEvent = async (payload) => {
    setSubmitting(true);
    setFeedback("");
    try {
      const event = await createCalendarEvent({
        ...payload,
        event_type: "study_session",
        document_ids: referenceInfo.docIds,
      });
      setShowCalendarModal(false);
      setFeedback("Đã tạo sự kiện trên Google Calendar.");
      if (onSuccess) {
        onSuccess(event);
      }
    } catch (err) {
      setFeedback(
        err?.response?.data?.detail ||
          "Không thể tạo sự kiện Google Calendar. Vui lòng thử lại."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const disabled = !question || !answer;

  return (
    <>
      <div className="mt-3 flex items-center space-x-2">
        <button
          onClick={handleOpen}
          disabled={loading || submitting || disabled}
          className={`inline-flex items-center px-3 py-1.5 text-sm border rounded-full transition ${
            disabled
              ? "border-gray-200 text-gray-400 cursor-not-allowed"
              : "border-purple-200 text-purple-600 hover:bg-purple-50"
          }`}
        >
          <span className="mr-2">📅</span>
          {loading
            ? "Đang kiểm tra..."
            : submitting
            ? "Đang xử lý..."
            : "Thêm vào lịch"}
        </button>
        {feedback && (
          <span className="text-xs text-gray-500 max-w-[220px]">
            {feedback}
          </span>
        )}
      </div>
      {showConnectModal && (
        <ConnectCalendarModal onClose={() => setShowConnectModal(false)} />
      )}
      {showCalendarModal && (
        <CalendarModal
          question={question}
          answer={answer}
          references={references}
          submitting={submitting}
          onSubmit={handleCreateEvent}
          onClose={() => setShowCalendarModal(false)}
        />
      )}
    </>
  );
}

