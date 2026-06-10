"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthHeaders } from "../lib/api-auth";

type UploadState = "idle" | "uploading" | "done" | "error";

export function uploadButtonLabel(state: UploadState): string {
  if (state === "uploading") return "Processing...";
  if (state === "done") return "Processed";
  if (state === "error") return "Try again";
  return "Upload invoice";
}

type FileProgress = { name: string; done: boolean; error: boolean; invoiceId?: string };

export function UploadPanel() {
  const router = useRouter();
  const authHeaders = useAuthHeaders();
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("Upload one or more PDF invoices to extract fields.");
  const [progress, setProgress] = useState<FileProgress[]>([]);

  async function uploadOne(file: File): Promise<string | null> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${apiUrl}/api/invoices/upload`, {
      method: "POST",
      headers: await authHeaders(),
      body: fd,
    });
    if (!res.ok) throw new Error(`${res.status}`);
    const body = await res.json() as { invoice_id?: string };
    return body.invoice_id ?? null;
  }

  async function onSubmit(formData: FormData) {
    const files = Array.from(inputRef.current?.files ?? []);
    if (files.length === 0) {
      setState("error");
      setMessage("Choose at least one PDF invoice.");
      return;
    }

    setState("uploading");
    setProgress(files.map((f) => ({ name: f.name, done: false, error: false })));
    setMessage(`Uploading ${files.length} file${files.length > 1 ? "s" : ""}…`);

    const results: Array<{ id: string | null; error: boolean }> = [];
    for (let i = 0; i < files.length; i++) {
      try {
        const id = await uploadOne(files[i]);
        results.push({ id, error: false });
        setProgress((prev) => prev.map((p, idx) => idx === i ? { ...p, done: true, invoiceId: id ?? undefined } : p));
      } catch {
        results.push({ id: null, error: true });
        setProgress((prev) => prev.map((p, idx) => idx === i ? { ...p, done: true, error: true } : p));
      }
    }

    const succeeded = results.filter((r) => !r.error).length;
    const failed = results.length - succeeded;
    setState(failed === results.length ? "error" : "done");

    if (results.length === 1 && results[0].id) {
      setMessage("Invoice queued for processing. Opening review screen…");
      router.push(`/invoices/${results[0].id}`);
    } else {
      setMessage(
        failed > 0
          ? `${succeeded} uploaded, ${failed} failed. Opening invoices list…`
          : `${succeeded} invoice${succeeded > 1 ? "s" : ""} queued for processing.`
      );
      router.push("/invoices");
      router.refresh();
    }
  }

  const messageColor =
    state === "error" ? "var(--error)" : state === "done" ? "var(--success)" : "var(--text-muted)";

  return (
    <form action={onSubmit} className="card">
      <h2 className="card-title">Upload invoices</h2>
      <p style={{ marginTop: "0.5rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
        Select one or more PDF invoices — all are queued simultaneously.
      </p>

      <div
        className="upload-zone"
        style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", padding: "2rem 1.5rem" }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <polyline points="16 12 12 8 8 12" />
          <line x1="12" y1="8" x2="12" y2="16" />
        </svg>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", textAlign: "center", margin: 0 }}>
          Drag and drop or choose files
        </p>
        <input
          ref={inputRef}
          name="file"
          type="file"
          accept="application/pdf,.txt"
          multiple
          className="input"
          style={{ maxWidth: "100%" }}
        />
      </div>

      <button className="btn btn-accent btn-lg" type="submit" style={{ width: "100%", marginTop: "16px" }} disabled={state === "uploading"}>
        {state === "uploading" ? `Uploading… (${progress.filter((p) => p.done).length}/${progress.length})` : uploadButtonLabel(state)}
      </button>

      {progress.length > 1 && (
        <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "4px" }}>
          {progress.map((p, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
              <span style={{ color: p.error ? "var(--error)" : p.done ? "var(--success)" : "var(--muted)" }}>
                {p.error ? "✗" : p.done ? "✓" : "·"}
              </span>
              <span style={{ color: "var(--text-muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</span>
            </div>
          ))}
        </div>
      )}

      <p style={{ marginTop: "1rem", fontSize: "0.875rem", color: messageColor, transition: "color 0.2s ease" }}>
        {message}
      </p>
    </form>
  );
}
