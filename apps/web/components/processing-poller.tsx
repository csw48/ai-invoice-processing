"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export default function ProcessingPoller({ invoiceId }: { invoiceId: string }) {
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${apiUrl}/api/invoices/${invoiceId}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status !== "processing") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          router.refresh();
        }
      } catch {
        // network error — keep polling
      }
    }, 2500);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [invoiceId, router]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "60vh",
      gap: "16px",
      color: "var(--muted)",
    }}>
      <div style={{ fontSize: "32px" }}>⏳</div>
      <p style={{ fontSize: "15px", fontWeight: 600, color: "var(--text)" }}>Extracting invoice fields…</p>
      <p style={{ fontSize: "13px" }}>AI is reading the document. This usually takes 5–15 seconds.</p>
      <p style={{ fontSize: "11px", opacity: 0.6 }}>Page will refresh automatically when complete.</p>
    </div>
  );
}
