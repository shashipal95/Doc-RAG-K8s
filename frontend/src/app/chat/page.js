"use client";

import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  getCurrentUser, getValidToken, authFetch,
  signOut,
} from "@/lib/auth";
import { useMediaQuery } from "@/lib/hooks";
import { VoiceInput } from "@/components/VoiceInput";

import WeatherCard from "@/components/WeatherCard";
import DocumentsModal from "@/components/DocumentsModal";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

function extractToken(data) {
  if (!data) return "";
  try {
    const json = typeof data === "string" ? JSON.parse(data) : data;
    return json.tok || "";
  } catch {
    return data; // Fallback
  }
}


/* ─────────────────────────────────────────────────────────
   HEADER DROPDOWN  (model / embed)
───────────────────────────────────────────────────────── */
function Dropdown({ label, value, onChange, options, isDark }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const cur = options.find(o => o.value === value);

  const surf = isDark ? "#2D2D2D" : "#F0EDE6";
  const bdr = isDark ? "var(--c-border-mid)" : "#CEC9BC";
  const txtClr = isDark ? "#F0EDE6" : "#27251D";
  const muted = isDark ? "rgba(240,237,230,.48)" : "#6A6458";
  const menuBg = isDark ? "#2D2D2D" : "#FFFFFF";
  const menuBd = isDark ? "var(--c-border-mid)" : "#CEC9BC";
  const actBg = "var(--c-accent-dim)";

  return (
    <div ref={ref} style={{ position: "relative", display: "flex", alignItems: "center", gap: 8 }}>

      {/* INLINE LABEL */}
      <span style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: ".08em",
        textTransform: "uppercase",
        fontFamily: "var(--font-mono)",
        color: isDark ? "rgba(240,237,230,.35)" : "#9A9080"
      }}>
        {label}
      </span>

      {/* BUTTON */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 12px",
          borderRadius: 10,
          border: `1px solid ${bdr}`,
          background: surf,
          color: txtClr,
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          whiteSpace: "nowrap",
          minWidth: 90,
        }}
      >
        <span style={{ flex: 1 }}>{cur ? (cur.label.includes(" (") ? cur.label.split(" (")[0] : cur.label.split(" ")[0]) : value}</span>
        <svg
          style={{
            width: 12,
            height: 12,
            opacity: .6,
            transition: "transform .15s",
            transform: open ? "rotate(180deg)" : "none",
          }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* MENU */}
      {open && (
        <div style={{
          position: "absolute",
          zIndex: 400,
          top: "calc(100% + 6px)",
          left: 0,
          background: menuBg,
          border: `1px solid ${menuBd}`,
          borderRadius: 10,
          overflow: "hidden",
          minWidth: 140,
          boxShadow: "0 14px 40px rgba(0,0,0,.35)"
        }}>
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "8px 12px",
                fontSize: 13,
                cursor: "pointer",
                border: "none",
                background: value === opt.value ? actBg : "transparent",
                color: value === opt.value ? "var(--c-accent)" : muted,
                fontWeight: value === opt.value ? 600 : 400
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   IMAGE GRID
───────────────────────────────────────────────────────── */
function ImageGrid({ images, isDark }) {
  const [lb, setLb] = useState(null);
  if (!images?.length) return null;
  return (
    <>
      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6 }}>
        {images.map((img, i) => (
          <div key={i} onClick={() => setLb(img)} style={{ position: "relative", borderRadius: 8, overflow: "hidden", cursor: "zoom-in", aspectRatio: "16/9", background: isDark ? "rgba(255,255,255,.06)" : "#F0EDE6" }}>
            <img src={img.thumb || img.url} alt={img.title || `Result ${i + 1}`} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block", transition: "transform .2s" }}
              onMouseEnter={e => e.currentTarget.style.transform = "scale(1.05)"}
              onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
              onError={e => e.currentTarget.parentElement.style.display = "none"}
            />
            {img.title && <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, background: "linear-gradient(transparent,rgba(0,0,0,.65))", padding: "14px 8px 5px", fontSize: 9.5, color: "#fff", textOverflow: "ellipsis", whiteSpace: "nowrap", overflow: "hidden" }}>{img.title}</div>}
          </div>
        ))}
      </div>
      <p style={{ fontSize: 10, marginTop: 5, color: isDark ? "rgba(255,255,255,.28)" : "#A09888" }}>Images via web search · Click to enlarge</p>
      {lb && (
        <div onClick={() => setLb(null)} style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(0,0,0,.9)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, backdropFilter: "blur(8px)" }}>
          <div onClick={e => e.stopPropagation()} style={{ position: "relative", maxWidth: 900, width: "100%", borderRadius: 14, overflow: "hidden", boxShadow: "0 32px 80px rgba(0,0,0,.6)" }}>
            <img src={lb.url} alt={lb.title} style={{ width: "100%", display: "block", maxHeight: "80vh", objectFit: "contain", background: "#111" }} />
            <div style={{ background: "#111", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 12, color: "#aaa" }}>{lb.title || "Image"}</span>
              {lb.source && <a href={lb.source} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "var(--c-accent)", textDecoration: "none", fontWeight: 600 }}>View source ↗</a>}
            </div>
            <button onClick={() => setLb(null)} style={{ position: "absolute", top: 12, right: 12, background: "rgba(0,0,0,.6)", border: "none", borderRadius: "50%", width: 32, height: 32, cursor: "pointer", color: "#fff", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
          </div>
        </div>
      )}
    </>
  );
}

