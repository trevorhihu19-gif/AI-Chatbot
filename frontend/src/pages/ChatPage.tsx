import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  Mic,
  Paperclip,
  Globe,
  Database,
  Loader2,
  Menu,
} from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import type { Citation, Message, Props, ChatInputProps } from "../Types/chat.ts";

// ── Message Components ──────────────────────────────────────────────────────
function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end px-2 w-full">
      <div
        className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-br-md outline-none"
        style={{
          background: "#1c1c1c",
          border: "1px solid #282828",
          color: "#e8e8e8",
          padding: "10px 18px",
          fontSize: "15px",
          lineHeight: "1.6",
          wordBreak: "break-word",
        }}
      >
        {content}
      </div>
    </div>
  );
}

function AssistantMessage({ message }: { message: Message }) {
  return (
    <div className="max-w-3xl mx-auto w-full px-4 sm:px-6 md:px-8 flex flex-col items-center">
      <div className="min-w-0 w-full max-w-3xl">
        {/* Thinking dots */}
        {!message.content && message.isStreaming && (
          <div className="flex items-center gap-1.5 py-3">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-2 h-2 rounded-full"
                style={{ background: "#444" }}
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        )}

        {/*  Response Text with  Markdown Parsing */}
        {message.content && (
          <div className="text-[15px] leading-[1.75] prose prose-invert max-w-none w-full block clearfix font-normal tracking-normal text-[#d0d0d0]">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-5 last:mb-0 text-left clear-both w-full">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 mb-5 space-y-2 clear-both w-full">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 mb-5 space-y-2 clear-both w-full">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="text-[#c8c8c8] pl-0.5">{children}</li>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-white">
                    {children}
                  </strong>
                ),
                code: ({ children }) => (
                  <code className="px-1.5 py-0.5 rounded text-[13.5px] bg-[#161616] border border-[#222] font-mono text-[#00d4aa]">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="p-4 rounded-xl bg-[#111] border border-[#1c1c1c] overflow-x-auto my-5 text-[14px] leading-relaxed font-mono">
                    {children}
                  </pre>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>

            {/* Pulsing Text Cursor */}
            {message.isStreaming && (
              <span
                className="inline-block ml-1 align-middle rounded-sm animate-pulse"
                style={{
                  background: "#00d4aa",
                  width: "2px",
                  height: "15px",
                }}
              />
            )}
          </div>
        )}

        {/* Tool badges */}
        {message.toolsUsed && message.toolsUsed.length > 0 && (
          <div className="flex gap-2 mt-4 flex-wrap">
            {message.toolsUsed.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11.5px]"
                style={{
                  background: "rgba(0,212,170,0.06)",
                  border: "1px solid rgba(0,212,170,0.12)",
                  color: "#00a882",
                }}
              >
                {t.includes("web") ? (
                  <Globe size={10} />
                ) : (
                  <Database size={10} />
                )}
                {t.includes("web") ? "Searched web" : "Searched docs"}
              </span>
            ))}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-5 space-y-2">
            <p
              className="text-[11px] font-semibold uppercase tracking-wider"
              style={{ color: "#555" }}
            >
              Sources
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {message.citations.slice(0, 4).map((c) => (
                <div
                  key={c.index}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-xl"
                  style={{ background: "#111", border: "1px solid #1c1c1c" }}
                >
                  <span
                    className="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-semibold shrink-0 mt-0.5"
                    style={{
                      background: "rgba(0,212,170,0.1)",
                      color: "#00d4aa",
                    }}
                  >
                    {c.index}
                  </span>
                  <div className="min-w-0">
                    <p
                      className="text-[12px] font-medium truncate"
                      style={{ color: "#888" }}
                    >
                      {c.title || c.filename || "Source"}
                    </p>
                    <p
                      className="text-[11.5px] mt-0.5 line-clamp-2"
                      style={{ color: "#555" }}
                    >
                      {c.snippet}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolIndicator({ tool }: { tool: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex items-center gap-2.5 pl-11 pr-2"
      style={{ color: "#444" }}
    >
      <Loader2
        size={12}
        className="animate-spin shrink-0"
        style={{ color: "#00a882" }}
      />
      <span className="text-[13px]">
        {tool.includes("web")
          ? "Searching the web…"
          : "Reading your documents…"}
      </span>
    </motion.div>
  );
}

// ── Shared Input Component ─────────────────────────────────────────────────



function ChatInput({
  input,
  setInput,
  loading,
  webSearch,
  setWebSearch,
  ragSearch,
  setRagSearch,
  onKeyDown,
  onSend,
  placeholder = "Message Surge…",
  maxWClass = "max-w-3xl",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  return (
    <div
      className={`w-full transition-all duration-150 rounded-2xl mx-auto p-3 flex flex-col justify-between${maxWClass}`}
      style={{
        background: "#161616",
        border: "1px solid #252525",
        boxShadow: "0 4px 24px rgba(0,0,0,0.5)",
      }}
      onFocusCapture={(e) => (e.currentTarget.style.borderColor = "#333")}
      onBlurCapture={(e) => (e.currentTarget.style.borderColor = "#252525")}
    >
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={1}
        className="w-full bg-transparent outline-none resize-none"
        style={{
          color: "#e0e0e0",
          minHeight: 52,
          maxHeight: 200,
          caretColor: "#00d4aa",
          paddingLeft: "24px",
          paddingRight: "24px",
          paddingTop: "16px",
          fontSize: "15px",
        }}
      />

      <div className="flex items-center justify-between px-1 pt-2">
        <div className="flex items-center gap-1">
          <button
            className="p-2 rounded-full transition-colors"
            style={{ color: "#555" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#aaa")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#555")}
          >
            <Paperclip size={16} />
          </button>

          <button
            onClick={() => setWebSearch((p) => !p)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[13px] font-medium transition-all"
            style={{
              color: webSearch ? "#00e6b8" : "#666",
              background: webSearch ? "rgba(0,230,184,0.1)" : "transparent",
              border: webSearch
                ? "1px solid rgba(0,230,184,0.25)"
                : "1px solid transparent",
            }}
          >
            <Globe size={14} />
            Web
          </button>

          <button
            onClick={() => setRagSearch((p) => !p)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[13px] font-medium transition-all"
            style={{
              color: ragSearch ? "#00e6b8" : "#666",
              background: ragSearch ? "rgba(0,230,184,0.1)" : "transparent",
              border: ragSearch
                ? "1px solid rgba(0,230,184,0.25)"
                : "1px solid transparent",
            }}
          >
            <Database size={14} />
            Docs
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            className="p-2 rounded-full transition-colors"
            style={{ color: "#555" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#aaa")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#555")}
          >
            <Mic size={15} />
          </button>
          <button
            onClick={onSend}
            disabled={!input.trim() || loading}
            className="w-8 h-8 rounded-full flex items-center justify-center transition-all duration-150 shrink-0"
            style={{
              background: input.trim() && !loading ? "#00e699ff" : "#1e1e1e",
              cursor: input.trim() && !loading ? "pointer" : "default",
            }}
          >
            {loading ? (
              <Loader2
                size={13}
                className="animate-spin"
                style={{ color: "#444" }}
              />
            ) : (
              <ArrowUp
                size={15}
                style={{ color: input.trim() ? "#000" : "#3a3a3a" }}
                strokeWidth={2.5}
              />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Chat Page Component ────────────────────────────────────────────────

export default function ChatPage({
  currentConvId,
  setCurrentConvId,
  onNewConversation,
  onOpenSidebar,
}: Props) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [webSearch, setWebSearch] = useState(false);
  const [ragSearch, setRagSearch] = useState(true);

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const getTokenRef = useRef(getToken);
  useEffect(() => {
    getTokenRef.current = getToken;
  }, [getToken]);

  useEffect(() => {
    if (!currentConvId) {
      setMessages([]);
      setFetchingHistory(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    
    setMessages([]);
    setFetchingHistory(true);

    const fetchChatHistory = async () => {
      try {
        const token = await getTokenRef.current();

        const res = await fetch(`/api/v1/chat/conversations/${currentConvId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

        const data = await res.json();

        if (data && data.messages) {
          const mappedMessages: Message[] = data.messages.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            citations: m.citations,
            toolsUsed: m.tools_used,
          }));
          setMessages(mappedMessages);
        }
      } catch (err: any) {
        if (err.name !== "AbortError") {
          console.error("Error loading chat history:", err);
        }
      } finally {
        if (!controller.signal.aborted) {
          setFetchingHistory(false);
        }
      }
    };

    fetchChatHistory();

    return () => {
      controller.abort();
    };
  }, [currentConvId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTools]);

  const send = async (text?: string) => {
    const rawText = typeof text === "string" ? text : input;
    const msg = rawText.trim();
    if (!msg || loading) return;

    setInput("");
    setLoading(true);
    setActiveTools([]);

    const uid = `u-${Date.now()}`;
    const aid = `a-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      { id: uid, role: "user", content: msg },
      {
        id: aid,
        role: "assistant",
        content: "",
        isStreaming: true,
        toolsUsed: [],
        citations: [],
      },
    ]);

    try {
      const token = await getToken();
      const res = await fetch("/api/v1/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: msg,
          conversation_id: currentConvId,
          use_web_search: webSearch,
          use_rag: ragSearch,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      const toolsUsed: string[] = [];
      const allCitations: Citation[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const chunk = JSON.parse(raw);
            if (chunk.type === "metadata" && chunk.conversation_id) {
              const isNew = !currentConvId;
              setCurrentConvId(chunk.conversation_id);
              if (isNew) onNewConversation();
            } else if (chunk.type === "token") {
              setMessages((p) =>
                p.map((m) =>
                  m.id === aid
                    ? { ...m, content: m.content + chunk.content }
                    : m,
                ),
              );
            } else if (chunk.type === "tool_start") {
              setActiveTools((p) => [...p, chunk.tool_name]);
            } else if (chunk.type === "tool_end") {
              setActiveTools((p) => p.filter((t) => t !== chunk.tool_name));
              if (chunk.tool_name && !toolsUsed.includes(chunk.tool_name))
                toolsUsed.push(chunk.tool_name);
              if (chunk.citations) allCitations.push(...chunk.citations);
            } else if (chunk.type === "done") {
              if (chunk.citations) allCitations.push(...chunk.citations);
              setMessages((p) =>
                p.map((m) =>
                  m.id === aid
                    ? {
                        ...m,
                        isStreaming: false,
                        toolsUsed,
                        citations: allCitations,
                      }
                    : m,
                ),
              );
              setActiveTools([]);
            } else if (chunk.type === "error") {
              setMessages((p) =>
                p.map((m) =>
                  m.id === aid
                    ? {
                        ...m,
                        content: "Something went wrong. Please try again.",
                        isStreaming: false,
                      }
                    : m,
                ),
              );
            }
          } catch {
            /* skip */
          }
        }
      }
    } catch {
      setMessages((p) =>
        p.map((m) =>
          m.id === aid
            ? {
                ...m,
                content: "Connection error. Is the backend running?",
                isStreaming: false,
              }
            : m,
        ),
      );
    } finally {
      setLoading(false);
      setActiveTools([]);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-full" style={{ background: "#0d0d0d" }}>
      {/* Mobile top bar */}
      <div
        className="flex items-center gap-3 px-4 py-3 shrink-0 lg:hidden"
        style={{ borderBottom: "1px solid #1a1a1a" }}
      >
        <button
          onClick={onOpenSidebar}
          className="p-2 rounded-lg transition-colors"
          style={{ color: "#555" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#aaa")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#555")}
        >
          <Menu size={18} />
        </button>
        <span style={{ color: "#888", fontSize: 14, fontWeight: 600 }}>
          Surge
        </span>
      </div>

      {/* Content Stream */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          /* ── Welcome Screen ── */
          <div
            className="flex flex-col items-center justify-center h-full px-6"
            style={{ maxWidth: 720, margin: "0 auto", width: "100%" }}
          >
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="w-full"
            >
              <div className="mb-8 text-center">
                <h1
                  className="text-[28px] sm:text-[34px] font-semibold tracking-tight mb-2"
                  style={{ color: "#e8e8e8" }}
                >
                  Good day. What can I help with?
                </h1>
              </div>

              <ChatInput
                input={input}
                setInput={setInput}
                loading={loading}
                webSearch={webSearch}
                setWebSearch={setWebSearch}
                ragSearch={ragSearch}
                setRagSearch={setRagSearch}
                onKeyDown={onKey}
                onSend={send}
                placeholder="How can I help you today?"
              />
            </motion.div>
          </div>
        ) : (
          /* ── Chat Messages ── */
          <div className="max-w-3xl mx-auto w-full px-4 py-10 space-y-8">
            <AnimatePresence>
              {messages.map((m) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  {m.role === "user" ? (
                    <UserMessage content={m.content} />
                  ) : (
                    <AssistantMessage message={m} />
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            <AnimatePresence>
              {activeTools.map((t) => (
                <ToolIndicator key={t} tool={t} />
              ))}
            </AnimatePresence>

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Floating Footer Input ── */}
      {hasMessages && (
        <div
          className="shrink-0 pb-6 pt-2 w-full flex flex-col items-center justify-center px-4"
          style={{
            background: "linear-gradient(to top, #0d0d0d 70%, transparent)",
          }}
        >
          <ChatInput
            input={input}
            setInput={setInput}
            loading={loading}
            webSearch={webSearch}
            setWebSearch={setWebSearch}
            ragSearch={ragSearch}
            setRagSearch={setRagSearch}
            onKeyDown={onKey}
            onSend={send}
            maxWClass="max-w-2xl sm:max-w-3xl"
          />

          <p className="text-center text-[11px] mt-3" style={{ color: "#555" }}>
            Surge can make mistakes. Verify important information.
          </p>
        </div>
      )}
    </div>
  );
}
