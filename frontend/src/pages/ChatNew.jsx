import React, { useState, useEffect, useRef } from "react";
import {
  askQuestion,
  listDocuments,
  getHistory,
  deleteHistory,
  deleteConversation,
} from "../services/api";
import Button from "../components/Button";
import ReactMarkdown from "react-markdown";

// Context Menu Component
function ContextMenu({ x, y, onRename, onDelete, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="fixed bg-white rounded-lg shadow-xl border border-gray-200 py-2 z-50 min-w-[160px]"
      style={{ left: x, top: y }}
    >
      <button
        onClick={() => {
          onRename();
          onClose();
        }}
        className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
      >
        <span className="mr-2">✏️</span> Đổi tên
      </button>
      <button
        onClick={() => {
          onDelete();
          onClose();
        }}
        className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center"
      >
        <span className="mr-2">🗑️</span> Xóa
      </button>
    </div>
  );
}

// Chat Item in Sidebar
function ChatItem({ conversation, isActive, onClick, onMenuClick }) {
  const [isHovered, setIsHovered] = useState(false);
  const title =
    conversation.title || conversation.question || "Cuộc trò chuyện mới";

  return (
    <div
      className={`group relative px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
        isActive
          ? "bg-purple-100 text-purple-900"
          : "hover:bg-gray-100 text-gray-700"
      }`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {new Date(conversation.created_at).toLocaleDateString("vi-VN")}
          </p>
        </div>
        {isHovered && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onMenuClick(e);
            }}
            className="ml-2 p-1 rounded hover:bg-gray-200 opacity-70 hover:opacity-100"
          >
            <span className="text-gray-600">⋯</span>
          </button>
        )}
      </div>
    </div>
  );
}

// Helper function để format citation
function formatCitation(ref) {
  if (!ref.document_file_type) {
    return "Nguồn tài liệu";
  }

  const fileType = ref.document_file_type.toLowerCase();

  // PDF: chỉ hiển thị "Trang X"
  if (fileType === "pdf" && ref.page_number) {
    return `Trang ${ref.page_number}`;
  }

  // DOCX/DOC/MD/TXT: hiển thị section/heading trực tiếp (không thêm tiền tố "Mục:")
  if (
    fileType === "docx" ||
    fileType === "doc" ||
    fileType === "md" ||
    fileType === "txt"
  ) {
    if (ref.section) {
      // Truncate nếu quá dài
      const sectionText =
        ref.section.length > 50
          ? ref.section.substring(0, 50) + "..."
          : ref.section;
      return sectionText;
    }
  }

  // Fallback: nếu không có thông tin cụ thể
  return "Nguồn tài liệu";
}

function getFileIcon(fileType) {
  const icons = {
    pdf: "📄",
    docx: "📝",
    md: "📋",
    txt: "📄",
  };
  return icons[fileType] || "📄";
}