/* ─────────────────────────────────────────────────────────
   IMAGE PREVIEW CHIP
───────────────────────────────────────────────────────── */
function ImgChip({ image, onClear, isDark }) {
  if (!image) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, padding: "6px 10px", borderRadius: 10, background: "var(--c-accent-soft)", border: "1px solid var(--c-accent-dim)", alignSelf: "flex-start", maxWidth: 260 }}>
      <img src={image.previewUrl} alt="preview" style={{ width: 38, height: 38, borderRadius: 7, objectFit: "cover", flexShrink: 0 }} />
      <div style={{ flex: 1, overflow: "hidden" }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: "var(--c-accent)", marginBottom: 1, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>{image.file.name}</p>
        <p style={{ fontSize: 10, color: isDark ? "rgba(240,237,230,.35)" : "#9A9080" }}>{(image.file.size / 1024).toFixed(0)} KB · Image attached</p>
      </div>
      <button onClick={onClear} style={{ background: "none", border: "none", cursor: "pointer", color: "#EF4444", fontSize: 14, padding: 2, opacity: .7 }}>✕</button>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   CONSTANTS
───────────────────────────────────────────────────────── */
const MODEL_OPTS = [
  { value: "groq", label: "Groq - llama-3.3" },
  { value: "gemini", label: "Gemini 2.5 flash" },
  { value: "openai", label: "OpenAI - GPT-4o" },
  { value: "ollama", label: "Ollama - llama 3.2" },
];
const EMBED_OPTS = [
  { value: "gemini", label: "Gemini" },
  { value: "openai", label: "OpenAI" },
];

/* ─────────────────────────────────────────────────────────
   THEME TOKENS
───────────────────────────────────────────────────────── */
const TH = {
  dark: {
    app: "var(--c-bg)",
    sb: "var(--c-bg-warm)",
    sbBdr: "var(--c-border)",
    hdr: "rgba(15, 15, 16, 0.75)",
    hdrBdr: "var(--c-border-soft)",
    msg: "var(--c-bg)",
    inp: "var(--c-bg-warm)",
    inpBdr: "var(--c-border-soft)",
    surface: "var(--c-surface)",
    bdr: "var(--c-border-soft)",
    bdr2: "var(--c-border-mid)",
    text: "var(--c-text)",
    muted: "var(--c-text-muted)",
    faint: "var(--c-text-faint)",
    ghost: "var(--c-text-ghost)",
    msgUser: { background: "var(--c-accent-dim)", color: "var(--c-text)", border: "1px solid var(--c-border)", boxShadow: "0 4px 20px rgba(0,0,0,.15)" },
    msgAI: { background: "var(--c-surface)", border: "1px solid var(--c-border-soft)", color: "var(--c-text)", boxShadow: "0 2px 14px rgba(0,0,0,.2)" },
    sessOn: { background: "var(--c-accent-dim)", border: "1px solid var(--c-accent-glow)", color: "var(--c-text)" },
    sessOff: "var(--c-text-muted)",
    toggleBtn: { background: "rgba(255,255,255,.07)", border: "1px solid var(--c-border-mid)", color: "var(--c-text-muted)" },
    sendBtn: { background: "var(--g-accent)", boxShadow: "0 4px 18px var(--c-accent-glow)" },
    attBtn: { background: "transparent", color: "var(--c-accent)", border: "1px solid var(--c-accent-dim)" },
    textarea: { background: "var(--c-surface)", border: "1px solid var(--c-border-soft)", color: "var(--c-text)" },
    dot: "var(--c-accent-glow)",
    cursor: "var(--c-accent)",
    hint: "var(--c-text-faint)",
    hintEm: "var(--c-accent)",
    divider: "var(--c-border-soft)",
    isDark: true,
  },
  light: {
    app: "var(--c-bg)",
    sb: "var(--c-bg-warm)",
    sbBdr: "var(--c-border)",
    hdr: "rgba(255,255,255,0.75)",
    hdrBdr: "var(--c-border-soft)",
    msg: "var(--c-bg)",
    inp: "var(--c-bg-warm)",
    inpBdr: "var(--c-border-soft)",
    surface: "var(--c-surface)",
    bdr: "var(--c-border)",
    bdr2: "var(--c-border-mid)",
    text: "var(--c-text)",
    muted: "var(--c-text-muted)",
    faint: "var(--c-text-faint)",
    ghost: "var(--c-text-ghost)",
    msgUser: { background: "var(--c-accent-soft)", color: "var(--c-text)", border: "1px solid var(--c-accent-dim)", boxShadow: "0 2px 12px rgba(0,0,0,.04)" },
    msgAI: { background: "#FFFFFF", border: "1px solid var(--c-border)", color: "var(--c-text)", boxShadow: "0 2px 12px rgba(0,0,0,.04)" },
    sessOn: { background: "var(--c-accent-soft)", border: "1px solid var(--c-accent-dim)", color: "var(--c-accent-2)" },
    sessOff: "var(--c-text-muted)",
    toggleBtn: { background: "var(--c-surface)", border: "1px solid var(--c-border)", color: "var(--c-text-muted)" },
    sendBtn: { background: "var(--g-accent)", boxShadow: "0 4px 18px var(--c-accent-glow)" },
    attBtn: { background: "var(--c-accent-soft)", color: "var(--c-accent-2)", border: "1px solid var(--c-accent-dim)" },
    textarea: { background: "var(--c-bg)", border: "1px solid var(--c-border)", color: "var(--c-text)" },
    dot: "var(--c-accent-glow)",
    cursor: "var(--c-accent-2)",
    hint: "var(--c-text-faint)",
    hintEm: "var(--c-accent-2)",
    divider: "var(--c-border)",
    isDark: false,
  },
};

/* ─────────────────────────────────────────────────────────
   COMPONENT
───────────────────────────────────────────────────────── */

/* ─────────────────────────────────────────────────────────
   MESSAGE ITEM (Memoized for performance)
───────────────────────────────────────────────────────── */
const MessageItem = React.memo(({ msg, i, th, isMobile, editingMsgIndex, editValue, setEditValue, saveEdit, setEditingMsgIndex, copyToClipboard, copyingIndex, handleEdit, retryMessage, handleFeedback, hoveredMsgIdx, setHoveredMsgIdx, loadingSuggestions, messagesLength, suggestions, sendMessage }) => {
  const DetailsComponent = useCallback(({ node, children, ...p }) => {
    const [isOpen, setIsOpen] = useState(false);
    const childrenArray = React.Children.toArray(children);
    const summary = childrenArray.find(c => c.type === "summary");
    const rest = childrenArray.filter(c => c.type !== "summary");
    return (
      <div style={{ marginTop: 10 }}>
        <div 
          onClick={() => setIsOpen(!isOpen)} 
          style={{ cursor: "pointer", fontWeight: 600, fontSize: 13, userSelect: "none", color: "var(--c-accent)", outline: "none", display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 8, border: "1px solid var(--c-border)", background: "var(--c-accent-soft)", transition: "all .15s" }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--c-accent-dim)"}
          onMouseLeave={e => e.currentTarget.style.background = "var(--c-accent-soft)"}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a4 4 0 0 0-4-4H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a4 4 0 0 1 4-4h6z" />
          </svg>
          {isOpen ? "Hide Sources" : "View Source"}
        </div>
        {isOpen && <div style={{ marginTop: 10, padding: "12px 14px", background: th.isDark ? "rgba(0,0,0,0.15)" : "#F9F6F0", borderRadius: 8, border: "1px solid var(--c-border)", color: th.text, fontSize: 13, lineHeight: 1.5 }}>{rest}</div>}
      </div>
    );
  }, [th]);

  return (
    <div className="msg-row" style={{ display: "flex", flexDirection: "column", paddingBottom: 52 }} onMouseEnter={() => setHoveredMsgIdx(i)} onMouseLeave={() => setHoveredMsgIdx(null)}>
      <div className="msg-in" style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", alignItems: "flex-start", gap: 10 }}>
        {msg.role === "assistant" && (
          <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#0F0F10", fontFamily: "var(--font-display)", boxShadow: "0 2px 10px var(--c-accent-glow)", marginTop: 2 }}>D</div>
        )}
        <div style={{ position: "relative", maxWidth: isMobile ? "90%" : "80%" }}>
          <div style={{ padding: "6px 12px", fontSize: isMobile ? 14 : 15, lineHeight: 1.5, overflowWrap: "anywhere", wordBreak: "break-word", borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "4px 18px 18px 18px", border: msg.role === "assistant" ? "1px solid var(--c-border-soft)" : "none", boxShadow: msg.role === "assistant" ? (th.isDark ? "0 4px 20px rgba(0,0,0,0.3)" : "0 4px 16px rgba(0,0,0,0.03)") : "0 8px 30px var(--c-accent-glow)", ...(msg.role === "user" ? th.msgUser : th.msgAI) }}>
            {msg.imagePreview && (
              <div style={{ marginBottom: 12 }}>
                <img src={msg.imagePreview} alt="attached" style={{ maxWidth: "100%", maxHeight: isMobile ? 240 : 320, borderRadius: 12, display: "block", objectFit: "cover", boxShadow: "0 6px 24px rgba(0,0,0,.25)" }} />
                <div className="badge" style={{ marginTop: 8, fontSize: 10 }}>🖼 Image attached</div>
              </div>
            )}

            {msg.audioPreview && (
              <div className="media-card">
                <div className="media-header">
                  <div className="icon">🎵</div>
                  <div style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{msg.audioPreview.name}</div>
                </div>
                {msg.audioPreview.url
                  ? <audio controls className="media-player" src={msg.audioPreview.url} />
                  : <div style={{ fontSize: 11, opacity: .5, fontStyle: "italic", padding: "4px 0" }}>Audio transcribed & indexed</div>}
              </div>
            )}
            {msg.videoPreview && (
              <div className="media-card">
                <div className="media-header">
                  <div className="icon">🎬</div>
                  <div style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{msg.videoPreview.name}</div>
                </div>
                {msg.videoPreview.url
                  ? <video controls className="media-player" src={msg.videoPreview.url} style={{ maxHeight: 220 }} />
                  : <div style={{ fontSize: 11, opacity: .5, fontStyle: "italic", padding: "4px 0" }}>Video transcribed & indexed</div>}
              </div>
            )}
            {msg.docAttachment && (
              <div className="media-card" style={{ padding: "10px 14px", borderStyle: "dashed" }}>
                <div className="media-header" style={{ marginBottom: 0 }}>
                  <div className="icon" style={{ background: "var(--c-accent-soft)", color: "var(--c-accent)" }}>📄</div>
                  <div style={{ flex: 1 }}>{msg.docAttachment.name}</div>
                </div>
              </div>
            )}

            {msg.streaming && !msg.content ? (
              <span style={{ display: "flex", gap: 4, alignItems: "center", height: 18 }}>
                {[0, 1, 2].map(j => <span key={j} style={{ width: 6, height: 6, borderRadius: "50%", background: th.dot, animation: "bounce 1.2s ease-in-out infinite", animationDelay: `${j * .18}s`, display: "inline-block" }} />)}
              </span>
            ) : (
              <>
                {editingMsgIndex === i ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <textarea
                      autoFocus
                      className="msg-edit-area"
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveEdit(i); } if (e.key === "Escape") setEditingMsgIndex(null); }}
                    />
                    <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                      <button onClick={() => setEditingMsgIndex(null)} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 12, border: "none", background: "rgba(255,255,255,0.1)", color: "#fff", cursor: "pointer" }}>Cancel</button>
                      <button onClick={() => saveEdit(i)} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 12, border: "none", background: "#fff", color: "#000", fontWeight: 600, cursor: "pointer" }}>Save & Send</button>
                    </div>
                  </div>
                ) : (
                  <>
                    {(() => {
                      const contentStr = (msg.content || "").replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gim, "");
                      let weatherData = null;
                      let displayContent = contentStr;

                      const blockMatch = contentStr.match(/```weather-card\s*\n([\s\S]*?)\n```/i);
                      const plainMatch = contentStr.match(/weather-card\s*(\{[\s\S]*?\})/i);

                      if (blockMatch) {
                        try {
                          weatherData = JSON.parse(blockMatch[1]);
                          displayContent = contentStr.replace(/```weather-card\s*\n([\s\S]*?)\n```/i, "").trim();
                        } catch (e) { console.error("Failed to parse weather card data", e); }
                      } else if (plainMatch) {
                        try {
                          weatherData = JSON.parse(plainMatch[1]);
                          displayContent = contentStr.replace(/(?:```(?:json)?\s*\n)?weather-card\s*\{[\s\S]*?\}(?:\s*\n```)?/i, "").trim();
                        } catch (e) { console.error("Failed to parse weather plain-text card data", e); }
                      }

                      return (
                        <>
                          <ReactMarkdown rehypePlugins={[rehypeRaw]} components={{
                            details: DetailsComponent,
                            p: ({ node, ...p }) => <p style={{ margin: "6px 0", fontSize: 15, lineHeight: 1.5 }} {...p} />,
                            ul: ({ node, ...p }) => <ul style={{ paddingLeft: 20, margin: "8px 0", listStyleType: "disc" }} {...p} />,
                            ol: ({ node, ...p }) => <ol style={{ paddingLeft: 20, margin: "8px 0", listStyleType: "decimal" }} {...p} />,
                            li: ({ node, ...p }) => <li style={{ marginBottom: 4 }} {...p} />,
                            strong: ({ node, ...p }) => <strong style={{ fontWeight: 700, color: "var(--c-accent)" }} {...p} />,
                            h1: ({ node, ...p }) => <h1 style={{ fontSize: "1.4rem", fontWeight: 800, margin: "14px 0 8px", borderBottom: `1px solid ${th.divider}`, paddingBottom: 6 }} {...p} />,
                            h2: ({ node, ...p }) => <h2 style={{ fontSize: "1.3rem", fontWeight: 700, margin: "12px 0 6px" }} {...p} />,
                            h3: ({ node, ...p }) => <h3 style={{ fontSize: "1.2rem", fontWeight: 600, margin: "10px 0 4px" }} {...p} />,
                            code: ({ node, inline, ...p }) => inline
                              ? <code style={{ background: "var(--c-accent-soft)", color: "var(--c-accent)", padding: "2px 5px", borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500 }} {...p} />
                              : <code style={{ display: "block", background: th.isDark ? "var(--c-bg-warm)" : "#EBE8DB", padding: "12px 16px", borderRadius: 10, fontFamily: "var(--font-mono)", fontSize: 13, overflowX: "auto", margin: "12px 0", color: "var(--c-accent)", border: "1px solid var(--c-border)" }} {...p} />,
                          }}>
                            {displayContent.replace(/\n{3,}/g, "\n\n")}
                          </ReactMarkdown>
                          {weatherData && <WeatherCard data={weatherData} />}
                        </>
                      );
                    })()}
                    {msg.streaming && <span style={{ display: "inline-block", width: 2, height: 14, background: th.cursor, marginLeft: 3, verticalAlign: "middle", animation: "blink 1s step-end infinite", borderRadius: 2 }} />}
                  </>
                )}
              </>
            )}
            {msg.role === "assistant" && msg.images?.length > 0 && <ImageGrid images={msg.images} isDark={th.isDark} />}
          </div>

          {!msg.streaming && editingMsgIndex !== i && (
            <div className={`msg-actions ${msg.role}`} style={{ opacity: hoveredMsgIdx === i ? 1 : 0, transform: hoveredMsgIdx === i ? 'translateY(0)' : 'translateY(4px)', pointerEvents: hoveredMsgIdx === i ? 'auto' : 'none' }}>
              <button className="msg-action-btn" style={{ background: th.isDark ? "#2D2D2D" : "#FFFFFF", color: th.isDark ? "#F0EDE6" : "#27251D", border: "none" }} onClick={() => copyToClipboard(msg.content, i)} title="Copy text">
                {copyingIndex === i ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="#5EC995" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                )}
              </button>
              {msg.role === "user" && (
                <button className="msg-action-btn" style={{ background: th.isDark ? "#2D2D2D" : "#FFFFFF", color: th.isDark ? "#F0EDE6" : "#27251D", border: "none" }} onClick={() => handleEdit(i)} title="Edit & resend">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                </button>
              )}
              <button className="msg-action-btn" style={{ background: th.isDark ? "#2D2D2D" : "#FFFFFF", color: th.isDark ? "#F0EDE6" : "#27251D", border: "none" }} onClick={() => retryMessage(i)} title="Retry">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
              </button>
              {msg.role === "assistant" && (
                <>
                  <button className={`msg-action-btn ${msg.feedback === 'up' ? 'active' : ''}`} style={{ background: th.isDark ? "#2D2D2D" : "#FFFFFF", color: th.isDark ? "#F0EDE6" : "#27251D", border: "none" }} onClick={() => handleFeedback(i, 'up')} title="Good response">
                    <svg viewBox="0 0 24 24" fill={msg.feedback === 'up' ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2.5"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" /></svg>
                  </button>
                  <button className={`msg-action-btn ${msg.feedback === 'down' ? 'active' : ''}`} style={{ background: th.isDark ? "#2D2D2D" : "#FFFFFF", color: th.isDark ? "#F0EDE6" : "#27251D", border: "none" }} onClick={() => handleFeedback(i, 'down')} title="Poor response">
                    <svg viewBox="0 0 24 24" fill={msg.feedback === 'down' ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2.5"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" /></svg>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
        {msg.role === "user" && (
          <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: "var(--c-accent-soft)", border: "1px solid var(--c-accent-dim)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--c-accent)", marginTop: 2 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
        )}
      </div>
      {(loadingSuggestions && i === messagesLength - 1 && msg.role === "assistant" && !msg.streaming) && (
        <div style={{ paddingLeft: 38, marginBottom: 20, display: "flex", gap: 10, flexWrap: "wrap", marginTop: 56 }}>
          {[1, 2, 3].map(j => (
            <div key={j} style={{ height: 36, width: 120 + j * 30, borderRadius: 18, background: th.isDark ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.05)", animation: "pulse 1.5s ease-in-out infinite" }} />
          ))}
        </div>
      )}
      {i === messagesLength - 1 && msg.role === "assistant" && !msg.streaming && suggestions.length > 0 && (
        <div className="fade-up" style={{ paddingLeft: 38, marginBottom: 20, display: "flex", gap: 8, flexWrap: "wrap", marginTop: 56 }}>
          {suggestions.map((sug, idx) => (
            <button key={idx} onClick={(e) => sendMessage(e, sug)} style={{ padding: "8px 16px", borderRadius: 20, fontSize: 13, border: "1px solid var(--c-accent-dim)", background: "var(--c-accent-soft)", color: "var(--c-accent)", cursor: "pointer", transition: "all 0.2s" }} onMouseEnter={e => { e.currentTarget.style.background = "var(--c-accent-dim)" }} onMouseLeave={e => { e.currentTarget.style.background = "var(--c-accent-soft)" }}>
              {sug}
            </button>
          ))}
        </div>
      )}
    </div>
  );
});

export default function ChatPage() {
  const router = useRouter();

  const [themeColor, setThemeColor] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("app_theme_color");
      return saved && ["emerald", "purple", "cyan", "blue"].includes(saved) ? saved : "emerald";
    }
    return "emerald";
  });
  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("app_theme_mode");
      return saved && (saved === "dark" || saved === "light") ? saved : "light";
    }
    return "light";
  });
  const theme = themeMode;
  const th = TH[theme];

  // Load persistence (removed as state initialized from localStorage)

  // Save changes and update element attributes
  useEffect(() => {
    localStorage.setItem("app_theme_color", themeColor);
    document.documentElement.setAttribute("data-theme", themeColor);
  }, [themeColor]);

  useEffect(() => {
    localStorage.setItem("app_theme_mode", themeMode);
    document.documentElement.setAttribute("data-mode", themeMode);
  }, [themeMode]);


  const [user, setUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [docStatus, setDocStatus] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [provider, setProvider] = useState("groq");
  const [embeddingProvider, setEmbP] = useState("gemini");
  const [deletingDocs, setDeletingDocs] = useState(false);
  const [clearMsg, setClearMsg] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [openMenuSessionId, setOpenMenuSessionId] = useState(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedAudio, setSelectedAudio] = useState(null);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [histSearch, setHistSearch] = useState("");
  const [showAttach, setShowAttach] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [latitude, setLatitude] = useState(null);
  const [longitude, setLongitude] = useState(null);
  const [showDocsModal, setShowDocsModal] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const themeMenuRef = useRef(null);

  useEffect(() => {
    const handleOutsideThemeClick = (e) => {
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target)) {
        setShowThemeMenu(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideThemeClick);
    return () => document.removeEventListener("mousedown", handleOutsideThemeClick);
  }, []);

  // Message Action States
  const [editingMsgIndex, setEditingMsgIndex] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [copyingIndex, setCopyingIndex] = useState(null);
  const [hoveredMsgIdx, setHoveredMsgIdx] = useState(null);

  const isMobile = useMediaQuery("(max-width: 768px)");
  const isTiny = useMediaQuery("(max-width: 480px)");

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
    else setSidebarOpen(true);
  }, [isMobile]);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const audioRef = useRef(null);
  const hasGreetedRef = useRef(false);
  const latestInputRef = useRef(input);
  const latestImgRef = useRef(selectedImage);
  const isInitialMount = useRef(true); // used to skip session-key wipe on first render
  const currentSessionRef = useRef(currentSession);

  useEffect(() => { currentSessionRef.current = currentSession; }, [currentSession]);

  useEffect(() => { latestInputRef.current = input; }, [input]);
  useEffect(() => { latestImgRef.current = selectedImage; }, [selectedImage]);

  // Load coordinates from localStorage on mount
  useEffect(() => {
    const savedLat = localStorage.getItem("gps_lat");
    const savedLon = localStorage.getItem("gps_lon");
    if (savedLat && savedLon) {
      setLatitude(parseFloat(savedLat));
      setLongitude(parseFloat(savedLon));
    }
  }, []);

  // Close context menu on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (openMenuSessionId) {
        setOpenMenuSessionId(null);
      }
    };
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [openMenuSessionId]);

  const startNewChat = () => {
    setCurrentSession(null);
    setInput("");
    setSelectedImage(null);
    setSuggestions([]);
    hasGreetedRef.current = true;
    setMessages([{ role: "assistant", content: "Hello 👋 How can I help you today?" }]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    audioRef.current?.play().catch(() => { });
  };

  const LAST_SESSION_KEY = "docchat_last_session";

  const loadSessions = useCallback(async () => {
    try {
      const res = await authFetch("/api/v1/sessions");
      if (res.ok) setSessions(await res.json());
    } catch (e) { console.error("[sessions] load failed:", e); }
  }, []);

  // Persist active session so page refresh restores it.
  // IMPORTANT: skip the very first render — on mount currentSession is null
  // which would wipe the localStorage key before init() has a chance to read it.
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (currentSession) {
      localStorage.setItem(LAST_SESSION_KEY, currentSession);
    } else {
      localStorage.removeItem(LAST_SESSION_KEY);
    }
  }, [currentSession]);

  useEffect(() => {
    const init = async () => {
      const token = await getValidToken();
      if (!token) { router.push("/login"); return; }
      const stored = getCurrentUser();
      if (stored) {
        setUser({ id: stored.id, name: stored.name || stored.email?.split("@")[0], email: stored.email });
      } else {
        try {
          const res = await authFetch("/api/v1/auth/me");
          const data = await res.json();
          setUser({ id: data.id, name: data.name || data.email?.split("@")[0], email: data.email });
        } catch { router.push("/login"); return; }
      }

      // Load all sessions so the sidebar is populated
      const sessRes = await authFetch("/api/v1/sessions").catch(() => null);
      if (sessRes?.ok) {
        const allSessions = await sessRes.json();
        setSessions(allSessions);

        // Try to restore the last active session
        const lastId = localStorage.getItem(LAST_SESSION_KEY);
        const sessionExists = lastId && allSessions.some(s => s.id === lastId);

        if (sessionExists) {
          // Inline restore to avoid closure issue with loadMessages defined later
          setCurrentSession(lastId);
          hasGreetedRef.current = true;
          try {
            const msgRes = await authFetch(`/api/v1/sessions/${lastId}/messages`);
            if (msgRes.ok) {
              const data = await msgRes.json();
              const fetched = data.map(m => {
                const meta = m.metadata || {};
                const att = meta.attachment || {};
                let imgUrl = null;
                if (meta.type === "image" && meta.url) imgUrl = meta.url;
                else if (att.type === "image" && att.url) imgUrl = att.url;
                if (imgUrl && imgUrl.startsWith("/") && !imgUrl.startsWith("//")) {
                  imgUrl = `${BASE_URL}${imgUrl}`;
                }
                return {
                  role: m.role,
                  content: m.content,
                  imagePreview: imgUrl,
                  audioPreview: (meta.type === "audio" || att.type === "audio") ? { name: att.name || "Audio", url: att.url || null } : null,
                  videoPreview: (meta.type === "video" || att.type === "video") ? { name: att.name || "Video", url: att.url || null } : null,
                  docAttachment: (meta.type === "document" || att.type === "document") ? { name: att.name || "Document", url: att.url || null } : null,
                  images: meta.images || [],
                  streaming: false,
                };
              });
              setMessages([{ role: "assistant", content: "Hello 👋 How can I help you today?" }, ...fetched]);
              return; // session restored successfully
            }
          } catch (e) { console.error("[init] restore failed:", e); }
        }
      }

      // No saved session or restore failed
      startNewChat();
    };
    init();
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const deleteSession = async (id) => {
    try { await authFetch(`/api/v1/sessions/${id}`, { method: "DELETE" }); } catch { }
    if (currentSession === id) { setCurrentSession(null); setMessages([]); }
    loadSessions();
  };

  const startRename = (e, session) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  };

  const commitRename = async (id) => {
    const trimmed = editingTitle.trim();
    if (!trimmed) { setEditingSessionId(null); return; }
    try {
      await authFetch(`/api/v1/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
      });
      setSessions(prev => prev.map(s => s.id === id ? { ...s, title: trimmed } : s));
    } catch (e) { console.error("[rename] failed:", e); }
    setEditingSessionId(null);
  };

  const cancelRename = () => setEditingSessionId(null);

  const loadMessages = async (sessionId) => {
    if (!sessionId) return;
    setCurrentSession(sessionId);
    if (isMobile) setSidebarOpen(false);
    hasGreetedRef.current = true;

    try {
      const res = await authFetch(`/api/v1/sessions/${sessionId}/messages`);
      if (!res.ok) { console.error("[history] failed to load messages"); return; }
      const data = await res.json();
      const fetched = data.map(m => {
        const meta = m.metadata || {};
        const att = meta.attachment || {};
        
        // Robust image extraction
        let imgUrl = null;
        if (meta.type === "image" && meta.url) imgUrl = meta.url;
        else if (att.type === "image" && att.url) imgUrl = att.url;
        else if (meta.images && meta.images.length > 0) imgUrl = null; // Images from search handled separately

        // Handle relative URLs if they leaked into DB
        if (imgUrl && imgUrl.startsWith("/") && !imgUrl.startsWith("//")) {
          imgUrl = `${BASE_URL}${imgUrl}`;
        }

        return {
          id: m.id,
          role: m.role,
          content: m.content,
          imagePreview: imgUrl,
          audioPreview: (meta.type === "audio" || att.type === "audio") ? { name: att.name || "Audio", url: att.url || null } : null,
          videoPreview: (meta.type === "video" || att.type === "video") ? { name: att.name || "Video", url: att.url || null } : null,
          docAttachment: (meta.type === "document" || att.type === "document") ? { name: att.name || "Document", url: att.url || null } : null,
          images: meta.images || [],
          feedback: m.feedback,
          streaming: false,
        };
      });
      setMessages([{ role: "assistant", content: "Hello 👋 How can I help you today?" }, ...fetched]);
    } catch (e) { console.error("[history] error:", e); }
  };

  const logout = async () => { await signOut(); router.push("/"); };

  const resizeTA = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
  const DOC_EXTS = [".pdf", ".docx", ".txt"];

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const isImage = IMAGE_TYPES.includes(file.type);
    const isDoc = DOC_EXTS.some(ext => file.name.toLowerCase().endsWith(ext));

    if (isImage) { setSelectedImage({ file, previewUrl: URL.createObjectURL(file) }); return; }

    const AUDIO_VIDEO_EXTS = [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".mpeg", ".mpga"];
    const isMedia = AUDIO_VIDEO_EXTS.some(ext => file.name.toLowerCase().endsWith(ext));

    if (isDoc || isMedia) {
      setUploading(true);
      setUploadMsg(isMedia ? "Transcribing…" : "Indexing…");
      setDocStatus(null);

      // Track attachment for history — set state before upload so it shows in the message
      if (isMedia) {
        const isVideo = [".mp4", ".webm"].some(ext => file.name.toLowerCase().endsWith(ext));
        if (isVideo) setSelectedVideo({ name: file.name, previewUrl: null });
        else setSelectedAudio({ name: file.name, previewUrl: null });
      } else {
        setSelectedDoc({ name: file.name });
      }

      try {
        const form = new FormData();
        form.append("file", file);
        form.append("provider", provider);
        form.append("embedding_provider", embeddingProvider);
        const res = await authFetch("/api/v1/documents/upload", { method: "POST", body: form });
        if (!res.ok) { const err = await res.json().catch(() => ({ detail: "Upload failed" })); throw new Error(err.detail); }
        const result = await res.json();
        
        // Capture the playable URL if returned (for audio/video/document)
        if (result.url) {
          const fullUrl = `${BASE_URL}${result.url}`;
          if (isMedia) {
            const isVideo = [".mp4", ".webm"].some(ext => file.name.toLowerCase().endsWith(ext));
            if (isVideo) setSelectedVideo({ name: file.name, previewUrl: fullUrl });
            else setSelectedAudio({ name: file.name, previewUrl: fullUrl });
          } else {
            setSelectedDoc({ name: file.name, url: fullUrl });
          }
        }


        setUploadMsg(`✓ ${result.chunks_added} chunks indexed`);
        setDocStatus("indexed");
        audioRef.current?.play().catch(() => { });
      } catch (err) {
        setUploadMsg(`✗ ${err.message}`);
        setDocStatus("error");
        // Clear on error
        if (isMedia) { setSelectedAudio(null); setSelectedVideo(null); }
        else setSelectedDoc(null);
      } finally {
        setUploading(false);
        setTimeout(() => setUploadMsg(""), 5000);
      }
    } else {
      setUploadMsg("✗ Unsupported file type");
      setTimeout(() => setUploadMsg(""), 3500);
    }
  };
  const clearImage = () => {
    if (selectedImage?.previewUrl) URL.revokeObjectURL(selectedImage.previewUrl);
    setSelectedImage(null);
  };

  const clearDatabase = async () => {
    setDeletingDocs(true);
    setConfirmDelete(false);
    try {
      const res = await authFetch("/api/v1/documents/clear", { method: "DELETE" });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      setDocStatus("none");
      setClearMsg("✓ Embedded documents deleted");
      setTimeout(() => setClearMsg(""), 3500);
    } catch (err) {
      console.error("[delete-embedded] error:", err);
      setClearMsg(`✗ ${err.message || "Failed to delete"}`);
      setTimeout(() => setClearMsg(""), 4000);
    }
    setDeletingDocs(false);
  };

  const sendMessage = async (e, textOverride = null) => {
    e?.preventDefault();
    const txt = textOverride !== null ? textOverride : latestInputRef.current;
    const img = latestImgRef.current;
    if ((!txt.trim() && !img) || loading) return;
    const question = txt.trim();

    // Capture attachment state BEFORE clearing — React batches setState so
    // reading selectedAudio after setSelectedAudio(null) returns null immediately
    const capturedAudio = selectedAudio;
    const capturedVideo = selectedVideo;
    const capturedDoc = selectedDoc;

    setInput(""); setSelectedImage(null); setSelectedAudio(null); setSelectedVideo(null); setSelectedDoc(null); setSuggestions([]);
    setTimeout(resizeTA, 0);
    setMessages(prev => [...prev, {
      role: "user",
      content: question,
      imagePreview: img?.previewUrl ?? null,
      audioPreview: capturedAudio ? { name: capturedAudio.name, url: capturedAudio.previewUrl } : null,
      videoPreview: capturedVideo ? { name: capturedVideo.name, url: capturedVideo.previewUrl } : null,
      docAttachment: capturedDoc ? { name: capturedDoc.name, url: capturedDoc.url } : null,
    }]);
    setLoading(true);
    let activeSess = currentSession;

    if (!activeSess) {
      try {
        const res = await authFetch("/api/v1/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: question.slice(0, 40) || "Image Query" }) });
        if (!res.ok) { setLoading(false); return; }
        const s = await res.json();
        activeSess = s.id;
        setCurrentSession(activeSess);
        await loadSessions();
      } catch { setLoading(false); return; }
    }

    let uploadedUrl = null;
    if (img) {
      try {
        const form = new FormData();
        form.append("file", img.file);
        const uploadRes = await authFetch("/api/v1/documents/upload-image", { method: "POST", body: form });
        if (uploadRes.ok) {
          const uploadData = await uploadRes.json();
          uploadedUrl = `${BASE_URL}${uploadData.url}`;
        }
      } catch { }
    }

    // Build attachment metadata for history (use captured values — state already cleared)
    let attachmentMeta = {};
    if (img && uploadedUrl) {
      attachmentMeta = { attachment: { type: "image", url: uploadedUrl, name: img.file.name } };
    } else if (capturedAudio) {
      attachmentMeta = { attachment: { type: "audio", name: capturedAudio.name, url: capturedAudio.previewUrl || null } };
    } else if (capturedVideo) {
      attachmentMeta = { attachment: { type: "video", name: capturedVideo.name, url: capturedVideo.previewUrl || null } };
    } else if (capturedDoc) {
      attachmentMeta = { attachment: { type: "document", name: capturedDoc.name, url: capturedDoc.url || null } };
    }

    try {
      const res = await authFetch(`/api/v1/sessions/${activeSess}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "user", content: question, metadata: attachmentMeta }),
      });
      if (res.ok) {
        const data = await res.json();
        const msgId = data.id;
        if (activeSess === currentSessionRef.current) {
          setMessages(prev => {
            const u = [...prev];
            const userIdx = u.findLastIndex(m => m.role === "user");
            if (userIdx !== -1) u[userIdx].id = msgId;
            return u;
          });
        }
        // Move current session to top of history
        setSessions(prevSessions => {
          const sessionToMove = prevSessions.find(s => s.id === activeSess);
          if (!sessionToMove) return prevSessions;
          const otherSessions = prevSessions.filter(s => s.id !== activeSess);
          return [sessionToMove, ...otherSessions];
        });
      }
    } catch (e) { console.error("[history] failed to save user message:", e); }
    
    if (activeSess === currentSessionRef.current) {
      setMessages(prev => [...prev, { role: "assistant", content: "", images: [], streaming: true }]);
    }

    let full = "", imgs = [];
    try {
      const token = await getValidToken();
      let res;
      if (img) {
        const form = new FormData();
        form.append("question", question); form.append("provider", provider);
        form.append("embedding_provider", embeddingProvider);
        if (activeSess) form.append("session_id", activeSess);
        form.append("image", img.file);
        res = await fetch(`${BASE_URL}/api/v1/documents/query-image`, { method: "POST", headers: { "Authorization": `Bearer ${token}` }, body: form });
      } else {
        res = await fetch(`${BASE_URL}/api/v1/documents/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
          body: JSON.stringify({
            question,
            top_k: 3,
            provider,
            embedding_provider: embeddingProvider,
            session_id: activeSess,
            web_search: webSearch,
            agent_mode: agentMode,
            latitude: latitude || (localStorage.getItem("gps_lat") ? parseFloat(localStorage.getItem("gps_lat")) : null),
            longitude: longitude || (localStorage.getItem("gps_lon") ? parseFloat(localStorage.getItem("gps_lon")) : null)
          })
        });
      }
      if (!res.ok) { let d = `HTTP ${res.status}`; try { const j = await res.json(); d = j.detail || d; } catch { } throw new Error(d); }

      const reader = res.body.getReader(), dec = new TextDecoder();
      let buf = "", done = false;
      while (!done) {
        const { done: sd, value } = await reader.read();
        if (sd) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n"); buf = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split("\n"); let ev = "message", dl = "";
          for (const ln of lines) {
            if (ln.startsWith("event: ")) ev = ln.slice(7).trim();
            else if (ln.startsWith("data:")) {
              // Standard SSE: data: <content>
              // If content is a space, it's "data:  "
              // If content is empty, it's "data: "
              dl = ln.startsWith("data: ") ? ln.slice(6) : ln.slice(5);
            }
          }

          if (ev === "images") { try { imgs = JSON.parse(dl); if (activeSess === currentSessionRef.current) setMessages(prev => { const u = [...prev]; u[u.length - 1] = { ...u[u.length - 1], images: imgs }; return u; }); } catch { } continue; }
          if (ev === "error") { try { full = `Error: ${JSON.parse(dl).error}`; } catch { full = "An error occurred."; } done = true; break; }

          try { 
            const tok = extractToken(dl); 
            if (tok === "[DONE]") { done = true; break; }
            if (tok) { 
              full = full ? full + tok : tok.replace(/^\n+/, ""); 
              if (activeSess === currentSessionRef.current) {
                setMessages(prev => { const u = [...prev]; u[u.length - 1] = { ...u[u.length - 1], content: full, streaming: true }; return u; }); 
              }
            } 
          } catch { }



        }
      }
      audioRef.current?.play().catch(() => { });
    } catch (err) { full = full || `Error: ${err.message}`; }

    const final = (full || "No response.").replace(/^\n+/, "");
    if (activeSess === currentSessionRef.current) {
      setMessages(prev => { const u = [...prev]; u[u.length - 1] = { role: "assistant", content: final, images: imgs, streaming: false }; return u; });
    }
    try {
      const res = await authFetch(`/api/v1/sessions/${activeSess}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "assistant", content: final, metadata: { images: imgs } }),
      });
      if (res.ok) {
        const data = await res.json();
        const msgId = data.id;
        if (activeSess === currentSessionRef.current) {
          setMessages(prev => {
            const u = [...prev];
            u[u.length - 1] = { ...u[u.length - 1], id: msgId };
            return u;
          });
        }
      }
    } catch (e) { console.error("[history] failed to save assistant message:", e); }
    setLoading(false);
    
    // Fetch follow-up suggestions
    if (activeSess) {
      if (activeSess === currentSessionRef.current) setLoadingSuggestions(true);
      const FALLBACK_POOL = [
        "Tell me more about this",
        "Can you summarize the key points?",
        "What should I do next?",
        "Explain this in simpler terms",
        "Give me some examples",
        "What are the main takeaways?",
        "Are there any related topics?",
        "How does this apply to real-world scenarios?"
      ];
      const FALLBACK_SUGGESTIONS = FALLBACK_POOL.sort(() => 0.5 - Math.random()).slice(0, 3);
      try {
        const token = await getValidToken();
        const sugRes = await fetch(`${BASE_URL}/api/v1/sessions/${activeSess}/suggestions`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
          body: JSON.stringify({ provider })
        });
        if (sugRes.ok) {
          const sugData = await sugRes.json();
          const fetched = sugData.suggestions || [];
          if (activeSess === currentSessionRef.current) setSuggestions(fetched.length > 0 ? fetched : FALLBACK_SUGGESTIONS);
        } else {
          if (activeSess === currentSessionRef.current) setSuggestions(FALLBACK_SUGGESTIONS);
        }
      } catch (e) {
        console.error("[suggestions] error:", e);
        if (activeSess === currentSessionRef.current) setSuggestions(FALLBACK_SUGGESTIONS);
      } finally {
        if (activeSess === currentSessionRef.current) setLoadingSuggestions(false);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); }
  };
  const copyToClipboard = async (text, index) => {
    try {
      let cleanText = (text || "").replace(/<script\b[^>]*>([\s\S]*?)<\/script>/gim, "");
      cleanText = cleanText.replace(/```weather-card\s*\n([\s\S]*?)\n```/i, "");
      cleanText = cleanText.replace(/(?:```(?:json)?\s*\n)?weather-card\s*\{[\s\S]*?\}(?:\s*\n```)?/i, "");
      cleanText = cleanText.replace(/\n\n---\n<details\b[^>]*>([\s\S]*?)<\/details>/gi, "");
      cleanText = cleanText.replace(/<details\b[^>]*>([\s\S]*?)<\/details>/gi, "");
      cleanText = cleanText.replace(/^#{1,6}\s+/gm, "");
      cleanText = cleanText.replace(/^[ \t]*[*+-]\s+/gm, "");
      cleanText = cleanText.replace(/\*\*(.*?)\*\*/g, "$1");
      cleanText = cleanText.replace(/__(.*?)__/g, "$1");
      cleanText = cleanText.replace(/\*([^*]+)\*/g, "$1");
      cleanText = cleanText.replace(/_([^_]+)_/g, "$1");
      cleanText = cleanText.replace(/`([^`\n]+)`/g, "$1");
      cleanText = cleanText.replace(/```[a-zA-Z]*\n([\s\S]*?)\n```/g, "$1");
      cleanText = cleanText.trim();


      await navigator.clipboard.writeText(cleanText);
      setCopyingIndex(index);
      setTimeout(() => setCopyingIndex(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const retryMessage = (index) => {
    const msg = messages[index];
    if (!msg) return;

    if (msg.role === "user") {
      // Retry from user message: remove everything after and resend
      setMessages(prev => prev.slice(0, index));
      sendMessage(null, msg.content);
    } else {
      // Retry from assistant message: find previous user message and resend
      const prevUserMsg = messages.slice(0, index).reverse().find(m => m.role === "user");
      if (prevUserMsg) {
        setMessages(prev => prev.slice(0, index - 1)); // Remove the old assistant response
        sendMessage(null, prevUserMsg.content);
      }
    }
  };

  const handleEdit = (index) => {
    setEditingMsgIndex(index);
    setEditValue(messages[index].content);
  };

  const saveEdit = (index) => {
    const newVal = editValue.trim();
    if (!newVal) { setEditingMsgIndex(null); return; }
    
    // Truncate history to before this message and resend
    setMessages(prev => prev.slice(0, index));
    setEditingMsgIndex(null);
    sendMessage(null, newVal);
  };

  const handleFeedback = async (index, type) => {
    const msg = messages[index];
    if (!msg?.id || !currentSession) return;

    // Toggle logic: if same type clicked, clear it (null)
    const newFeedback = msg.feedback === type ? null : type;

    // Optimistic UI update
    setMessages(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], feedback: newFeedback };
      return updated;
    });

    try {
      await authFetch(`/api/v1/sessions/${currentSession}/messages/${msg.id}/feedback`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: newFeedback }),
      });
    } catch (e) {
      console.error("[feedback] failed to save:", e);
      // Rollback on error
      setMessages(prev => {
        const updated = [...prev];
        updated[index] = { ...updated[index], feedback: msg.feedback };
        return updated;
      });
    }
  };


  const filteredSessions = useMemo(() => {
    return sessions.filter(s => (s.title || "").toLowerCase().includes(histSearch.toLowerCase()));
  }, [sessions, histSearch]);

  const SB_W = 260;

  if (!user) return null;

  return (
    <div data-theme={theme} style={{ 
      display: "flex", 
      height: "100vh", 
      width: "100vw",
      overflow: "hidden", 
      background: th.app, 
      fontFamily: "var(--font-body)", 
      color: th.text, 
      letterSpacing: "-0.012em",
      position: "relative" 
    }}>

      <input ref={fileInputRef} type="file" accept="image/*,.pdf,.docx,.txt,.mp3,.wav,.m4a,.ogg,.flac,.webm,.mp4,.mpeg" style={{ display: "none" }} onChange={handleFile} />
      <audio ref={audioRef} src="https://assets.mixkit.co/active_storage/sfx/2358/2358-preview.mp3" />

      <style>{`
        @keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes msgIn{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
        @keyframes bounce{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}
        @keyframes pop{from{opacity:0;transform:scale(.95) translateY(4px)}to{opacity:1;transform:scale(1) translateY(0)}}
        @keyframes pulse{0%,100%{opacity:.4}50%{opacity:.9}}
        @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        @keyframes pulseAccent{0%{box-shadow:0 0 0 0 var(--c-accent-glow)}70%{box-shadow:0 0 0 6px rgba(0,0,0,0)}100%{box-shadow:0 0 0 0 rgba(0,0,0,0)}}
        .msg-in{animation:msgIn .24s ease both}
        .fade-up{animation:fadeUp .28s ease both}
        .sb-del{opacity:0!important;transition:opacity .18s,background .15s}
        .sb-row:hover .sb-del{opacity:1!important}
        .sb-del:hover{background:rgba(239,68,68,.15)!important;color:#EF4444!important}
        textarea:focus{outline:none}
        textarea::placeholder{color:${th.faint}}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:var(--c-accent-glow);border-radius:99px}
        @keyframes marquee-scroll {
          0%, 15% { transform: translateX(0); }
          85%, 100% { transform: translateX(var(--marquee-dist)); }
        }
        .marquee-active {
          animation: marquee-scroll var(--marquee-duration) linear alternate infinite;
        }
        .ctx-menu-item:hover {
          background: ${th.isDark ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.03)"} !important;
        }
        .ctx-menu-item-danger:hover {
          background: ${th.isDark ? "rgba(248,113,113,.1)" : "rgba(220,38,38,.05)"} !important;
        }
        .msg-actions .msg-action-btn {
          background: ${th.isDark ? "var(--c-surface-2)" : "#FFFFFF"} !important;
          color: var(--c-text) !important;
          border: 1px solid var(--c-border) !important;
        }
        .msg-actions .msg-action-btn:hover {
          background: var(--c-accent-dim) !important;
        }
        .btn-icon:hover {
          background: ${th.isDark ? "#2D2D2D" : "rgba(0,0,0,0.05)"} !important;
          color: ${th.isDark ? "var(--c-accent)" : "var(--c-accent-2)"} !important;
        }
      `}</style>

      {/* ══════════════════════════════════════
          SIDEBAR
      ══════════════════════════════════════ */}
      {isMobile && sidebarOpen && (
        <div 
          onClick={() => setSidebarOpen(false)}
          style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,.4)", backdropFilter: "blur(4px)", zIndex: 450, animation: "fadeIn .1s ease-out" }} 
        />
      )}
      <aside style={{ 
        width: sidebarOpen ? SB_W : 0, 
        flexShrink: 0, 
        overflow: "hidden", 
        transition: "width .1s ease-out", 
        willChange: "width",
        background: th.isDark ? "rgba(33, 33, 33, 0.9)" : "rgba(250, 250, 248, 0.9)", 
        backdropFilter: sidebarOpen ? "blur(14px)" : "none",
        WebkitBackdropFilter: sidebarOpen ? "blur(14px)" : "none",
        borderRight: sidebarOpen ? `1px solid ${th.sbBdr}` : "none", 
        display: "flex", 
        flexDirection: "column",
        position: isMobile ? "absolute" : "relative",
        top: 0,
        bottom: 0,
        left: 0,
        zIndex: 500,
        boxShadow: (isMobile && sidebarOpen) ? "20px 0 60px rgba(0,0,0,0.4)" : "none"
      }}>

        <div style={{ width: SB_W, height: "100%", display: "flex", flexDirection: "column" }}>

          {/* ① DocsChat LOGO ─────────────────── */}
          <div style={{ padding: "17px 17px 15px", borderBottom: `1px solid ${th.divider}`, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <div style={{ width: 32, height: 32, borderRadius: 10, background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 800, color: "var(--c-text)", boxShadow: "0 4px 15px var(--c-accent-glow)", flexShrink: 0 }}>D</div>
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 17, letterSpacing: "-.022em", color: th.text }}>DocsChat</span>
              <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: ".07em", textTransform: "uppercase", color: "var(--c-accent)", background: "var(--c-accent-soft)", border: "1px solid var(--c-accent-dim)", padding: "3px 7px", borderRadius: 99 }}>AI</span>
            </div>
            <button onClick={startNewChat} style={{ marginTop: 16, width: "100%", padding: "10px 14px", borderRadius: 12, fontSize: 13, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7, fontFamily: "var(--font-body)", transition: "all .2s cubic-bezier(0.4, 0, 0.2, 1)", background: "var(--c-accent-soft)", border: "1px solid var(--c-accent-dim)", color: th.isDark ? "var(--c-accent)" : "var(--c-accent-2)", letterSpacing: "0.02em" }}
              onMouseEnter={e => {
                e.currentTarget.style.background = "var(--c-accent-dim)";
                e.currentTarget.style.transform = "translateY(-1px) scale(1.02)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "var(--c-accent-soft)";
                e.currentTarget.style.transform = "none";
              }}
            >
              <svg width="11" height="11" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3} strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
              New Chat
            </button>
          </div>

          {/* ② SEARCH + HISTORY ─────────────── */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "13px 16px 0" }}>
            <p style={{ fontSize: 9.5, color: th.faint, textTransform: "uppercase", letterSpacing: ".10em", fontWeight: 600, fontFamily: "var(--font-mono)", marginBottom: 9 }}>Chat History</p>

            {/* Search */}
            <div style={{ position: "relative", marginBottom: 9 }}>
              <svg style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} width="12" height="12" fill="none" viewBox="0 0 24 24" stroke={th.faint} strokeWidth={2.5} strokeLinecap="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
              <input value={histSearch} onChange={e => setHistSearch(e.target.value)} placeholder="Search conversations…"
                style={{ width: "100%", padding: "7px 10px 7px 28px", borderRadius: 8, fontSize: 12, background: th.ghost, border: `1px solid ${th.bdr}`, color: th.text, fontFamily: "var(--font-body)", outline: "none" }}
                onFocus={e => { e.target.style.borderColor = "var(--c-accent)"; e.target.style.boxShadow = "0 0 0 3px var(--c-accent-dim)"; }}
                onBlur={e => { e.target.style.borderColor = th.bdr; e.target.style.boxShadow = "none"; }}
              />
            </div>

            {/* Session list */}
            <div style={{ flex: 1, overflowY: "auto", margin: "0 -4px", padding: "0 4px 10px" }}>
              {filteredSessions.length === 0 && (
                <p style={{ fontSize: 12, color: th.faint, textAlign: "center", marginTop: 12 }}>
                  {histSearch ? "No matches" : "No conversations yet"}
                </p>
              )}
              {filteredSessions.map(s => (
                <div
                  key={s.id}
                  className={`session-item sb-row ${currentSession === s.id ? 'active' : ''}`}
                  onClick={() => { if (editingSessionId !== s.id) loadMessages(s.id); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "7px 10px",
                    borderRadius: 10,
                    marginBottom: 4,
                    position: "relative",
                    cursor: "pointer",
                    background: currentSession === s.id 
                      ? (th.isDark ? "rgba(255,160,0,.12)" : "rgba(255,160,0,.08)") 
                      : "transparent",
                    border: `1px solid ${currentSession === s.id 
                      ? "rgba(255,160,0,.25)" 
                      : "transparent"}`,
                    transition: "all .2s ease",
                  }}
                  onMouseEnter={e => {
                    if (currentSession !== s.id) {
                      e.currentTarget.style.background = th.isDark ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.03)";
                    }
                  }}
                  onMouseLeave={e => {
                    if (currentSession !== s.id) {
                      e.currentTarget.style.background = "transparent";
                    }
                  }}
                >
                  {/* Icon */}
                  {editingSessionId !== s.id && (
                    <span style={{ flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      {currentSession === s.id ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: th.isDark ? "var(--c-accent)" : "var(--c-accent-2)" }}>
                          <path d="M12 2L14.5 7.5L20 10L14.5 12.5L12 18L9.5 12.5L4 10L9.5 7.5L12 2Z" />
                        </svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, color: th.text }}>
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                      )}
                    </span>
                  )}

                  {/* Title or inline input */}
                  {editingSessionId === s.id ? (
                    <form
                      style={{ flex: 1, display: "flex", alignItems: "center", gap: 4 }}
                      onSubmit={e => { e.preventDefault(); commitRename(s.id); }}
                    >
                      <input
                        autoFocus
                        value={editingTitle}
                        onChange={e => setEditingTitle(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Escape') cancelRename(); }}
                        onClick={e => e.stopPropagation()}
                        maxLength={120}
                        style={{
                          flex: 1,
                          fontSize: 12,
                          fontFamily: "var(--font-body)",
                          padding: "3px 7px",
                          borderRadius: 6,
                          border: "1px solid var(--c-accent)",
                          background: th.isDark ? "#2D2D2D" : "#fff",
                          color: th.text,
                          outline: "none",
                          minWidth: 0,
                        }}
                      />
                      {/* Confirm */}
                      <button
                        type="submit"
                        onClick={e => e.stopPropagation()}
                        style={{ background: "none", border: "none", cursor: "pointer", color: "#5EC995", padding: "2px 3px", display: "flex", flexShrink: 0 }}
                        title="Save"
                      >
                        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.8} strokeLinecap="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </button>
                      {/* Cancel */}
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); cancelRename(); }}
                        style={{ background: "none", border: "none", cursor: "pointer", color: th.isDark ? "rgba(248,113,113,.75)" : "#DC2626", padding: "2px 3px", display: "flex", flexShrink: 0 }}
                        title="Cancel"
                      >
                        <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.8} strokeLinecap="round">
                          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </form>
                  ) : (
                    <span 
                      style={{
                        flex: 1,
                        fontSize: 13,
                        fontWeight: currentSession === s.id ? 600 : 500,
                        overflow: "hidden",
                        whiteSpace: "nowrap",
                        textOverflow: "ellipsis",
                      }}
                      onMouseEnter={e => {
                        const container = e.currentTarget;
                        const textEl = container.firstChild;
                        if (!textEl) return;
                        const overflow = textEl.scrollWidth - container.clientWidth;
                        if (overflow > 0) {
                          textEl.style.setProperty('--marquee-dist', `-${overflow}px`);
                          textEl.style.setProperty('--marquee-duration', `${overflow / 30}s`);
                          textEl.classList.add('marquee-active');
                        }
                      }}
                      onMouseLeave={e => {
                        const container = e.currentTarget;
                        const textEl = container.firstChild;
                        if (!textEl) return;
                        textEl.classList.remove('marquee-active');
                        textEl.style.transform = "none";
                        textEl.style.transition = "transform 0.3s ease";
                      }}
                    >
                      <span style={{ display: "inline-block" }}>
                        {s.title}
                      </span>
                    </span>
                  )}

                  {/* Action buttons — hidden until hover, only when not editing */}
                  {editingSessionId !== s.id && (
                    <button
                      className="sb-del"
                      title="Delete conversation"
                      onClick={e => { e.stopPropagation(); deleteSession(s.id); }}
                      style={{
                        flexShrink: 0,
                        background: "transparent",
                        border: "none",
                        borderRadius: 6,
                        color: th.isDark ? "rgba(248,113,113,.75)" : "#DC2626",
                        cursor: "pointer",
                        padding: "3px 5px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <path d="M10 11v6M14 11v6M9 6V4h6v2" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* ③ YOUR DOCUMENTS ────── */}
          <div style={{ padding: "10px 16px 11px", borderTop: `1px solid ${th.divider}`, flexShrink: 0 }}>
            <button
              id="btn-your-documents"
              onClick={() => setShowDocsModal(true)}
              style={{ 
                width: "100%", 
                padding: "10px 12px", 
                borderRadius: 11, 
                fontSize: 12, 
                fontWeight: 600, 
                cursor: "pointer", 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center", 
                gap: 8, 
                fontFamily: "var(--font-body)", 
                transition: "all .15s", 
                background: "var(--c-accent-soft)", 
                border: "1px solid var(--c-accent-dim)", 
                color: th.isDark ? "var(--c-accent)" : "var(--c-accent-2)" 
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--c-accent-dim)"; e.currentTarget.style.transform = "translateY(-1px)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "var(--c-accent-soft)"; e.currentTarget.style.transform = "none"; }}
            >
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              Your Documents
            </button>
          </div>

          {/* ④ USER FOOTER ─────────────────────── */}
          <div style={{ padding: "14px 16px", borderTop: `1px solid ${th.divider}`, flexShrink: 0, background: th.isDark ? "rgba(255,255,255,0.01)" : "transparent" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, color: "var(--c-text)", fontFamily: "var(--font-display)", boxShadow: "0 2px 8px var(--c-accent-glow)" }}>
                {user?.name?.[0].toUpperCase() || "U"}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: th.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.name || "User"}</p>
                <p style={{ fontSize: 11, color: th.faint, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.email}</p>
              </div>
              <button onClick={logout} className="btn-icon" style={{ borderRadius: 8, padding: 8 }}>
                <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            </div>
          </div>

        </div>
      </aside>

      {/* ══════════════════════════════════════
          MAIN
      ══════════════════════════════════════ */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>

        {/* HEADER */}
        <header className="glass" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: isTiny ? "0 8px" : "0 18px", height: 60, flexShrink: 0, borderBottom: `1px solid ${th.hdrBdr}`, gap: isTiny ? 4 : 12, position: "sticky", top: 0, zIndex: 100 }}>
          <div style={{ display: "flex", alignItems: "center", gap: isTiny ? 6 : 10, minWidth: 0, flex: 1 }}>
            {/* Hamburger */}
            <button onClick={() => setSidebarOpen(v => !v)} className="btn-icon" style={{ borderRadius: 10, flexShrink: 0 }}>
              <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>


            {/* Logo — only when sidebar is closed */}
            {!sidebarOpen && !isMobile && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 4, flexShrink: 0 }}>
                <div style={{ width: 26, height: 26, borderRadius: 8, background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-display)", fontSize: 12, fontWeight: 700, color: "var(--c-text)", boxShadow: "0 0 14px var(--c-accent-glow)", flexShrink: 0 }}>D</div>
                <span className="text-display" style={{ fontSize: 16, color: th.text }}>DocsChat</span>
              </div>
            )}


            <div style={{ width: 1, height: 20, background: th.divider, flexShrink: 0, margin: "0 4px" }} />

            {/* Model + Embed dropdowns */}
            <Dropdown label={isMobile ? null : "Model"} value={provider} onChange={v => { setProvider(v); if (textareaRef.current) textareaRef.current.placeholder = `Ask ${MODEL_OPTS.find(o => o.value === v)?.label}…`; }} options={MODEL_OPTS} isDark={th.isDark} />
            {!isMobile && <Dropdown label="Embed" value={embeddingProvider} onChange={setEmbP} options={EMBED_OPTS} isDark={th.isDark} />}

            <div style={{ width: 1, height: 20, background: th.divider, flexShrink: 0, margin: "0 4px", display: isMobile ? "none" : "block" }} />


            {/* Web Search Toggle */}
            <button
              onClick={() => setWebSearch(v => !v)}
              className="btn"
              style={{
                width: isMobile ? 34 : "auto",
                height: 34,
                padding: isMobile ? 0 : "0 14px",
                borderRadius: 12,
                fontSize: 11.5,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: ".04em",
                border: webSearch ? "none" : `1px solid ${th.bdr}`,
                background: webSearch ? "var(--g-accent)" : (th.isDark ? "rgba(255,255,255,.04)" : "#F0EDE6"),
                color: webSearch ? "var(--c-text)" : th.muted,
                boxShadow: webSearch ? "0 4px 12px var(--c-accent-glow)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0
              }}
            >


              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: isMobile ? 0 : 6 }}>
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
              {!isMobile && "Web"}

            </button>


            {/* Agent Mode Toggle */}
            <button
              onClick={() => {
                if (!agentMode) {
                  // If turning ON, try to get GPS
                  if ("geolocation" in navigator) {
                    navigator.geolocation.getCurrentPosition(
                      (pos) => {
                        const { latitude: lat, longitude: lon } = pos.coords;
                        setLatitude(lat);
                        setLongitude(lon);
                        localStorage.setItem("gps_lat", lat);
                        localStorage.setItem("gps_lon", lon);
                        setAgentMode(true);
                      },
                      (err) => {
                        console.error("Geolocation error:", err);
                        // Try to use localStorage fallback if available
                        const savedLat = localStorage.getItem("gps_lat");
                        const savedLon = localStorage.getItem("gps_lon");
                        if (savedLat && savedLon) {
                          setLatitude(parseFloat(savedLat));
                          setLongitude(parseFloat(savedLon));
                        } else {
                          alert("For accurate weather, please allow location access. Falling back to IP detection.");
                        }
                        setAgentMode(true);
                      }
                    );
                  } else {
                    setAgentMode(true);
                  }
                } else {
                  setAgentMode(false);
                }
              }}
              className="btn"
              style={{
                width: isTiny ? 34 : "auto",
                height: 34,
                padding: isTiny ? 0 : "0 14px",
                borderRadius: 12,
                fontSize: 11.5,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: ".04em",
                border: agentMode ? "none" : `1px solid ${th.bdr}`,
                background: agentMode ? "var(--g-accent)" : (th.isDark ? "rgba(255,255,255,.04)" : "#F0EDE6"),
                color: agentMode ? "var(--c-text)" : th.muted,
                boxShadow: agentMode ? "0 4px 12px var(--c-accent-glow)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0
              }}
            >


              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: isMobile ? 0 : 6 }}>
                <rect x="3" y="11" width="18" height="10" rx="2" />
                <circle cx="12" cy="5" r="2" />
                <path d="M12 7v4" />
                <line x1="8" y1="16" x2="8" y2="16" />
                <line x1="16" y1="16" x2="16" y2="16" />
              </svg>
              {!isMobile && "Agent"}

            </button>
          </div>



          {/* RIGHT: Theme switcher dropdown */}
          <div ref={themeMenuRef} style={{ position: "relative" }}>
            <button 
              onClick={() => setShowThemeMenu(v => !v)} 
              className="btn-ghost btn-sm" 
              style={{ 
                width: 38, 
                height: 38, 
                borderRadius: 12, 
                padding: 0, 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center",
                background: showThemeMenu ? (th.isDark ? "rgba(255,255,255,0.06)" : "#F0EDE6") : "transparent",
                border: showThemeMenu ? "1px solid var(--c-border-mid)" : "1px solid transparent",
                position: "relative"
              }}
              title="Theme Settings"
            >
              <span style={{ 
                position: "absolute", 
                top: 4, 
                right: 4, 
                width: 8, 
                height: 8, 
                borderRadius: "50%", 
                background: "var(--c-accent)",
                boxShadow: "0 0 8px var(--c-accent-glow)"
              }} />

              {themeMode === "dark" ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              )}
            </button>

            {showThemeMenu && (
              <div style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                width: 240,
                background: th.isDark ? "rgba(22, 20, 16, 0.95)" : "rgba(255, 255, 255, 0.98)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                border: `1px solid ${th.isDark ? "rgba(255, 220, 120, 0.12)" : "#CEC9BC"}`,
                borderRadius: 16,
                padding: 16,
                boxShadow: "0 10px 32px rgba(0,0,0,0.35)",
                zIndex: 1000,
                display: "flex",
                flexDirection: "column",
                gap: 14,
                animation: "pop 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) both"
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em", color: th.isDark ? "rgba(240,237,230,0.4)" : "#9A9080" }}>
                  Theme Options
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: th.muted }}>Accent Color</div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    {[
                      { id: "blue", name: "Blue", hex: "#38BDF8" },
                      { id: "purple", name: "Purple", hex: "#A855F7" },
                      { id: "cyan", name: "Cyan", hex: "#06B6D4" },
                      { id: "emerald", name: "Emerald", hex: "#10B981" }
                    ].map(c => {
                      const isActive = themeColor === c.id;
                      return (
                        <button
                          key={c.id}
                          onClick={() => setThemeColor(c.id)}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: "50%",
                            background: c.hex,
                            border: isActive ? `3px solid ${th.isDark ? "#fff" : "#27251D"}` : `1px solid ${th.isDark ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.15)"}`,
                            boxShadow: isActive ? `0 0 12px ${c.hex}` : "none",
                            cursor: "pointer",
                            transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                            position: "relative",
                            padding: 0
                          }}
                          title={c.name}
                          onMouseEnter={e => {
                            if (!isActive) e.currentTarget.style.transform = "scale(1.15)";
                          }}
                          onMouseLeave={e => {
                            if (!isActive) e.currentTarget.style.transform = "scale(1)";
                          }}
                        >
                          {isActive && (
                            <span style={{
                              position: "absolute",
                              inset: -6,
                              borderRadius: "50%",
                              border: `1.5px solid ${c.hex}`,
                              animation: "pulseAccent 1.6s infinite"
                            }} />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div style={{ height: "1px", background: th.divider }} />

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: th.muted }}>Appearance</div>
                  <div style={{ 
                    display: "flex", 
                    background: th.isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)", 
                    borderRadius: 10, 
                    padding: 3, 
                    gap: 4 
                  }}>
                    {[
                      { id: "dark", name: "Dark", icon: "🌙" },
                      { id: "light", name: "Light", icon: "☀️" }
                    ].map(modeOpt => {
                      const isModeActive = themeMode === modeOpt.id;
                      return (
                        <button
                          key={modeOpt.id}
                          onClick={() => setThemeMode(modeOpt.id)}
                          style={{
                            flex: 1,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 6,
                            padding: "6px 0",
                            fontSize: 12,
                            fontWeight: 600,
                            border: "none",
                            borderRadius: 7,
                            background: isModeActive ? (th.isDark ? "#2D2D2D" : "#FFFFFF") : "transparent",
                            color: isModeActive ? th.text : th.muted,
                            cursor: "pointer",
                            boxShadow: isModeActive && !th.isDark ? "0 2px 6px rgba(0,0,0,0.06)" : "none",
                            transition: "all 0.15s"
                          }}
                        >
                          <span>{modeOpt.icon}</span>
                          <span>{modeOpt.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>

        </header>

        {/* MESSAGES */}
        <div style={{ flex: 1, overflowY: "auto", background: th.msg }}>
          <div style={{ maxWidth: "100%", margin: "0", padding: "28px 20px 14px", display: "flex", flexDirection: "column", gap: 0 }}>
            {messages.map((msg, i) => (
              <MessageItem
                key={i}
                msg={msg}
                i={i}
                th={th}
                isMobile={isMobile}
                editingMsgIndex={editingMsgIndex}
                editValue={editValue}
                setEditValue={setEditValue}
                saveEdit={saveEdit}
                setEditingMsgIndex={setEditingMsgIndex}
                copyToClipboard={copyToClipboard}
                copyingIndex={copyingIndex}
                handleEdit={handleEdit}
                retryMessage={retryMessage}
                handleFeedback={handleFeedback}
                hoveredMsgIdx={hoveredMsgIdx}
                setHoveredMsgIdx={setHoveredMsgIdx}
                loadingSuggestions={loadingSuggestions}
                messagesLength={messages.length}
                suggestions={suggestions}
                sendMessage={sendMessage}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* INPUT */}
        <div style={{ flexShrink: 0, padding: "12px 20px 16px", background: th.inp, borderTop: `1px solid ${th.inpBdr}` }}>
          <div style={{ maxWidth: "100%", margin: "0" }}>

            {/* Upload status pill */}
            {uploadMsg && (
              <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 11px", marginBottom: 8, borderRadius: 99, fontSize: 11, fontFamily: "var(--font-mono)", background: uploadMsg.startsWith("✓") ? "rgba(94,201,149,.09)" : "rgba(239,68,68,.08)", border: `1px solid ${uploadMsg.startsWith("✓") ? "rgba(94,201,149,.22)" : "rgba(239,68,68,.18)"}`, color: uploadMsg.startsWith("✓") ? "#5EC995" : "#F87171" }}>{uploadMsg}</div>
            )}

            {selectedImage && <ImgChip image={selectedImage} onClear={clearImage} isDark={th.isDark} />}

            <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
              {/* Attach button + popup */}
              <div style={{ position: "relative", flexShrink: 0 }}>
                <button onClick={() => setShowAttach(v => !v)} disabled={uploading} style={{ ...th.attBtn, width: 44, height: 44, borderRadius: 11, cursor: uploading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all .16s", opacity: uploading ? .4 : 1, position: "relative" }}>
                  {uploading
                    ? <span style={{ width: 14, height: 14, border: "2px solid var(--c-accent-dim)", borderTopColor: "var(--c-accent)", borderRadius: "50%", animation: "spin .7s linear infinite", display: "block" }} />
                    : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
                  }
                  {(selectedImage || docStatus === "indexed") && !uploading && (
                    <span style={{ position: "absolute", top: 5, right: 5, width: 7, height: 7, borderRadius: "50%", background: "var(--c-accent)", border: `2px solid ${th.inp}` }} />
                  )}
                </button>
                {showAttach && (
                  <div onMouseLeave={() => setShowAttach(false)} style={{ position: "absolute", bottom: "calc(100% + 8px)", left: 0, background: th.isDark ? "#2D2D2D" : "#FFFFFF", border: `1px solid ${th.bdr2}`, borderRadius: 12, overflow: "hidden", minWidth: 212, boxShadow: "0 14px 40px rgba(0,0,0,.35)", zIndex: 200 }}>
                    <div style={{ padding: "5px 13px 2px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ fontSize: 9.5, color: th.faint, fontFamily: "var(--font-mono)", letterSpacing: ".09em", textTransform: "uppercase" }}>Attach file</div>
                      <button onClick={() => setShowAttach(false)} style={{ background: "none", border: "none", cursor: "pointer", color: th.faint, padding: "4px", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", transition: "background .12s" }}
                        onMouseEnter={e => e.currentTarget.style.background = "rgba(0,0,0,.05)"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                      </button>
                    </div>
                    {[
                      { 
                        icon: (
                          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                          </svg>
                        ), 
                        title: "PDF / DOCX / TXT", 
                        sub: "Index & search", 
                        accept: ".pdf,.docx,.txt" 
                      },
                      { 
                        icon: (
                          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <circle cx="8.5" cy="8.5" r="1.5"></circle>
                            <polyline points="21 15 16 10 5 21"></polyline>
                          </svg>
                        ), 
                        title: "Image", 
                        sub: "Vision Q&A", 
                        accept: "image/*" 
                      },
                      { 
                        icon: (
                          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 18V5l12-2v13"></path>
                            <circle cx="6" cy="18" r="3"></circle>
                            <circle cx="18" cy="16" r="3"></circle>
                          </svg>
                        ), 
                        title: "Audio / Video", 
                        sub: "MP3, WAV, M4A, MP4 · Whisper", 
                        accept: ".mp3,.wav,.m4a,.ogg,.flac,.webm,.mp4,.mpeg,.mpga" 
                      },
                    ].map(opt => (
                      <button key={opt.title} onClick={() => { setShowAttach(false); if (fileInputRef.current) { fileInputRef.current.accept = opt.accept; fileInputRef.current.click(); } }} style={{ width: "100%", display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", background: "transparent", border: "none", borderTop: `1px solid ${th.bdr}`, cursor: "pointer", textAlign: "left", transition: "background .12s" }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--c-accent-soft)"}
                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                      >
                        <span style={{ color: th.isDark ? "var(--c-accent)" : "var(--c-accent-2)", display: "flex", alignItems: "center", justifyContent: "center", width: 24, height: 24 }}>
                          {opt.icon}
                        </span>
                        <div>
                          <p style={{ fontSize: 12.5, fontWeight: 600, color: th.text, marginBottom: 1 }}>{opt.title}</p>
                          <p style={{ fontSize: 10.5, color: th.muted }}>{opt.sub}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Textarea */}
              <textarea 
                ref={textareaRef} 
                value={input} 
                onChange={e => { setInput(e.target.value); resizeTA(); }} 
                onKeyDown={handleKeyDown} 
                placeholder={isTiny ? "Msg..." : `Ask ${MODEL_OPTS.find(o => o.value === provider)?.label ?? provider}…`} 
                disabled={loading} 
                rows={1} 
                style={{ 
                  flex: 1, 
                  resize: "none", 
                  borderRadius: 11, 
                  padding: isMobile ? "11px 14px" : "11px 16px", 
                  fontSize: isMobile ? 14.5 : 15.5, 
                  lineHeight: 1.65, 
                  overflow: "hidden", 
                  minHeight: 44,
                  maxHeight: 220, 
                  fontFamily: "var(--font-body)", 
                  transition: "border-color .15s ease, box-shadow .15s ease, opacity .15s ease", 
                  boxShadow: th.isDark ? "0 4px 24px rgba(0,0,0,0.4), 0 1px 1px rgba(255,255,255,0.05) inset" : "0 4px 20px rgba(0,0,0,0.06), 0 1px 0 rgba(255,255,255,0.8) inset",
                  opacity: loading ? .55 : 1, 
                  ...th.textarea 
                }}
                onFocus={e => { e.target.style.borderColor = "var(--c-accent)"; e.target.style.boxShadow = "0 0 0 3px var(--c-accent-dim)"; }}
                onBlur={e => { e.target.style.borderColor = ""; e.target.style.boxShadow = "none"; }}
              />


              {/* Voice */}
              <VoiceInput
                th={th}
                onTranscript={(text) => { setInput(prev => (prev + " " + text).trim()); resizeTA(); }}
                onSpeechEnd={() => { if (latestInputRef.current.trim() || latestImgRef.current) sendMessage(null, latestInputRef.current); }}
                onError={err => console.error("Voice:", err)}
              />

              {/* Send */}
              <button onClick={sendMessage} disabled={loading || (!input.trim() && !selectedImage)} style={{ ...th.sendBtn, border: "none", borderRadius: 11, width: 44, height: 44, cursor: loading || (!input.trim() && !selectedImage) ? "not-allowed" : "pointer", opacity: loading || (!input.trim() && !selectedImage) ? .28 : 1, display: "flex", alignItems: "center", justifyContent: "center", transition: "all .17s", flexShrink: 0 }}
                onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = "scale(1.05)"; }}
                onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
              >
                {loading
                  ? <span style={{ width: 16, height: 16, border: "2px solid rgba(0,0,0,.25)", borderTopColor: "var(--c-text)", borderRadius: "50%", animation: "spin .7s linear infinite", display: "block" }} />
                  : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--c-text)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" /></svg>
                }
              </button>
            </div>

            <p style={{ textAlign: "center", fontSize: 11, color: th.hint, marginTop: 7 }}>
              Enter to send · Shift+Enter for new line ·{" "}
              <span style={{ color: th.hintEm }}>📎 attach PDF / DOCX / TXT or image</span>
            </p>
          </div>
        </div>
      </main>
      
      {showDocsModal && (
        <DocumentsModal 
          onClose={() => setShowDocsModal(false)} 
          darkMode={th.isDark} 
          th={th} 
        />
      )}
    </div>
  );
}