import React, { useState, useEffect, useRef } from "react";
import {
  askQuestion,
  listDocuments,
  getHistory,
  deleteHistory,
  deleteConversation,
} from "../services/api";
import Button from "../components/Button";
import CalendarButton from "../components/CalendarButton";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
function Message({ message, isUser, previousMessage }) {
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
        let extracted = extractString(value.answer);
        // CRITICAL FIX: If extracted string contains JSON structure, extract just the text
        if (typeof extracted === "string") {
          // Check if it's a JSON string (starts with { or contains JSON fields)
          if (
            extracted.trim().startsWith("{") &&
            extracted.includes('"answer"')
          ) {
            try {
              const parsed = JSON.parse(extracted);
              if (parsed && typeof parsed === "object" && parsed.answer) {
                extracted = String(parsed.answer);
                console.log("[Message] Extracted answer from JSON string");
              }
            } catch (e) {
              // If JSON parse fails, try to extract answer field manually
              const match = extracted.match(
                /"answer"\s*:\s*"((?:[^"\\]|\\.|\\n)*)"/
              );
              if (match) {
                try {
                  extracted = JSON.parse('"' + match[1] + '"');
                  console.log(
                    "[Message] Extracted answer from escaped JSON string"
                  );
                } catch (e2) {
                  // Fallback: manual unescape
                  extracted = match[1]
                    .replace(/\\n/g, "\n")
                    .replace(/\\"/g, '"')
                    .replace(/\\\\/g, "\\");
                }
              }
            }
          }
          // Check if it contains escaped JSON format like: "answer": "...", "answer_type": "..."
          else if (
            extracted.includes('"answer"') &&
            extracted.includes('"answer_type"')
          ) {
            // Try to extract just the answer field value
            const match = extracted.match(
              /"answer"\s*:\s*"((?:[^"\\]|\\.|\\n)*)"/
            );
            if (match) {
              try {
                extracted = JSON.parse('"' + match[1] + '"');
                console.log("[Message] Extracted answer from JSON-like string");
              } catch (e) {
                // Fallback: manual unescape
                extracted = match[1]
                  .replace(/\\n/g, "\n")
                  .replace(/\\"/g, '"')
                  .replace(/\\\\/g, "\\");
              }
            }
          }
        }
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
  // CRITICAL: Detect table format FIRST, then numbered lists
  let hasTable = false;
  let hasNumberedList = false;

  if (messageText && typeof messageText === "string") {
    // CRITICAL: Detect if answer contains a table FIRST
    hasTable =
      messageText.includes("|") && /\|.*\|.*\n\|[-:]+\|/.test(messageText);

    // Only detect numbered list if NOT a table
    // FIXED: Detect both "1. **" and "1.  **" (with single or double space)
    hasNumberedList =
      !hasTable &&
      /\d+\.\s+\*\*/.test(messageText) &&
      (messageText.match(/\d+\.\s+\*\*/g) || []).length >= 2;

    // Pre-process: Fix formatting ONLY if not a table
    if (hasNumberedList) {
      // CRITICAL: Ensure TRIPLE newlines for ReactMarkdown to recognize blank lines
      // ReactMarkdown needs \n\n\n (or more) to create separate <p> tags
      messageText = messageText.replace(/([^\n])\s+(\d+\.\s+)/g, "$1\n\n\n$2");
      messageText = messageText.replace(
        /(\d+\.\s+[^\n]+?)\s+(\d+\.\s+)/g,
        "$1\n\n\n$2"
      );
      messageText = messageText.replace(
        /(\d+\.\s+[^\n]+)\n(?!\n)(\d+\.\s+)/g,
        "$1\n\n\n$2"
      );

      // Clean up: Remove excessive newlines (keep max 3)
      messageText = messageText.replace(/\n{4,}/g, "\n\n\n");
      // Remove leading newlines
      messageText = messageText.replace(/^\n+/, "");

      console.log(`[Message] Fixed numbered list with triple newlines`);

      // DEBUG: Log first 500 chars to check newlines
      console.log(
        `[Message] First 500 chars after fix:`,
        messageText.substring(0, 500)
      );
      console.log(
        `[Message] Newline count:`,
        (messageText.match(/\n/g) || []).length
      );
      console.log(
        `[Message] Triple newline count:`,
        (messageText.match(/\n\n\n/g) || []).length
      );
      console.log(
        `[Message] Double newline count:`,
        (messageText.match(/\n\n/g) || []).length
      );
    } else if (hasTable) {
      // For tables, preserve exact formatting from backend
      console.log("[Message] Table detected, preserving format");
    }

    if (!hasTable) {
      // Only apply cleanup if there's no table (to preserve table format)
      // Remove patterns like [CHUNKS_USED: 1, 2, 3] or CHUNKS_USED: 1, 2, 3
      messageText = messageText
        .replace(/\[?CHUNKS_USED:\s*[\d,\s]+\]?/gi, "")
        .trim();

      // Remove chunk references like "(chunk 76)", "chunk 76", "(chunk 265, 273)", etc.
      // Pattern: (chunk X) or chunk X or (chunk X, Y, Z) - case insensitive
      messageText = messageText
        // Remove chunk references with parentheses: (chunk 76), (chunk 265, 273)
        .replace(/\(\s*chunk\s+\d+(?:\s*,\s*\d+)*\s*\)/gi, "")
        // Remove chunk references without parentheses: chunk 76, chunk 265, 273
        .replace(/\s+chunk\s+\d+(?:\s*,\s*\d+)*/gi, "")
        // Clean up extra spaces, commas, and parentheses left behind
        .replace(/\s*,\s*,/g, ",") // Double commas
        .replace(/\s*,\s*\./g, ".") // Comma before period
        .replace(/\s*,\s*\)/g, ")") // Comma before closing paren
        .replace(/\(\s*,/g, "(") // Opening paren with comma
        .replace(/\(\s*\)/g, "") // Empty parentheses
        .replace(/\s*\(\s*/g, " (") // Space before opening paren
        .replace(/\s{2,}/g, " ") // Multiple spaces
        .replace(/^\s*,\s*/, "") // Leading comma
        .replace(/\s*,\s*$/, "") // Trailing comma
        .trim();
    } else {
      // If table exists, remove CHUNKS_USED pattern AND citations from table cells
      // Split by lines to process table rows separately
      const lines = messageText.split("\n");
      const cleanedLines = lines
        .map((line) => {
          // Check if this is a table row (contains | but not separator row)
          if (line.includes("|") && !/^\|[-:|\s]+\|/.test(line.trim())) {
            // This is a table data row
            // Remove CHUNKS_USED pattern
            let cleaned = line.replace(/\[?CHUNKS_USED:\s*[\d,\s]+\]?/gi, "");
            // Remove citations in table cells: "(từ [filename], chunk X)" or "(từ chunk X)"
            // Pattern 1: "(từ filename.pdf, chunk X)" or "(từ filename.pdf, chunk X, Y, Z)"
            cleaned = cleaned.replace(
              /\(từ\s+[^,)]+,\s*chunk\s+\d+(?:\s*,\s*\d+)*\s*\)/gi,
              ""
            );
            // Pattern 2: "(từ chunk X)" or "(từ chunk X, Y, Z)" (fallback for old format)
            cleaned = cleaned.replace(
              /\(từ\s+chunk\s+\d+(?:\s*,\s*\d+)*\s*\)/gi,
              ""
            );
            // Remove standalone chunk references at end of cell: "chunk X" or "chunk X, Y, Z"
            // Match chunk reference before | or at end of line
            cleaned = cleaned.replace(
              /\s+chunk\s+\d+(?:\s*,\s*\d+)*\s*(?=\||$)/gi,
              ""
            );
            // Clean up extra spaces but preserve table structure
            cleaned = cleaned.replace(/\s{2,}/g, " ");
            return cleaned;
          } else if (hasTable && line.trim() && !line.trim().startsWith("|")) {
            // This is text after table (like conclusion) - also remove citations
            let cleaned = line;
            // Pattern 1: "(từ [filename], chunk X)" or "(từ [filename], chunk X, Y, Z)"
            cleaned = cleaned.replace(
              /\(từ\s+[^,)]+,\s*chunk\s+\d+(?:\s*,\s*\d+)*\s*\)/gi,
              ""
            );
            // Pattern 2: "(từ chunk X)" or "(từ chunk X, Y, Z)" (fallback)
            cleaned = cleaned.replace(
              /\(từ\s+chunk\s+\d+(?:\s*,\s*\d+)*\s*\)/gi,
              ""
            );
            // Remove standalone chunk references at end of sentences
            cleaned = cleaned.replace(
              /\s+chunk\s+\d+(?:\s*,\s*\d+)*\s*(?=[\.\n]|$)/gi,
              ""
            );
            // Clean up extra spaces
            cleaned = cleaned.replace(/\s{2,}/g, " ");
            return cleaned;
          } else if (
            /^\s*\*\*?Nguồn tham khảo:?\*\*?\s*/i.test(line) ||
            /^\s*Nguồn tham khảo:?\s*/i.test(line)
          ) {
            // This is "Nguồn tham khảo:" line - remove it
            return null;
          }
          return line;
        })
        .filter((line) => line !== null);

      messageText = cleanedLines
        .join("\n")
        // Remove "Nguồn tham khảo:" lines that might remain
        .replace(
          /\n\s*\*\*?Nguồn tham khảo:?\*\*?\s*[^\n]*(?:chunk\s+\d+(?:\s*,\s*\d+)*)*\s*/gi,
          ""
        )
        .replace(
          /\n\s*Nguồn tham khảo:?\s*[^\n]*(?:chunk\s+\d+(?:\s*,\s*\d+)*)*\s*/gi,
          ""
        )
        // Clean up extra empty lines
        .replace(/\n{3,}/g, "\n\n")
        .trim();
    }
  }

  const calendarMetadata = !isUser ? message?.calendarMetadata || {} : {};
  const calendarQuestion =
    calendarMetadata.question ||
    (previousMessage && previousMessage.isUser ? previousMessage.text : "");
  const calendarAnswer = calendarMetadata.answer || messageText;
  const calendarReferences =
    message.references || calendarMetadata.references || [];

  // Bubble hiển thị trạng thái AI đang suy nghĩ
  if (!isUser && message && message.isTyping) {
    return (
      <div className="mb-6">
        <div className="inline-block max-w-[85%] rounded-2xl px-4 py-3 bg-gray-100 text-gray-800">
          <div className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce delay-150" />
            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce delay-300" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`mb-6 ${isUser ? "text-right" : ""}`}>
      <div
        className={`inline-block max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-800"
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap leading-relaxed text-left">
            {messageText}
          </div>
        ) : (
          <>
            <div className="prose prose-sm max-w-none leading-relaxed">
              {messageText && typeof messageText === "string" ? (
                hasNumberedList ? (
                  // Manual render for numbered lists to ensure spacing
                  <div>
                    {(() => {
                      // CRITICAL: Split BEFORE ReactMarkdown processes it
                      // Use regex to split by numbered items pattern
                      // FIXED: Match both "1. **" and "1.  **" (single or double space)
                      // CRITICAL: Use negative lookbehind to avoid splitting "10. **" into "1" and "0. **"
                      // Pattern: (?<!\d) ensures we don't match if there's a digit before (e.g., "10" -> don't match "1")
                      const introMatch = messageText.match(
                        /^(.*?)(?<!\d)(?=\d+\.\s+\*\*)/s
                      );
                      const intro = introMatch ? introMatch[1].trim() : "";

                      // Split by numbered items: "1. **", "2. **", "10. **", etc.
                      // FIXED: Use negative lookbehind (?<!\d) to ensure we match complete numbers
                      // This prevents "10. **" from being split into "1" and "0. **"
                      const itemsText = messageText.substring(intro.length);
                      const items = itemsText
                        .split(/(?<!\d)(?=\d+\.\s+\*\*)/)
                        .map((s) => s.trim()) // Trim each item immediately
                        .filter((s) => s.length > 0); // CRITICAL: Filter empty strings

                      console.log(
                        `[Message] Intro length: ${intro.length}, Items: ${items.length}`
                      );

                      // Build sections array, filtering empty intro
                      const sections = [];
                      if (intro && intro.trim().length > 0) {
                        sections.push(intro.trim());
                      }
                      sections.push(...items);

                      // CRITICAL: Filter empty sections BEFORE mapping
                      const validSections = sections.filter(
                        (s) => s && s.trim().length > 0
                      );

                      console.log(
                        `[Message] Total sections: ${sections.length}, Valid sections: ${validSections.length}`
                      );

                      return validSections.map((section, idx) => {
                        const trimmed = section.trim();
                        // Double-check: should never be empty at this point
                        if (!trimmed || trimmed.length === 0) {
                          console.warn(
                            `[Message] Empty section at index ${idx}`
                          );
                          return null;
                        }

                        // FIXED: Match both "1. **" and "1.  **" (single or double space)
                        // Use negative lookbehind to ensure we match complete numbers
                        const isNumbered = /^(?<!\d)\d+\.\s+\*\*/.test(trimmed);

                        console.log(
                          `[Message] Section ${idx}: numbered=${isNumbered}, length=${
                            trimmed.length
                          }, text="${trimmed.substring(0, 50)}"`
                        );

                        // For numbered items, render manually to preserve the number
                        if (isNumbered) {
                          // Extract number and rest of text
                          const match = trimmed.match(/^(\d+\.\s+)(\*\*.*)/);
                          if (match) {
                            const [, number, rest] = match;
                            return (
                              <div
                                key={idx}
                                className="mb-6 border-l-4 border-purple-200 pl-4 py-2"
                              >
                                <p className="leading-7 text-gray-700 m-0">
                                  <span className="font-semibold text-gray-900">
                                    {number}
                                  </span>
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                      p: ({ node, ...props }) => (
                                        <span {...props} />
                                      ),
                                      strong: ({ node, ...props }) => (
                                        <strong
                                          className="font-bold text-gray-900"
                                          {...props}
                                        />
                                      ),
                                    }}
                                  >
                                    {rest}
                                  </ReactMarkdown>
                                </p>
                              </div>
                            );
                          }
                        }

                        // For non-numbered items (intro), use ReactMarkdown normally
                        return (
                          <div key={idx} className="mb-3">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                p: ({ node, ...props }) => (
                                  <p
                                    className="leading-7 text-gray-700 m-0"
                                    {...props}
                                  />
                                ),
                                strong: ({ node, ...props }) => (
                                  <strong
                                    className="font-bold text-gray-900"
                                    {...props}
                                  />
                                ),
                              }}
                            >
                              {trimmed}
                            </ReactMarkdown>
                          </div>
                        );
                      });
                    })()}
                  </div>
                ) : (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[]}
                    components={{
                      // Custom styling for markdown elements - Technical document format
                      h1: ({ node, ...props }) => (
                        <h1
                          className="text-2xl font-bold mb-4 mt-6 text-gray-900 border-b-2 border-gray-300 pb-2"
                          {...props}
                        />
                      ),
                      h2: ({ node, ...props }) => (
                        <h2
                          className="text-xl font-bold mb-3 mt-5 text-gray-800 border-b border-gray-200 pb-1.5"
                          {...props}
                        />
                      ),
                      h3: ({ node, ...props }) => (
                        <h3
                          className="text-lg font-semibold mb-2 mt-4 text-gray-700"
                          {...props}
                        />
                      ),
                      p: ({ node, ...props }) => (
                        <p
                          className="mb-3 leading-7 text-gray-700"
                          {...props}
                        />
                      ),
                      ul: ({ node, ...props }) => (
                        <ul
                          className="list-disc list-outside mb-4 space-y-2 ml-6"
                          {...props}
                        />
                      ),
                      ol: ({ node, ...props }) => (
                        <ol
                          className="list-decimal list-outside mb-4 space-y-2 ml-6"
                          {...props}
                        />
                      ),
                      li: ({ node, ...props }) => (
                        <li
                          className="ml-2 leading-6 text-gray-700"
                          {...props}
                        />
                      ),
                      strong: ({ node, ...props }) => (
                        <strong
                          className="font-bold text-gray-900"
                          {...props}
                        />
                      ),
                      em: ({ node, ...props }) => (
                        <em className="italic text-gray-700" {...props} />
                      ),
                      hr: ({ node, ...props }) => (
                        <hr className="my-4 border-gray-300" {...props} />
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
                        <div className="overflow-x-auto my-4 rounded-lg border border-gray-300 shadow-sm">
                          <table
                            className="min-w-full border-collapse bg-white"
                            {...props}
                          />
                        </div>
                      ),
                      thead: ({ node, ...props }) => (
                        <thead className="bg-gray-100" {...props} />
                      ),
                      tbody: ({ node, ...props }) => <tbody {...props} />,
                      tr: ({ node, ...props }) => (
                        <tr
                          className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
                          {...props}
                        />
                      ),
                      th: ({ node, ...props }) => (
                        <th
                          className="border-r border-gray-300 px-4 py-3 bg-gray-100 font-bold text-left text-gray-800"
                          {...props}
                        />
                      ),
                      td: ({ node, ...props }) => (
                        <td
                          className="border-r border-gray-300 px-4 py-3 text-gray-700"
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
                )
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
            {!isUser && calendarQuestion && calendarAnswer && (
              <CalendarButton
                question={calendarQuestion}
                answer={calendarAnswer}
                references={calendarReferences}
              />
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
  const [selectedDocs, setSelectedDocs] = useState([]); // ← THAY ĐỔI: Array thay vì string
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState("");
  const [showDocumentSelector, setShowDocumentSelector] = useState(true); // State để ẩn/hiện phần chọn tài liệu
  const [contextMenu, setContextMenu] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [newTitle, setNewTitle] = useState("");
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const chatTitleCache = useRef({}); // Cache for custom titles
  const pendingUserMessageRef = useRef(null);
  const pendingTypingMessageRef = useRef(null);
  const abortControllerRef = useRef(null);
  const activeRequestIdRef = useRef(null); // Để bỏ qua kết quả nếu đã bấm Hủy
  const cancelTimestampRef = useRef(null); // Track when user canceled to cleanup orphaned conversations

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

  // Auto-resize textarea when question changes
  useEffect(() => {
    if (textareaRef.current) {
      // Reset height to auto to get the correct scrollHeight
      textareaRef.current.style.height = "auto";
      // Set height based on scrollHeight, but max at 200px
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [question]);

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
        const references = h.references || [];
        const document_ids = Array.from(
          new Set(
            references.map((ref) => ref.document_id).filter((docId) => !!docId)
          )
        );
        convGroups[convId].push({
          ...h,
          document_ids,
        });
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
        const questionText = String(record.question || "");
        const answerText = String(record.answer || "");
        const references = record.references || [];
        const documentIds = Array.from(
          new Set(
            references.map((ref) => ref.document_id).filter((docId) => !!docId)
          )
        );
        allMessages.push({ text: questionText, isUser: true });
        allMessages.push({
          text: answerText,
          isUser: false,
          references,
          calendarMetadata: {
            question: questionText,
            answer: answerText,
            references,
            documentId: record.document_id || null,
            documentIds,
            historyId: record.id,
            conversationId: record.conversation_id || conversationId,
          },
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
            calendarMetadata: {
              question: String(conversation.question || ""),
              answer: String(conversation.answer || ""),
              references: conversation.references || [],
              documentId: conversation.document_id || null,
              documentIds: Array.from(
                new Set(
                  (conversation.references || [])
                    .map((ref) => ref.document_id)
                    .filter((docId) => !!docId)
                )
              ),
              historyId: conversation.id,
              conversationId: conversation.id,
            },
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
    if (!question.trim() || loading) return;

    // Kiểm tra bắt buộc phải chọn tài liệu
    if (!selectedDocs || selectedDocs.length === 0) {
      // ← THAY ĐỔI
      setError("Vui lòng chọn ít nhất một tài liệu trước khi gửi câu hỏi");
      return;
    }

    // Limit: tối đa 5 documents
    if (selectedDocs.length > 5) {
      // ← THÊM
      setError("Chỉ có thể chọn tối đa 5 tài liệu cùng lúc");
      return;
    }

    setLoading(true);
    setError("");

    const submittedQuestion = String(question || "");
    const requestId = `req-${Date.now()}`;
    activeRequestIdRef.current = requestId;

    console.log(`[ChatNew] ===== Starting new request ${requestId} =====`);
    console.log(`[ChatNew] Question: "${submittedQuestion}"`);
    console.log(`[ChatNew] Selected documents: ${selectedDocs.length} file(s)`); // ← THAY ĐỔI
    console.log(`[ChatNew] Active conversation: ${activeConversationId}`);

    // Nếu vẫn còn message tạm từ lần trước (do lỗi nào đó), dọn sạch trước
    if (pendingUserMessageRef.current || pendingTypingMessageRef.current) {
      console.log(`[ChatNew] Cleaning up old pending messages`);
      setMessages((prev) => {
        // Filter by isPending and isTyping flags instead of IDs
        const filtered = prev.filter((m) => !m.isPending && !m.isTyping);
        console.log(
          `[ChatNew] Cleaned up ${
            prev.length - filtered.length
          } old pending messages`
        );
        return filtered;
      });
      pendingUserMessageRef.current = null;
      pendingTypingMessageRef.current = null;
    }

    // Tạo message tạm thời cho user + bubble đang gõ cho lần request mới
    const userMessage = {
      id: `user-${Date.now()}`,
      text: submittedQuestion,
      isUser: true,
      isPending: true,
      requestId: requestId, // Track which request this belongs to
    };
    const typingMessage = {
      id: `typing-${Date.now()}`,
      isUser: false,
      isTyping: true,
      requestId: requestId, // Track which request this belongs to
    };

    pendingUserMessageRef.current = userMessage;
    pendingTypingMessageRef.current = typingMessage;

    console.log(
      `[ChatNew] Created pending messages - User: ${userMessage.id}, Typing: ${typingMessage.id}`
    );
    setMessages((prev) => [...prev, userMessage, typingMessage]);

    // Tạo AbortController để có thể hủy request
    const controller = new AbortController();
    abortControllerRef.current = controller;

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
        submittedQuestion,
        selectedDocs, // ← THAY ĐỔI: Pass array thay vì single ID
        conversationIdForBackend,
        controller.signal
      );

      console.log(`[ChatNew] Received response for request ${requestId}`);
      console.log(`[ChatNew] Active request ID: ${activeRequestIdRef.current}`);
      console.log(
        `[ChatNew] Response conversation_id: ${result.conversation_id}`
      );
      console.log(`[ChatNew] Response history_id: ${result.history_id}`);

      // Nếu request này đã bị hủy trong lúc chờ thì bỏ qua kết quả
      if (activeRequestIdRef.current !== requestId) {
        console.log(
          `[ChatNew] ⚠️ Response received for CANCELED request ${requestId}, IGNORING and NOT saving to state`
        );
        console.log(
          `[ChatNew] ⚠️ This response should NOT create a new conversation or message`
        );

        // CRITICAL: Make sure we don't save this to history or state
        // Just return immediately without any state updates
        return;
      }

      // Get conversation_id from response (backend returns it)
      const returnedConversationId =
        result.conversation_id || result.history_id;

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
        // Loại bỏ các message tạm thời (user + typing) trước khi append kết quả thật
        const messagesToAppendTo = (() => {
          const base =
            messages.length > 0 && activeConversationId === targetConversationId
              ? messages
              : conversationMessagesRef.current[targetConversationId] || [];
          // Filter by isPending and isTyping flags instead of IDs
          return base.filter((m) => !m.isPending && !m.isTyping);
        })();

        console.log(
          `[ChatNew] Appending to conversation ${targetConversationId}`
        );
        console.log(
          `[ChatNew] Current messages count: ${messages.length}, Ref count: ${
            conversationMessagesRef.current[targetConversationId]?.length || 0
          }, Active conversation: ${activeConversationId}`
        );

        const references = result.references || [];
        const documentIds = Array.from(
          new Set(
            references.map((ref) => ref.document_id).filter((docId) => !!docId)
          )
        );
        // THÊM: Log documents được search vs documents có references
        const documentsSearched = result.documents_searched || selectedDocs;
        console.log(
          `[ChatNew] Documents searched: ${documentsSearched.length}, Documents with refs: ${documentIds.length}`
        );
        const newMessages = [
          ...messagesToAppendTo,
          { text: submittedQuestion, isUser: true },
          {
            text: String(result.answer || ""), // ✅ Đảm bảo luôn là string
            isUser: false,
            references, // ✅ Thêm references
            calendarMetadata: {
              question: submittedQuestion,
              answer: String(result.answer || ""),
              references,
              documentId: null, // ← DEPRECATED: không dùng nữa
              documentIds, // ← THAY ĐỔI: Dùng array
              historyId: result.history_id,
              conversationId: returnedConversationId || targetConversationId,
            },
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
          references,
          created_at: new Date().toISOString(),
          document_id: selectedDocs[0] || null, // ← THAY ĐỔI: Use first doc for backward compatibility
          conversation_id: returnedConversationId || targetConversationId,
          document_ids: documentIds,
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
        const references = result.references || [];
        const documentIds = Array.from(
          new Set(
            references.map((ref) => ref.document_id).filter((docId) => !!docId)
          )
        );
        const newConversation = {
          id: finalConversationId,
          question: question,
          answer: result.answer,
          references,
          created_at: new Date().toISOString(),
          document_id: selectedDoc || null,
          title: null,
          document_ids: documentIds,
        };

        // Update messages
        const initialMessages = [
          { text: submittedQuestion, isUser: true },
          {
            text: String(result.answer || ""), // ✅ Đảm bảo luôn là string
            isUser: false,
            references,
            calendarMetadata: {
              question: submittedQuestion,
              answer: String(result.answer || ""),
              references,
              documentId: selectedDoc || null,
              documentIds,
              historyId: result.history_id,
              conversationId: finalConversationId,
            },
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
          references,
          created_at: new Date().toISOString(),
          document_id: selectedDoc || null,
          conversation_id: finalConversationId,
          document_ids: documentIds,
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
      pendingUserMessageRef.current = null;
      pendingTypingMessageRef.current = null;
      abortControllerRef.current = null;
      activeRequestIdRef.current = null;
    } catch (err) {
      console.log(`[ChatNew] ===== Request ${requestId} FAILED =====`);
      console.log(`[ChatNew] Error:`, err);

      // Nếu request bị hủy thì không hiện lỗi
      const isCanceled =
        err?.code === "ERR_CANCELED" ||
        err?.name === "CanceledError" ||
        (typeof err?.message === "string" &&
          err.message.toLowerCase().includes("canceled"));

      console.log(`[ChatNew] Is canceled: ${isCanceled}`);

      if (!isCanceled) {
        setError(err?.response?.data?.detail || "Gửi câu hỏi thất bại");
      } else {
        console.log(
          `[ChatNew] Request was canceled by user, not showing error`
        );
      }

      // Xoá các message tạm thời nếu có và đưa lại câu hỏi về ô input
      if (pendingUserMessageRef.current || pendingTypingMessageRef.current) {
        console.log(
          `[ChatNew] Restoring question to input and removing pending messages`
        );

        if (pendingUserMessageRef.current?.text) {
          setQuestion(pendingUserMessageRef.current.text);
        }

        setMessages((prev) => {
          // Filter by isPending and isTyping flags instead of IDs
          // This is more reliable as IDs might not match if state changed
          const filtered = prev.filter((m) => !m.isPending && !m.isTyping);
          console.log(
            `[ChatNew] Removed ${
              prev.length - filtered.length
            } pending messages (before: ${prev.length}, after: ${
              filtered.length
            })`
          );
          return filtered;
        });
      }

      console.log(`[ChatNew] Cleaning up request ${requestId} state`);
      pendingUserMessageRef.current = null;
      pendingTypingMessageRef.current = null;
      abortControllerRef.current = null;
      activeRequestIdRef.current = null;
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    console.log(`[ChatNew] ===== USER CANCELED REQUEST =====`);
    console.log(
      `[ChatNew] Active request ID before cancel: ${activeRequestIdRef.current}`
    );
    console.log(`[ChatNew] Pending messages:`, {
      user: pendingUserMessageRef.current?.id,
      typing: pendingTypingMessageRef.current?.id,
    });

    if (abortControllerRef.current) {
      console.log(`[ChatNew] Aborting HTTP request`);
      abortControllerRef.current.abort();
    }

    setLoading(false);

    // CRITICAL: Clear activeRequestIdRef FIRST before cleaning up messages
    // This ensures that if response comes back, it will be ignored
    const canceledRequestId = activeRequestIdRef.current;
    activeRequestIdRef.current = null;
    console.log(
      `[ChatNew] Cleared active request ID (was: ${canceledRequestId})`
    );

    // Xoá câu hỏi + bubble typing đang chờ, đồng thời đưa lại câu hỏi về ô input
    if (pendingUserMessageRef.current || pendingTypingMessageRef.current) {
      console.log(
        `[ChatNew] Restoring question to input and removing pending messages`
      );

      if (pendingUserMessageRef.current?.text) {
        const restoredQuestion = pendingUserMessageRef.current.text;
        setQuestion(restoredQuestion);
        console.log(`[ChatNew] Restored question: "${restoredQuestion}"`);
      }

      setMessages((prev) => {
        // Filter by isPending and isTyping flags instead of IDs
        // This is more reliable as IDs might not match if state changed
        const filtered = prev.filter((m) => !m.isPending && !m.isTyping);
        console.log(
          `[ChatNew] Messages before: ${prev.length}, after: ${
            filtered.length
          }, removed: ${prev.length - filtered.length}`
        );
        return filtered;
      });
    }

    console.log(`[ChatNew] Cleaning up refs`);

    // Record the cancel timestamp for orphaned conversation cleanup
    const cancelTime = new Date();
    cancelTimestampRef.current = cancelTime;
    console.log(
      `[ChatNew] Recorded cancel timestamp: ${cancelTime.toISOString()}`
    );

    pendingUserMessageRef.current = null;
    pendingTypingMessageRef.current = null;
    abortControllerRef.current = null;
    console.log(`[ChatNew] ===== CANCEL COMPLETE =====`);

    // CRITICAL: Backend might have already created a history record before we canceled
    // Wait a bit and cleanup any orphaned conversations created around the cancel time
    console.log(`[ChatNew] Scheduling cleanup for orphaned conversations...`);

    // Save current conversation IDs before canceling
    const existingConvIds = new Set(conversations.map((c) => c.id));
    const currentActiveConvId = activeConversationId;
    console.log(
      `[ChatNew] State at cancel - Existing conversations: ${existingConvIds.size}, Active: ${currentActiveConvId}`
    );

    setTimeout(async () => {
      try {
        console.log(`[ChatNew] ===== CLEANUP STARTING (5s after cancel) =====`);
        console.log(`[ChatNew] Cancel timestamp: ${cancelTime.toISOString()}`);

        // Reload conversations to get any that were created during the canceled request
        const data = await getHistory(null, 100);
        console.log(
          `[ChatNew] Loaded ${data.length} history records from backend`
        );

        if (data.length === 0) {
          console.log(`[ChatNew] No history records found, skipping cleanup`);
          return;
        }

        // Find orphaned HISTORY RECORDS (not just conversations!)
        // IMPORTANT: A conversation can have multiple Q&As (history records)
        // When canceling in an existing conversation, backend creates a NEW history record
        // We need to delete that specific history record, not the entire conversation!

        const orphanedHistoryIds = [];
        const affectedConversationIds = new Set();

        data.forEach((h) => {
          const historyId = h.id;
          const convId = h.conversation_id || h.id;
          const createdAt = new Date(h.created_at);

          // Calculate time difference from cancel
          const timeSinceCancelMs = createdAt - cancelTime;

          // Window: -1s before to +6s after cancel
          // This captures history records from the canceled request
          // Backend can take 2-5s+ to process (embedding + LLM API + save DB)
          const withinCancelWindow =
            timeSinceCancelMs >= -1000 && timeSinceCancelMs <= 6000;

          console.log(
            `[ChatNew] History ${historyId.substring(0, 8)}...: ` +
              `conv=${convId.substring(0, 8)}..., ` +
              `time=${timeSinceCancelMs}ms, ` +
              `window=${withinCancelWindow}, ` +
              `created=${createdAt.toISOString()}`
          );

          // Mark as orphaned if created within cancel window
          if (withinCancelWindow) {
            orphanedHistoryIds.push(historyId);
            affectedConversationIds.add(convId);
            console.log(
              `[ChatNew] ⚠️ ORPHANED HISTORY: ${historyId}, ` +
                `created ${timeSinceCancelMs}ms relative to cancel`
            );
          }
        });

        if (orphanedHistoryIds.length > 0) {
          console.log(
            `[ChatNew] 🗑️ Deleting ${orphanedHistoryIds.length} orphaned history records:`,
            orphanedHistoryIds
          );

          // Delete each orphaned history record
          let deletedCount = 0;
          for (const historyId of orphanedHistoryIds) {
            try {
              await deleteHistory(historyId);
              deletedCount++;
              console.log(
                `[ChatNew] ✅ Deleted orphaned history: ${historyId}`
              );
            } catch (err) {
              console.error(
                `[ChatNew] ❌ Failed to delete history ${historyId}:`,
                err
              );
            }
          }

          if (deletedCount > 0) {
            // Reload conversations to update UI
            await loadConversations();
            console.log(
              `[ChatNew] ✅ Cleanup complete - deleted ${deletedCount} orphaned history records from ${affectedConversationIds.size} conversations`
            );

            // If current active conversation was affected, reload its messages
            if (affectedConversationIds.has(activeConversationId)) {
              console.log(
                `[ChatNew] Reloading messages for affected active conversation: ${activeConversationId}`
              );
              setTimeout(() => {
                loadConversationMessages(activeConversationId);
              }, 100);
            }
          }
        } else {
          console.log(`[ChatNew] ✅ No orphaned history records found`);
        }

        console.log(`[ChatNew] ===== CLEANUP COMPLETE =====`);
      } catch (err) {
        console.error(
          `[ChatNew] ❌ Error during orphaned conversation cleanup:`,
          err
        );
      }
    }, 7000); // Wait 7 seconds for backend to finish processing and save to DB (embedding + LLM can be slow)
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
              setSelectedDocs([]); // ← THAY ĐỔI: Clear array
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
                <Message
                  key={idx}
                  message={msg}
                  isUser={msg.isUser}
                  previousMessage={idx > 0 ? messages[idx - 1] : null}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="max-w-3xl mx-auto">
            {/* Multi-select documents dropdown */}
            <div className="mb-3">
              {/* Header với nút toggle */}
              <div className="flex items-center justify-between mb-2">
                <button
                  type="button"
                  onClick={() => setShowDocumentSelector(!showDocumentSelector)}
                  className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-purple-600 transition-colors"
                >
                  <span className="text-lg">
                    {showDocumentSelector ? "▼" : "▶"}
                  </span>
                  <span>📚 Chọn tài liệu</span>
                  {selectedDocs.length > 0 && (
                    <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs font-semibold">
                      {selectedDocs.length}
                    </span>
                  )}
                </button>
                {!showDocumentSelector && selectedDocs.length > 0 && (
                  <span className="text-xs text-gray-500">
                    Đã chọn: {selectedDocs.length} tài liệu
                  </span>
                )}
              </div>

              {/* Collapsible content */}
              {showDocumentSelector && (
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-gray-700 flex-shrink-0">
                    📚 Chọn tài liệu:
                  </label>

                  {/* Custom multi-select với checkboxes */}
                  <div className="flex-1 relative">
                    <select
                      multiple
                      value={selectedDocs}
                      onChange={(e) => {
                        const selected = Array.from(
                          e.target.selectedOptions,
                          (option) => option.value
                        );

                        // Limit: tối đa 5 documents
                        if (selected.length > 5) {
                          setError("Chỉ có thể chọn tối đa 5 tài liệu");
                          return;
                        }

                        setSelectedDocs(selected);
                        setError(""); // Clear error nếu valid
                        console.log(
                          `[ChatNew] Selected ${selected.length} document(s)`
                        );
                      }}
                      className="w-full px-3 py-2 text-sm border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none"
                      style={{ minHeight: "80px" }}
                    >
                      {documents.map((doc) => (
                        <option
                          key={doc.id}
                          value={doc.id}
                          className="py-2 px-2 hover:bg-purple-50 cursor-pointer"
                        >
                          {selectedDocs.includes(doc.id) ? "✓ " : "  "}
                          {doc.filename}
                        </option>
                      ))}
                    </select>

                    {/* Display selected count */}
                    {selectedDocs.length > 0 && (
                      <div className="mt-1 flex items-center justify-between text-xs">
                        <span className="text-purple-600 font-medium">
                          Đã chọn: {selectedDocs.length} tài liệu
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedDocs([]);
                            setError("");
                          }}
                          className="text-gray-500 hover:text-red-600 underline"
                        >
                          Bỏ chọn tất cả
                        </button>
                      </div>
                    )}

                    {/* Helper text */}
                    <p className="mt-1 text-xs text-gray-500">
                      💡 Giữ Ctrl/Cmd để chọn nhiều tài liệu (tối đa 5)
                    </p>
                  </div>
                </div>
              )}
            </div>
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Hỏi bất kỳ điều gì..."
                  rows={1}
                  disabled={loading}
                  className="w-full px-4 py-3 pr-12 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none resize-none disabled:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
                  style={{
                    minHeight: "52px",
                    maxHeight: "200px",
                    overflowY: "auto",
                  }}
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
                    className="absolute right-2 top-3 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                    title="Xóa câu hỏi"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>

              {/* Nút Gửi / Dừng riêng biệt - như ChatGPT */}
              {loading ? (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium transition-all flex items-center gap-2 shadow-lg hover:shadow-xl"
                  title="Dừng câu hỏi đang gửi"
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <rect x="6" y="6" width="12" height="12" strokeWidth={2} />
                  </svg>
                  Dừng
                </button>
              ) : (
                <Button
                  type="submit"
                  disabled={!question.trim()}
                  className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
                >
                  Gửi
                </Button>
              )}
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
