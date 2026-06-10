"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useAuthHeaders } from "../lib/api-auth";

type TextItem = {
  str: string;
  transform: number[];
  width: number;
  height: number;
};

type Highlight = {
  field: string;
  value: string;
  color: string;
  active: boolean;
};

type PageHighlightRect = {
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  active: boolean;
};

const FIELD_COLORS: Record<string, string> = {
  vendor_name: "#818cf8",
  vendor_vat: "#a78bfa",
  vendor_iban: "#60a5fa",
  invoice_number: "#34d399",
  invoice_date: "#f59e0b",
  due_date: "#fb923c",
  subtotal: "#10b981",
  vat_amount: "#6ee7b7",
  total_amount: "#ef4444",
  currency: "#94a3b8",
};

function getColor(field: string) {
  return FIELD_COLORS[field] ?? "#94a3b8";
}

export function highlightCandidates(value: string): string[] {
  const trimmed = value.trim();
  const candidates = new Set<string>([trimmed]);
  const normalizedNumber = trimmed.replace(/\s/g, "").replace(",", ".");

  if (/^-?\d+(?:\.\d+)?$/.test(normalizedNumber)) {
    const parsed = Number(normalizedNumber);
    if (Number.isFinite(parsed)) {
      const fixed = parsed.toFixed(2);
      candidates.add(normalizedNumber);
      candidates.add(normalizedNumber.replace(".", ","));
      candidates.add(fixed);
      candidates.add(fixed.replace(".", ","));
    }
  }

  return [...candidates].filter(Boolean);
}

function findRects(
  items: TextItem[],
  vt: number[],
  value: string,
  field: string,
  active: boolean
): PageHighlightRect[] {
  const color = getColor(field);
  const needles = highlightCandidates(value)
    .map((candidate) => candidate.toLowerCase().replace(/\s+/g, " "))
    .filter((candidate) => candidate.length >= 2);
  if (needles.length === 0) return [];

  type Word = { text: string; transform: number[]; width: number; height: number };
  const words: Word[] = [];
  items.forEach((item) => {
    item.str.split(/(\s+)/).forEach((part) => {
      if (part.trim()) words.push({ text: part, transform: item.transform, width: item.width, height: item.height });
    });
  });

  const rects: PageHighlightRect[] = [];

  for (const needle of needles) {
    const needleWords = needle.split(/\s+/);
    for (let i = 0; i <= words.length - needleWords.length; i++) {
      const slice = words.slice(i, i + needleWords.length);
      if (slice.map((w) => w.text.toLowerCase()).join(" ") !== needle) continue;

      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      slice.forEach((w) => {
        const [, , , scaleY, tx, ty] = w.transform;
        const h = Math.abs(scaleY) || w.height || 12;
        const cx = vt[0] * tx + vt[2] * ty + vt[4];
        const cy = vt[1] * tx + vt[3] * ty + vt[5];
        minX = Math.min(minX, cx);
        minY = Math.min(minY, cy - h * Math.abs(vt[3] || 1));
        maxX = Math.max(maxX, cx + w.width * Math.abs(vt[0] || 1));
        maxY = Math.max(maxY, cy);
      });

      if (minX < maxX && minY < maxY) {
        rects.push({ x: minX, y: minY, w: maxX - minX, h: maxY - minY, color, active });
      }
    }
  }
  return rects;
}

type Props = {
  fileUrl: string;
  highlights: Highlight[];
  scale?: number;
};

type PageFrame = {
  canvas: HTMLCanvasElement;
  items: TextItem[];
  vt: number[];
  width: number;
  height: number;
};

export default function InvoicePdfViewer({ fileUrl, highlights, scale = 1.5 }: Props) {
  const authHeaders = useAuthHeaders();
  const containerRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [frames, setFrames] = useState<PageFrame[]>([]);

  // Render PDF once per fileUrl/scale — highlights are computed separately
  const renderPdf = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pdfjsLib = await import("pdfjs-dist");
      pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

      // Pre-fetch as ArrayBuffer to avoid pdfjs streaming/ReadableStream issues
      const response = await fetch(fileUrl, { headers: await authHeaders() });
      if (!response.ok) throw new Error(`Failed to fetch PDF: ${response.status}`);
      const data = await response.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data }).promise;
      setNumPages(pdf.numPages);

      const result: PageFrame[] = [];
      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page = await pdf.getPage(pageNum);
        const viewport = page.getViewport({ scale });

        const canvas = document.createElement("canvas");
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        const ctx = canvas.getContext("2d")!;

         
        await (page.render as any)({ canvasContext: ctx, viewport }).promise;

        const textContent = await page.getTextContent();
        result.push({
          canvas,
          items: textContent.items as TextItem[],
          vt: viewport.transform as number[],
          width: canvas.width,
          height: canvas.height,
        });
      }
      setFrames(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [fileUrl, scale, authHeaders]); // highlights NOT a dependency — rects computed below

  useEffect(() => { renderPdf(); }, [renderPdf]);

  // Recompute highlight rects cheaply whenever highlights change
  const pageRects = useMemo(() =>
    frames.map((fr) => {
      const rects: PageHighlightRect[] = [];
      for (const hl of highlights) {
        if (!hl.value || hl.value.length < 2) continue;
        rects.push(...findRects(fr.items, fr.vt, hl.value, hl.field, hl.active));
      }
      return rects;
    }),
    [frames, highlights]
  );

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--muted)", fontSize: "13px" }}>
        Loading PDF…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "20px", color: "var(--error)", fontSize: "13px" }}>
        Could not render PDF: {error}
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ overflow: "auto", height: "100%", padding: "16px", background: "#f0f0f0", display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
      {frames.map((fr, idx) => (
        <div key={idx} style={{ position: "relative", boxShadow: "0 2px 8px rgba(0,0,0,0.15)", background: "#fff" }}>
          <canvas
            ref={(el) => { if (el) { el.getContext("2d")!.drawImage(fr.canvas, 0, 0); } }}
            width={fr.width}
            height={fr.height}
            style={{ display: "block", maxWidth: "100%" }}
          />
          <svg
            style={{ position: "absolute", top: 0, left: 0, width: fr.width, height: fr.height, pointerEvents: "none" }}
            viewBox={`0 0 ${fr.width} ${fr.height}`}
          >
            {(pageRects[idx] ?? []).map((rect, ri) => (
              <rect
                key={ri}
                x={rect.x} y={rect.y} width={rect.w} height={rect.h}
                fill={rect.color} fillOpacity={rect.active ? 0.35 : 0.18}
                stroke={rect.color} strokeWidth={rect.active ? 2 : 1} strokeOpacity={0.8}
                rx={2}
              />
            ))}
          </svg>
        </div>
      ))}
      {numPages > 0 && (
        <p style={{ fontSize: "11px", color: "var(--muted)", textAlign: "center" }}>
          {numPages} page{numPages !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