// Citations Component
function Citations({ references }) {
  if (!references || references.length === 0) return null;

  // Group by document
  const grouped = references.reduce((acc, ref) => {
    const key = ref.document_id;
    if (!acc[key]) {
      acc[key] = {
        filename: ref.document_filename || "Tài liệu",
        file_type: ref.document_file_type,
        refs: [],
      };
    }
    acc[key].refs.push(ref);
    return acc;
  }, {});

  return (
    <div className="mt-3 pt-3 border-t border-gray-200">
      <div className="text-xs font-semibold text-gray-500 mb-2 flex items-center">
        <span className="mr-1">📚</span> Nguồn trích dẫn:
      </div>
      <div className="space-y-2">
        {Object.values(grouped).map((group, idx) => (
          <div key={idx} className="text-xs">
            <div className="font-medium text-gray-700 mb-1">
              {getFileIcon(group.file_type)} {group.filename}
            </div>
            <div className="ml-4 space-y-0.5">
              {group.refs.map((ref, refIdx) => (
                <div key={refIdx} className="text-gray-600">
                  {formatCitation(ref)}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Message Component
function Message({ message, isUser }) {
  // Đảm bảo messageText luôn là string thuần túy (không phải React element)
  let messageText = "";

  // Helper function để extract string từ bất kỳ giá trị nào
  const extractString = (value) => {
    if (value === null || value === undefined) return "";
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean")
      return String(value);
    // Nếu là object, kiểm tra xem có phải React element không
    if (typeof value === "object") {
      // Nếu có $$typeof, đây là React element - không thể render trực tiếp
      if (value.$$typeof) {
        console.warn(
          "[Message] Detected React element in message, skipping",
          value
        );
        return "";
      }
      // Nếu có text property
      if (value.text !== undefined) {
        const extracted = extractString(value.text);
        // Double check: nếu extracted vẫn là object, return empty
        if (typeof extracted === "object" && extracted.$$typeof) {
          console.warn("[Message] Extracted text is still a React element");
          return "";
        }
        return extracted;
      }
      // Nếu có answer property
      if (value.answer !== undefined) {
        const extracted = extractString(value.answer);
        // Double check: nếu extracted vẫn là object, return empty
        if (typeof extracted === "object" && extracted.$$typeof) {
          console.warn("[Message] Extracted answer is still a React element");
          return "";
        }
        return extracted;
      }
      // Thử JSON.stringify nếu là plain object
      try {
        return JSON.stringify(value);
      } catch {
        return "";
      }
    }
    return String(value || "");
  };

  messageText = extractString(message);

  // Final validation: đảm bảo messageText là string và không phải React element
  if (typeof messageText !== "string") {
    console.error(
      "[Message] messageText is not a string:",
      typeof messageText,
      messageText
    );
    messageText = "";
  }

  // Check if messageText contains React element (shouldn't happen but double check)
  if (messageText && typeof messageText === "object" && messageText.$$typeof) {
    console.error("[Message] messageText is a React element, clearing");
    messageText = "";
  }

  // Remove CHUNKS_USED pattern from message text (case insensitive)
  if (messageText && typeof messageText === "string") {
    // Remove patterns like [CHUNKS_USED: 1, 2, 3] or CHUNKS_USED: 1, 2, 3
    messageText = messageText
      .replace(/\[?CHUNKS_USED:\s*[\d,\s]+\]?/gi, "")
      .trim();
  }

  return (
    <div className={`mb-6 ${isUser ? "text-right" : ""}`}>
      <div
        className={`inline-block max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-800"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap leading-relaxed">
            {messageText}
          </div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none leading-relaxed">
              {messageText && typeof messageText === "string" ? (
                <ReactMarkdown
                  components={{
                    // Custom styling for markdown elements
                    h1: ({ node, ...props }) => (
                      <h1 className="text-xl font-bold mb-2 mt-4" {...props} />
                    ),
                    h2: ({ node, ...props }) => (
                      <h2 className="text-lg font-bold mb-2 mt-3" {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3
                        className="text-base font-bold mb-1 mt-2"
                        {...props}
                      />
                    ),
                    p: ({ node, ...props }) => (
                      <p className="mb-2" {...props} />
                    ),
                    ul: ({ node, ...props }) => (
                      <ul
                        className="list-disc list-inside mb-2 space-y-1"
                        {...props}
                      />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol
                        className="list-decimal list-inside mb-2 space-y-1"
                        {...props}
                      />
                    ),
                    li: ({ node, ...props }) => (
                      <li className="ml-4" {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                      <strong className="font-bold" {...props} />
                    ),
                    em: ({ node, ...props }) => (
                      <em className="italic" {...props} />
                    ),
                    code: ({ node, inline, ...props }) =>
                      inline ? (
                        <code
                          className="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono"
                          {...props}
                        />
                      ) : (
                        <code
                          className="block bg-gray-200 p-2 rounded text-sm font-mono overflow-x-auto mb-2"
                          {...props}
                        />
                      ),
                    pre: ({ node, ...props }) => (
                      <pre
                        className="bg-gray-200 p-2 rounded text-sm font-mono overflow-x-auto mb-2"
                        {...props}
                      />
                    ),
                    table: ({ node, ...props }) => (
                      <div className="overflow-x-auto mb-2">
                        <table
                          className="min-w-full border-collapse border border-gray-300"
                          {...props}
                        />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th
                        className="border border-gray-300 px-2 py-1 bg-gray-200 font-bold"
                        {...props}
                      />
                    ),
                    td: ({ node, ...props }) => (
                      <td
                        className="border border-gray-300 px-2 py-1"
                        {...props}
                      />
                    ),
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        className="border-l-4 border-gray-400 pl-4 italic my-2"
                        {...props}
                      />
                    ),
                    a: ({ node, ...props }) => (
                      <a
                        className="text-blue-600 underline"
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                      />
                    ),
                  }}
                >
                  {String(messageText)}
                </ReactMarkdown>
              ) : (
                <div className="text-gray-500 italic">No content available</div>
              )}
            </div>
            {message &&
              typeof message === "object" &&
              message.references &&
              message.references.length > 0 && (
                <Citations references={message.references} />
              )}
          </>
        )}
      </div>
    </div>
  );
}

export default function ChatNew() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null); // This is now conversation_id, not history_id
  const [messages, setMessages] = useState([]);
  const conversationIdMap = useRef({}); // Map conversation_id -> list of history records
  const [question, setQuestion] = useState("");
  const [selectedDoc, setSelectedDoc] = useState("");
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState("");
  const [contextMenu, setContextMenu] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const messagesEndRef = useRef(null);
  const chatTitleCache = useRef({}); // Cache for custom titles

  // Load titles from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("chatTitles");
      if (saved) {
        chatTitleCache.current = JSON.parse(saved);
      }
    } catch {
      chatTitleCache.current = {};
    }
  }, []);

  // Save titles to localStorage when they change
  const saveTitleToCache = (conversationId, title) => {
    if (title) {
      chatTitleCache.current[conversationId] = title;
    } else {
      delete chatTitleCache.current[conversationId];
    }
    localStorage.setItem("chatTitles", JSON.stringify(chatTitleCache.current));
  };

  // Load active conversation ID from localStorage on mount
  useEffect(() => {
    try {
      const savedActiveId = localStorage.getItem("activeConversationId");
      if (savedActiveId) {
        setActiveConversationId(savedActiveId);
      }
    } catch {
      // Ignore errors
    }
    loadDocuments();
    loadConversations();
  }, []);

  // Track if we're in a multi-message conversation
  const conversationMessagesRef = useRef({}); // conversationId -> messages array

  // Save activeConversationId to localStorage when it changes
  useEffect(() => {
    if (activeConversationId) {
      try {
        localStorage.setItem("activeConversationId", activeConversationId);
      } catch {
        // Ignore errors
      }
    }
  }, [activeConversationId]);

  // Use a ref to track the previous activeConversationId to avoid unnecessary reloads
  const prevActiveConversationIdRef = useRef(null);

  useEffect(() => {
    // Only reload messages if activeConversationId actually changed
    // Don't reload if we're just adding messages to the current conversation
    if (activeConversationId) {
      // Only reload if conversation actually changed (user clicked different conversation)
      if (prevActiveConversationIdRef.current !== activeConversationId) {
        console.log(
          `[ChatNew] Conversation changed from ${prevActiveConversationIdRef.current} to ${activeConversationId}`
        );

        // Check if we have cached messages for this conversation
        const hasCachedMessages =
          conversationMessagesRef.current[activeConversationId] &&
          conversationMessagesRef.current[activeConversationId].length > 0;

        if (hasCachedMessages) {
          // Use cached messages immediately
          console.log(
            `[ChatNew] Using cached messages for conversation ${activeConversationId}`
          );
          setMessages(conversationMessagesRef.current[activeConversationId]);
        } else {
          // Load messages from conversationIdMap or conversations list
          console.log(
            `[ChatNew] Loading messages for conversation ${activeConversationId}`
          );
          loadConversationMessages(activeConversationId);
        }

        // Update ref
        prevActiveConversationIdRef.current = activeConversationId;
      }
      // If conversation hasn't changed, don't do anything (preserve current messages)
    } else {
      // No active conversation, clear messages
      setMessages([]);
      prevActiveConversationIdRef.current = null;
    }
  }, [activeConversationId]); // Only depend on activeConversationId

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadDocuments = async () => {
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  const loadConversations = async () => {
    setLoadingHistory(true);
    try {
      const data = await getHistory(null, 100);

      // Group history records by conversation_id
      // Only group records that have the same conversation_id
      // Records without conversation_id will be treated as separate conversations
      const convGroups = {};
      data.forEach((h) => {
        // Only use conversation_id if it exists, otherwise use history_id as fallback
        // But this should not happen if backend sets conversation_id correctly
        const convId = h.conversation_id || h.id;
        if (!convGroups[convId]) {
          convGroups[convId] = [];
        }
        convGroups[convId].push(h);
      });

      // Store full conversation data
      Object.keys(convGroups).forEach((convId) => {
        conversationIdMap.current[convId] = convGroups[convId].sort(
          (a, b) => new Date(a.created_at) - new Date(b.created_at) // Sort by time, oldest first
        );
      });

      // Clean up: Remove conversations that no longer exist in backend
      const existingConvIds = new Set(Object.keys(convGroups));
      Object.keys(conversationIdMap.current).forEach((convId) => {
        if (!existingConvIds.has(convId)) {
          // Conversation was deleted, remove from cache
          delete conversationIdMap.current[convId];
          delete conversationMessagesRef.current[convId];
          delete chatTitleCache.current[convId];
          console.log(
            `[ChatNew] Removed deleted conversation ${convId} from cache`
          );

          // If deleted conversation was active, clear it
          if (activeConversationId === convId) {
            setActiveConversationId(null);
            setMessages([]);
            try {
              localStorage.removeItem("activeConversationId");
            } catch {}
          }
        }
      });

      // Create conversation list (one entry per conversation_id, using first Q&A as title)
      const convs = Object.keys(convGroups).map((convId) => {
        const records = convGroups[convId];
        const firstRecord = records[0]; // Oldest record
        const lastRecord = records[records.length - 1]; // Newest record

        return {
          id: convId, // conversation_id
          question: firstRecord.question, // First question for title
          answer: firstRecord.answer,
          references: firstRecord.references || [],
          created_at: firstRecord.created_at,
          document_id: firstRecord.document_id,
          title: chatTitleCache.current[convId] || null,
          messageCount: records.length, // Number of Q&As in this conversation
        };
      });

      // Sort by date (newest conversation first)
      convs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setConversations(convs);
      // Only set default activeConversationId if we don't have one saved
      if (convs.length > 0 && !activeConversationId) {
        // Check if we have a saved activeConversationId
        try {
          const savedActiveId = localStorage.getItem("activeConversationId");
          if (savedActiveId && convs.find((c) => c.id === savedActiveId)) {
            setActiveConversationId(savedActiveId);
          } else {
            setActiveConversationId(convs[0].id);
          }
        } catch {
          setActiveConversationId(convs[0].id);
        }
      }
    } catch (err) {
      setError("Không thể tải danh sách cuộc trò chuyện");
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadConversationMessages = (conversationId) => {
    console.log(
      `[ChatNew] Loading messages for conversation: ${conversationId}`
    );
    console.log(
      `[ChatNew] conversationIdMap keys:`,
      Object.keys(conversationIdMap.current)
    );

    // Load all Q&As in this conversation
    const historyRecords = conversationIdMap.current[conversationId] || [];

    if (historyRecords.length > 0) {
      console.log(
        `[ChatNew] Found ${historyRecords.length} records in conversationIdMap`
      );
      // Build messages from all Q&As in this conversation
      const allMessages = [];
      historyRecords.forEach((record) => {
        allMessages.push({ text: String(record.question || ""), isUser: true });
        allMessages.push({
          text: String(record.answer || ""), // ✅ Đảm bảo luôn là string
          isUser: false,
          references: record.references || [], // ✅ Thêm references
        });
      });
      setMessages(allMessages);
      // Store in ref for persistence
      conversationMessagesRef.current[conversationId] = allMessages;
    } else {
      console.log(
        `[ChatNew] No records in conversationIdMap, trying conversations list`
      );
      // Fallback: try to find from conversations list (backward compatibility)
      const conversation = conversations.find((c) => c.id === conversationId);
      if (conversation) {
        console.log(`[ChatNew] Found conversation in list, loading first Q&A`);
        const initialMessages = [
          { text: String(conversation.question || ""), isUser: true },
          {
            text: String(conversation.answer || ""), // ✅ Đảm bảo luôn là string
            isUser: false,
            references: conversation.references || [], // ✅ Thêm references
          },
        ];
        setMessages(initialMessages);
        conversationMessagesRef.current[conversationId] = initialMessages;

        // If conversationIdMap doesn't have this conversation, we might need to reload
        // But first try to load all history records for this conversation
        if (!conversationIdMap.current[conversationId]) {
          console.log(
            `[ChatNew] conversationIdMap missing data, reloading conversations`
          );
          // Reload to populate conversationIdMap
          loadConversations().then(() => {
            // After reload, try loading messages again
            const records = conversationIdMap.current[conversationId] || [];
            if (records.length > 0) {
              const allMessages = [];
              records.forEach((record) => {
                allMessages.push({
                  text: String(record.question || ""),
                  isUser: true,
                });
                allMessages.push({
                  text: String(record.answer || ""), // ✅ Đảm bảo luôn là string
                  isUser: false,
                  references: record.references || [], // ✅ Thêm references
                });
              });
              setMessages(allMessages);
              conversationMessagesRef.current[conversationId] = allMessages;
            }
          });
        }
      } else {
        console.log(`[ChatNew] Conversation not found in list`);
        setMessages([]);
        conversationMessagesRef.current[conversationId] = [];
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError("");

    try {
      // Send conversation_id if we're in an existing conversation
      // IMPORTANT: Include temp IDs too - they represent the active conversation
      const currentConversationId = activeConversationId
        ? activeConversationId
        : null;

      // But only send non-temp IDs to backend (backend doesn't know about temp IDs)
      const conversationIdForBackend =
        activeConversationId && !activeConversationId.startsWith("temp-")
          ? activeConversationId
          : null;

      const result = await askQuestion(
        question,
        selectedDoc || null,
        conversationIdForBackend
      );

      // Get conversation_id from response (backend returns it)
      const returnedConversationId =
        result.conversation_id || result.history_id;

      // Save question for later matching
      const submittedQuestion = question;

      // CRITICAL: Determine which conversation we should append to
      // Priority:
      // 1. If we have activeConversationId and backend returns the same ID -> append
      // 2. If we have activeConversationId and backend returns different ID -> still append to active (backend might be creating new, but we want to keep continuity)
      // 3. If backend returns ID that exists in our conversationIdMap -> append to that
      // 4. Otherwise -> create new conversation

      let targetConversationId = null;
      if (currentConversationId) {
        // We're in an active conversation, always use it
        targetConversationId = currentConversationId;
        console.log(
          `[ChatNew] Using active conversation: ${targetConversationId}, backend returned: ${returnedConversationId}`
        );
      } else if (
        returnedConversationId &&
        conversationIdMap.current[returnedConversationId]
      ) {
        // Backend returned a conversation_id that we already know about
        targetConversationId = returnedConversationId;
        console.log(
          `[ChatNew] Using existing conversation from backend: ${targetConversationId}`
        );
      } else if (returnedConversationId) {
        // Backend returned a new conversation_id
        targetConversationId = returnedConversationId;
        console.log(
          `[ChatNew] Using new conversation_id from backend: ${targetConversationId}`
        );
      }

      // If we have a target conversation, append to it
      if (targetConversationId) {
        // CRITICAL: Use current messages state OR ref to ensure we append to existing messages
        // Priority: use messages state if available and belong to target conversation
        const messagesToAppendTo =
          messages.length > 0 && activeConversationId === targetConversationId
            ? messages // Use current displayed messages if they belong to target conversation
            : conversationMessagesRef.current[targetConversationId] || [];

        console.log(
          `[ChatNew] Appending to conversation ${targetConversationId}`
        );
        console.log(
          `[ChatNew] Current messages count: ${messages.length}, Ref count: ${
            conversationMessagesRef.current[targetConversationId]?.length || 0
          }, Active conversation: ${activeConversationId}`
        );

        const newMessages = [
          ...messagesToAppendTo,
          { text: String(question || ""), isUser: true },
          {
            text: String(result.answer || ""), // ✅ Đảm bảo luôn là string
            isUser: false,
            references: result.references || [], // ✅ Thêm references
          },
        ];

        console.log(
          `[ChatNew] Appending to conversation ${targetConversationId}, new message count: ${newMessages.length}`
        );

        // Update state immediately
        setMessages(newMessages);

        // Store updated messages in ref
        conversationMessagesRef.current[targetConversationId] = newMessages;

        // Add new history record to conversationIdMap
        if (!conversationIdMap.current[targetConversationId]) {
          conversationIdMap.current[targetConversationId] = [];
        }
        conversationIdMap.current[targetConversationId].push({
          id: result.history_id,
          question: question,
          answer: result.answer,
          references: result.references || [],
          created_at: new Date().toISOString(),
          document_id: selectedDoc || null,
          conversation_id: returnedConversationId || targetConversationId,
        });

        // CRITICAL: Update activeConversationId to match the conversation we're appending to
        // This ensures the next question will append to the same conversation
        if (activeConversationId !== targetConversationId) {
          console.log(
            `[ChatNew] Updating activeConversationId from ${activeConversationId} to ${targetConversationId}`
          );
          setActiveConversationId(targetConversationId);
        }

        // If we had a temp ID and backend returned a real conversation_id, migrate everything
        if (
          targetConversationId.startsWith("temp-") &&
          returnedConversationId &&
          !returnedConversationId.startsWith("temp-")
        ) {
          console.log(
            `[ChatNew] Migrating from temp ID ${targetConversationId} to real ID ${returnedConversationId}`
          );

          // Migrate messages
          conversationMessagesRef.current[returnedConversationId] = newMessages;
          delete conversationMessagesRef.current[targetConversationId];

          // Migrate conversationIdMap
          if (conversationIdMap.current[targetConversationId]) {
            conversationIdMap.current[returnedConversationId] =
              conversationIdMap.current[targetConversationId];
            delete conversationIdMap.current[targetConversationId];
          }

          // Update activeConversationId to real ID
          setActiveConversationId(returnedConversationId);
          targetConversationId = returnedConversationId; // Update target for conversation list

          // Update conversations list - replace temp ID with real ID
          setConversations((prev) =>
            prev.map((c) =>
              c.id === targetConversationId
                ? { ...c, id: returnedConversationId }
                : c
            )
          );
        } else {
          // Update conversation in list if it exists
          setConversations((prev) => {
            const exists = prev.find((c) => c.id === targetConversationId);
            if (exists) {
              // Update existing conversation (update last message info)
              return prev.map((c) =>
                c.id === targetConversationId
                  ? {
                      ...c,
                      answer: result.answer,
                      created_at: new Date().toISOString(),
                      messageCount: (c.messageCount || 1) + 1,
                    }
                  : c
              );
            }
            return prev;
          });
        }

        // DO NOT reload conversations here - keep current state
      } else {
        // This is a completely NEW conversation (no activeConversationId at all)
        // Use the returned conversation_id from backend immediately
        const finalConversationId =
          returnedConversationId || `temp-${Date.now()}`;

        // CRITICAL: Set activeConversationId IMMEDIATELY to the returned conversation_id
        // This ensures the next question will use this conversation_id
        setActiveConversationId(finalConversationId);

        // Create conversation entry
        const newConversation = {
          id: finalConversationId,
          question: question,
          answer: result.answer,
          references: result.references || [],
          created_at: new Date().toISOString(),
          document_id: selectedDoc || null,
          title: null,
        };

        // Update messages
        const initialMessages = [
          { text: String(question || ""), isUser: true },
          {
            text: String(result.answer || ""), // ✅ Đảm bảo luôn là string
            isUser: false,
            references: result.references || [], // ✅ Thêm references
          },
        ];
        setMessages(initialMessages);
        conversationMessagesRef.current[finalConversationId] = initialMessages;

        // Store in conversationIdMap
        if (!conversationIdMap.current[finalConversationId]) {
          conversationIdMap.current[finalConversationId] = [];
        }
        conversationIdMap.current[finalConversationId].push({
          id: result.history_id,
          question: question,
          answer: result.answer,
          references: result.references || [],
          created_at: new Date().toISOString(),
          document_id: selectedDoc || null,
          conversation_id: finalConversationId,
        });

        // Update conversations list - check if conversation already exists
        setConversations((prev) => {
          const exists = prev.find((c) => c.id === finalConversationId);
          if (exists) {
            // Update existing conversation
            return prev.map((c) =>
              c.id === finalConversationId ? { ...c, ...newConversation } : c
            );
          } else {
            // Add new conversation at the top
            return [newConversation, ...prev];
          }
        });

        // For new conversations, we don't need to reload immediately
        // The conversation is already added to the list above
        // Only reload if needed (e.g., to get updated conversation_id mapping)
        // But avoid reloading to prevent resetting messages
      }

      setQuestion("");
    } catch (err) {
      setError(err?.response?.data?.detail || "Gửi câu hỏi thất bại");
    } finally {
      setLoading(false);
    }
  };

  const handleContextMenu = (e, conversationId) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      conversationId,
    });
  };

  const handleRename = (conversationId) => {
    const conversation = conversations.find((c) => c.id === conversationId);
    if (conversation) {
      setRenamingId(conversationId);
      setNewTitle(
        chatTitleCache.current[conversationId] ||
          conversation.question.substring(0, 50)
      );
    }
  };

  const saveRename = (conversationId) => {
    if (newTitle.trim()) {
      saveTitleToCache(conversationId, newTitle.trim());
      // Update conversation title in state
      setConversations((prev) =>
        prev.map((c) =>
          c.id === conversationId ? { ...c, title: newTitle.trim() } : c
        )
      );
    }
    setRenamingId(null);
    setNewTitle("");
  };

  const handleDelete = async (conversationId) => {
    if (!confirm("Bạn có chắc muốn xóa cuộc trò chuyện này?")) return;

    try {
      // Delete all history records in this conversation
      await deleteConversation(conversationId);

      // Clean up local state immediately
      // Remove from cache
      saveTitleToCache(conversationId, undefined);

      // Remove from conversationIdMap
      delete conversationIdMap.current[conversationId];

      // Remove from conversationMessagesRef
      delete conversationMessagesRef.current[conversationId];

      // Remove from conversations list
      setConversations((prev) => prev.filter((c) => c.id !== conversationId));

      // If deleted conversation was active, select first one or clear
      if (activeConversationId === conversationId) {
        // Get remaining conversations after deletion
        const remaining = conversations.filter((c) => c.id !== conversationId);
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].id);
          // Wait a bit for state to update, then load messages
          setTimeout(() => {
            loadConversationMessages(remaining[0].id);
          }, 100);
        } else {
          setActiveConversationId(null);
          setMessages([]);
          // Clear from localStorage
          try {
            localStorage.removeItem("activeConversationId");
          } catch {}
        }
      }

      // Reload conversations to sync with backend
      await loadConversations();

      // Show success message (optional)
      console.log(
        `[ChatNew] Successfully deleted conversation ${conversationId}`
      );
    } catch (err) {
      // If 404, conversation already deleted - treat as success
      if (err?.response?.status === 404) {
        // Clean up local state anyway
        saveTitleToCache(conversationId, undefined);
        delete conversationIdMap.current[conversationId];
        delete conversationMessagesRef.current[conversationId];
        setConversations((prev) => prev.filter((c) => c.id !== conversationId));

        if (activeConversationId === conversationId) {
          const remaining = conversations.filter(
            (c) => c.id !== conversationId
          );
          if (remaining.length > 0) {
            setActiveConversationId(remaining[0].id);
            setTimeout(() => {
              loadConversationMessages(remaining[0].id);
            }, 100);
          } else {
            setActiveConversationId(null);
            setMessages([]);
            try {
              localStorage.removeItem("activeConversationId");
            } catch {}
          }
        }
        await loadConversations();
        console.log(`[ChatNew] Conversation ${conversationId} already deleted`);
        return; // Success - conversation already deleted
      }

      console.error("Delete conversation error:", err);
      setError(err?.response?.data?.detail || "Xóa thất bại");
    }
  };

  const getConversationTitle = (conversation) => {
    return (
      conversation.title ||
      conversation.question.substring(0, 50) +
        (conversation.question.length > 50 ? "..." : "")
    );
  };

  return (
    <div className="flex h-[calc(100vh-80px)] bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-200 flex-shrink-0">
          <button
            onClick={() => {
              setActiveConversationId(null);
              setMessages([]);
              setQuestion("");
              setSelectedDoc("");
            }}
            className="w-full px-4 py-2.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center"
          >
            <span className="mr-2">✏️</span> Đoạn chat mới
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 min-h-0">
          <div className="mb-2 px-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Đoạn chat
          </div>
          {loadingHistory ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
            </div>
          ) : conversations.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">
              Chưa có cuộc trò chuyện nào
            </p>
          ) : (
            <div className="space-y-1">
              {conversations.map((conv) => (
                <div key={conv.id}>
                  {renamingId === conv.id ? (
                    <div className="px-3 py-2">
                      <input
                        type="text"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        onBlur={() => saveRename(conv.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            saveRename(conv.id);
                          } else if (e.key === "Escape") {
                            setRenamingId(null);
                            setNewTitle("");
                          }
                        }}
                        className="w-full px-2 py-1 text-sm border border-purple-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-500"
                        autoFocus
                      />
                    </div>
                  ) : (
                    <ChatItem
                      conversation={conv}
                      isActive={activeConversationId === conv.id}
                      onClick={() => {
                        setActiveConversationId(conv.id);
                        // Immediately load messages for this conversation
                        loadConversationMessages(conv.id);
                      }}
                      onMenuClick={(e) => handleContextMenu(e, conv.id)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 border-b border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-2xl">
                <div className="text-6xl mb-4">🧠</div>
                <h2 className="text-3xl font-bold text-gray-800 mb-4">
                  Bạn đang làm về cái gì?
                </h2>
                <p className="text-gray-600 mb-8">
                  Hãy đặt câu hỏi về tài liệu của bạn để nhận được câu trả lời
                  thông minh từ AI.
                </p>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto">
              {messages.map((msg, idx) => (
                <Message key={idx} message={msg} isUser={msg.isUser} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="max-w-3xl mx-auto">
            <div className="mb-3">
              <select
                value={selectedDoc}
                onChange={(e) => setSelectedDoc(e.target.value)}
                className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none"
              >
                <option value="">Tất cả tài liệu</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.filename}
                  </option>
                ))}
              </select>
            </div>
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Hỏi bất kỳ điều gì..."
                  rows={1}
                  disabled={loading}
                  className="w-full px-4 py-3 pr-12 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none resize-none max-h-32 disabled:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !loading) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                />
                {question.trim() && !loading && (
                  <button
                    type="button"
                    onClick={() => setQuestion("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                    title="Xóa câu hỏi"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
              <Button
                type="submit"
                disabled={loading || !question.trim()}
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
              >
                {loading ? <span className="animate-spin">⏳</span> : "Gửi"}
              </Button>
            </form>
          </div>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onRename={() => handleRename(contextMenu.conversationId)}
          onDelete={() => {
            handleDelete(contextMenu.conversationId);
            setContextMenu(null);
          }}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
