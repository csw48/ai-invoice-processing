"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthHeaders } from "../lib/api-auth";

type UploadState = "idle" | "uploading" | "done" | "error";

export function uploadButtonLabel(state: UploadState): string {
  if (state === "uploading") return "Processing...";
  if (state === "done") return "Processed";
  if (state === "error") return "Try again";
  return "Upload invoice";
}

export function UploadPanel() {
  const router = useRouter();
  const authHeaders = useAuthHeaders();
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState(
    "Upload a PDF invoice to extract fields and review them."
  );

  async function onSubmit(formData: FormData) {
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setState("error");
      setMessage("Choose a PDF invoice first.");
      return;
    }

    setState("uploading");
    setMessage("Extracting fields...");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(`${apiUrl}/api/invoices/upload`, {
        method: "POST",
        headers: await authHeaders(),
        body: formData,
      });
      if (!response.ok) {
        setState("error");
        setMessage(
          `Upload failed (${response.status}). Check the API server and env vars.`
        );
        return;
      }
      const body = (await response.json()) as {
        invoice_id?: string;
        classification?: { document_type?: string; type_reasoning?: string };
      };
      setState("done");
      const docType = body.classification?.document_type;
      if (docType && docType !== "invoice" && docType !== "credit_note") {
        setMessage(
          `Classified as "${docType}" — not an invoice. Opening review for manual handling...`
        );
      } else {
        setMessage("Invoice processed. Opening review screen...");
      }
      if (body.invoice_id) {
        router.push(`/invoices/${body.invoice_id}`);
      }
    } catch (err) {
      setState("error");
      setMessage(`Upload error: ${(err as Error).message}`);
    }
  }

  const messageColor =
    state === "error"
      ? "var(--error)"
      : state === "done"
      ? "var(--success)"
      : "var(--text-muted)";

  return (
    <form action={onSubmit} className="card">
      <h2 className="card-title">Quick upload</h2>
      <p
        style={{
          marginTop: "0.5rem",
          color: "var(--text-muted)",
          fontSize: "0.875rem",
        }}
      >
        Upload a text-based PDF invoice.
      </p>

      <div
        className="upload-zone"
        style={{
          marginTop: "1.5rem",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px",
          padding: "2rem 1.5rem",
        }}
      >
        {/* Upload icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="16 12 12 8 8 12" />
          <line x1="12" y1="8" x2="12" y2="16" />
        </svg>

        <p
          style={{
            fontSize: "0.8125rem",
            color: "var(--text-muted)",
            textAlign: "center",
            margin: 0,
          }}
        >
          Drag and drop or choose a file
        </p>

        <input
          name="file"
          type="file"
          accept="application/pdf,.txt"
          className="input"
          style={{ maxWidth: "100%" }}
        />
      </div>

      <button
        className="btn btn-accent btn-lg"
        type="submit"
        style={{ width: "100%", marginTop: "16px" }}
      >
        {uploadButtonLabel(state)}
      </button>

      <p
        style={{
          marginTop: "1rem",
          fontSize: "0.875rem",
          color: messageColor,
          transition: "color 0.2s ease",
        }}
      >
        {message}
      </p>
    </form>
  );
}
