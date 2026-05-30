"use client";

import { useEffect, useRef, useMemo, lazy, Suspense } from "react";

const InvoicePdfViewer = lazy(() => import("./invoice-pdf-viewer"));

type FieldHighlight = { field: string; value: string; color: string; active: boolean };

type Props = {
  fileUrl: string | null;
  rawText: string | null;
  fieldHighlights?: FieldHighlight[];
  activeHighlight?: string | null;
  externalTab?: "pdf" | "text";
  onTabChange?: (tab: "pdf" | "text") => void;
};

const FIELD_COLORS: Record<string, string> = {
  vendor_name: "#818cf8", vendor_vat: "#a78bfa", vendor_iban: "#60a5fa",
  invoice_number: "#34d399", invoice_date: "#f59e0b", due_date: "#fb923c",
  subtotal: "#10b981", vat_amount: "#6ee7b7", total_amount: "#ef4444", currency: "#94a3b8",
};

function buildHighlightedParts(text: string, allValues: string[], activeValue: string | null) {
  const escaped = allValues
    .filter((t) => typeof t === "string" && t.trim().length > 1)
    .sort((a, b) => b.length - a.length)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));

  if (!escaped.length) return [{ text, type: "plain" as const }];
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      const isActive = activeValue && part.toLowerCase() === activeValue.toLowerCase();
      return { text: part, type: isActive ? ("active" as const) : ("highlight" as const) };
    }
    return { text: part, type: "plain" as const };
  });
}

export default function InvoicePdfPanel({
  fileUrl,
  rawText,
  fieldHighlights = [],
  activeHighlight = null,
  externalTab,
  onTabChange,
}: Props) {
  const activeRef = useRef<HTMLElement | null>(null);
  const tab = externalTab ?? (fileUrl ? "pdf" : "text");

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeHighlight]);

  const allValues = fieldHighlights.map((h) => h.value).filter(Boolean);
  const parts = useMemo(() => {
    if (!rawText) return null;
    return buildHighlightedParts(rawText, allValues, activeHighlight);
  }, [rawText, allValues, activeHighlight]);

  let firstActiveSet = false;

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 14px", fontSize: "12px", fontWeight: active ? 700 : 500,
    color: active ? "var(--accent)" : "var(--muted)", background: "none", border: "none",
    borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
    cursor: "pointer", transition: "color 0.15s",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: "4px", padding: "0 16px", borderBottom: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0, alignItems: "center" }}>
        {fileUrl && <button style={tabStyle(tab === "pdf")} onClick={() => onTabChange?.("pdf")}>PDF</button>}
        <button style={tabStyle(tab === "text")} onClick={() => onTabChange?.("text")}>Raw text</button>
        {fieldHighlights.length > 0 && (
          <div style={{ marginLeft: "auto", display: "flex", gap: "6px", alignItems: "center", padding: "0 8px", flexWrap: "wrap" }}>
            {fieldHighlights.slice(0, 6).map((h) => (
              <span key={h.field} style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "10px", color: "var(--text)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: FIELD_COLORS[h.field] ?? "#94a3b8", flexShrink: 0 }} />
                {h.field.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
        {tab === "pdf" && fileUrl ? (
          <Suspense fallback={<div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--muted)", fontSize: "13px" }}>Loading PDF…</div>}>
            <InvoicePdfViewer
              fileUrl={fileUrl}
              highlights={fieldHighlights}
            />
          </Suspense>
        ) : (
          <div style={{ height: "100%", overflow: "auto", padding: "20px", background: "#fafafa" }}>
            {rawText ? (
              <pre style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "12px", lineHeight: 1.7, color: "var(--text)", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>
                {parts
                  ? parts.map((part, i) => {
                      if (part.type === "active") {
                        const isFirst = !firstActiveSet;
                        if (isFirst) firstActiveSet = true;
                        return (
                          <mark key={i} ref={isFirst ? (el) => { activeRef.current = el; } : undefined}
                            style={{ background: "#fb923c", color: "#fff", borderRadius: "2px", padding: "0 2px" }}>
                            {part.text}
                          </mark>
                        );
                      }
                      if (part.type === "highlight") {
                        return <mark key={i} style={{ background: "#fef08a", borderRadius: "2px", padding: "0 1px" }}>{part.text}</mark>;
                      }
                      return part.text;
                    })
                  : rawText}
              </pre>
            ) : (
              <p style={{ color: "var(--muted)", fontSize: "13px", textAlign: "center", marginTop: "40px" }}>No text content available.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
