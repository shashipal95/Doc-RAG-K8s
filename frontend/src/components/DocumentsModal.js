"use client";

import { useState, useEffect } from "react";
import { authFetch } from "@/lib/auth";

export default function DocumentsModal({ onClose, darkMode = false, th }) {
  const [documents, setDocuments] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [editingDocId, setEditingDocId] = useState(null);
  const [newFilename, setNewFilename] = useState("");
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setIsLoadingDocs(true);
    try {
      const res = await authFetch("/api/v1/documents");
      if (res.ok) {
        const data = await res.json();
        setDocuments(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error("Error loading documents:", error);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("provider", "gemini");
      formData.append("embedding_provider", "gemini");

      const res = await authFetch("/api/v1/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        await loadDocuments();
      } else {
        const error = await res.json();
        alert(`Upload failed: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Upload error:", error);
      alert("Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleView = async (docId) => {
    try {
      const res = await authFetch(`/api/v1/documents/${docId}/view-token`, { method: "POST" });
      if (res.ok) {
        const { token } = await res.json();
        const baseUrl = getBaseUrl();
        window.open(`${baseUrl}/api/v1/documents/view/${token}`, "_blank");
      }
    } catch (e) {
      console.error("View failed:", e);
    }
  };

  const handleDelete = async (docId) => {
    if (!confirm("Delete this document and all its embeddings?")) return;

    try {
      const res = await authFetch(`/api/v1/documents/${docId}`, {
        method: "DELETE",
      });

      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== docId));
      }
    } catch (error) {
      console.error("Delete error:", error);
      alert("Delete failed");
    }
  };

  const handleDownload = async (docId, filename, inline = false) => {
    try {
      const res = await authFetch(`/api/v1/documents/${docId}/download${inline ? "?inline=true" : ""}`);
      if (res.ok) {
        // Get the content type from the response to ensure the blob is typed correctly
        const contentType = res.headers.get("Content-Type") || "application/pdf";
        const blob = await res.blob();
        const typedBlob = new Blob([blob], { type: contentType });
        const url = window.URL.createObjectURL(typedBlob);
        
        if (inline) {
          // Open in a new tab with the correct title if possible
          const newWindow = window.open();
          if (newWindow) {
            newWindow.location.href = url;
          } else {
            // Fallback if popup blocked
            window.location.href = url;
          }
        } else {
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
        }
        // Cleanup URL after some time
        setTimeout(() => window.URL.revokeObjectURL(url), 10000);
      }
    } catch (error) {
      console.error("Download/View error:", error);
    }
  };

  /**
   * Resolves the backend base URL consistently.
   * Priority: NEXT_PUBLIC_API_URL env var → replace :3000→:8000 on localhost → same origin
   */
  const getBaseUrl = () => {
    if (process.env.NEXT_PUBLIC_API_URL) {
      return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
    }
    if (typeof window !== "undefined") {
      return window.location.origin.replace(":3000", ":8000").replace(/\/$/, "");
    }
    return "";
  };



  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatSize = (bytes) => {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "—";
    const now = new Date();
    const date = new Date(dateStr);
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days === 1) return "yesterday";
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  const bgColor = th?.surface || (darkMode ? "#1B1910" : "#FFFFFF");
  const textColor = th?.text || (darkMode ? "#F0EDE6" : "#27251D");
  const mutedColor = th?.muted || (darkMode ? "rgba(240,237,230,.5)" : "#6A6458");
  const borderColor = th?.divider || (darkMode ? "rgba(255,218,100,.08)" : "#E2DDD2");

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.85)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2000,
        padding: 20,
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 800,
          maxHeight: "85vh",
          background: bgColor,
          borderRadius: 20,
          overflow: "hidden",
          boxShadow: "0 30px 70px rgba(0,0,0,0.6)",
          border: `1px solid ${borderColor}`,
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: `1px solid ${borderColor}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)",
          }}
        >
          <div>
            <h2
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: textColor,
                margin: "0 0 2px",
                fontFamily: "var(--font-display)",
              }}
            >
              Your Documents
            </h2>
            <p
              style={{
                fontSize: 12,
                color: mutedColor,
                margin: 0,
                fontFamily: "var(--font-mono)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {documents.length} document{documents.length !== 1 ? "s" : ""} managed
            </p>
          </div>

          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              border: "none",
              background: darkMode ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)",
              color: textColor,
              fontSize: 18,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = "var(--c-accent-dim)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = darkMode
                ? "rgba(255,255,255,0.06)"
                : "rgba(0,0,0,0.05)")
            }
          >
            ×
          </button>
        </div>

        {/* Search and Upload */}
        <div
          style={{
            padding: "16px 24px",
            display: "flex",
            gap: 12,
            borderBottom: `1px solid ${borderColor}`,
          }}
        >
          <div style={{ flex: 1, position: "relative" }}>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              style={{
                width: "100%",
                padding: "10px 16px",
                borderRadius: 12,
                background: darkMode ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.03)",
                border: `1px solid ${borderColor}`,
                color: textColor,
                fontSize: 14,
                outline: "none",
                fontFamily: "var(--font-body)",
              }}
            />
          </div>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "0 18px",
              height: 42,
              borderRadius: 12,
              background: "var(--g-accent)",
              color: "var(--c-text)",
              fontSize: 13,
              fontWeight: 700,
              cursor: isUploading ? "not-allowed" : "pointer",
              border: "none",
              boxShadow: "0 4px 12px var(--c-accent-glow)",
            }}
          >
            {isUploading ? (
              <span
                style={{
                  width: 14,
                  height: 14,
                  border: "2px solid rgba(0,0,0,0.2)",
                  borderTopColor: "#000",
                  borderRadius: "50%",
                  animation: "spin 0.7s linear infinite",
                }}
              />
            ) : (
              "↑ Upload"
            )}
            <input
              type="file"
              onChange={handleUpload}
              disabled={isUploading}
              accept=".pdf,.txt,.docx"
              style={{ display: "none" }}
            />
          </label>
        </div>

        {/* Documents List */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 24px",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {isLoadingDocs ? (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 16,
              }}
            >
              <span
                style={{
                  width: 40,
                  height: 40,
                  border: `3px solid ${borderColor}`,
                  borderTopColor: "var(--c-accent)",
                  borderRadius: "50%",
                  animation: "spin 1s linear infinite",
                }}
              />
              <p
                style={{
                  fontSize: 13,
                  color: mutedColor,
                  margin: 0,
                  fontWeight: 500,
                  fontFamily: "var(--font-mono)",
                }}
              >
                FETCHING DOCUMENTS...
              </p>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div
              style={{
                flex: 1,
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.5 }}>📄</div>
              <p style={{ fontSize: 14, color: mutedColor, margin: 0, fontWeight: 500 }}>
                {searchQuery
                  ? "No documents match your search"
                  : "No documents indexed yet"}
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  style={{
                    padding: "12px 16px",
                    borderRadius: 14,
                    background: darkMode
                      ? "rgba(255,255,255,0.02)"
                      : "rgba(0,0,0,0.02)",
                    border: `1px solid ${borderColor}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    transition: "transform 0.2s",
                  }}
                >
                  {/* File Icon */}
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 10,
                      background: "var(--c-accent-soft)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 20,
                      flexShrink: 0,
                      border: "1px solid var(--c-accent-dim)",
                    }}
                  >
                    {doc.file_type?.includes("pdf") ? (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><text x="12" y="16" fontSize="6" fontWeight="bold" fill="#374151" stroke="none" textAnchor="middle" fontFamily="var(--font-mono)">PDF</text></svg>
                    ) : doc.file_type?.includes("word") ? (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><text x="12" y="16" fontSize="8" fontWeight="bold" fill="#374151" stroke="none" textAnchor="middle" fontFamily="var(--font-mono)">W</text></svg>
                    ) : (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="12" x2="16" y2="12" /><line x1="8" y1="15" x2="16" y2="15" /><rect x="4" y="16" width="16" height="6" rx="1" fill="#3B82F6" stroke="none" /><text x="12" y="21" fontSize="4" fontWeight="bold" fill="#FFFFFF" stroke="none" textAnchor="middle" fontFamily="var(--font-mono)">TXT</text></svg>
                    )}
                  </div>

                  {/* File Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {editingDocId === doc.id ? (
                      <div style={{ display: "flex", gap: 6 }}>
                        <input
                          autoFocus
                          value={newFilename}
                          onChange={(e) => setNewFilename(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRename(doc.id);
                            if (e.key === "Escape") setEditingDocId(null);
                          }}
                          style={{
                            flex: 1,
                            background: darkMode ? "#000" : "#fff",
                            border: "1px solid var(--c-accent)",
                            color: textColor,
                            padding: "4px 8px",
                            borderRadius: 6,
                            fontSize: 14,
                          }}
                        />
                        <button
                          onClick={() => handleRename(doc.id)}
                          style={{
                            background: "var(--c-accent)",
                            border: "none",
                            color: "#000",
                            padding: "4px 10px",
                            borderRadius: 6,
                            cursor: "pointer",
                            fontWeight: 700,
                          }}
                        >
                          Save
                        </button>
                      </div>
                    ) : (
                      <p
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: textColor,
                          margin: "0 0 2px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {doc.filename}
                      </p>
                    )}
                    <p
                      style={{
                        fontSize: 11,
                        color: mutedColor,
                        margin: 0,
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {formatSize(doc.file_size)} · {formatDate(doc.created_at)} ·{" "}
                      {doc.chunks_count} chunks
                    </p>
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>

                    <button
                      onClick={() => handleView(doc.id)}
                      style={{
                        padding: "0 12px",
                        height: 32,
                        borderRadius: 8,
                        background: "transparent",
                        border: `1px solid ${borderColor}`,
                        color: textColor,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      View
                    </button>

                    <button
                      onClick={() => handleDownload(doc.id, doc.filename)}
                      style={{
                        padding: "0 12px",
                        height: 32,
                        borderRadius: 8,
                        background: "transparent",
                        border: `1px solid ${borderColor}`,
                        color: textColor,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      Download
                    </button>


                    <button
                      onClick={() => handleDelete(doc.id)}
                      style={{
                        padding: "0 12px",
                        height: 32,
                        borderRadius: 8,
                        background: "rgba(239,68,68,0.06)",
                        border: "1px solid rgba(239,68,68,0.15)",
                        color: "#f87171",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 24px",
            borderTop: `1px solid ${borderColor}`,
            background: darkMode ? "rgba(255,255,255,0.01)" : "rgba(0,0,0,0.01)",
          }}
        >
          <p
            style={{
              fontSize: 10,
              color: mutedColor,
              margin: 0,
              textAlign: "center",
            }}
          >
            Deleted documents are permanently removed from QdrantDB and the database.
          </p>
        </div>
      </div>

      <style jsx>{`
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}