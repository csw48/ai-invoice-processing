"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type UploadState = "idle" | "uploading" | "done" | "error";

export function uploadButtonLabel(state: UploadState): string {
  if (state === "uploading") return "Processing...";
  if (state === "done") return "Processed";
  if (state === "error") return "Try again";
  return "Upload invoice";
}

export function UploadPanel() {
  const router = useRouter();
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("Upload a PDF invoice to extract fields and review them.");

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
      const response = await fetch(`${apiUrl}/api/invoices/upload`, { method: "POST", body: formData });
      if (!response.ok) {
        setState("error");
        setMessage(`Upload failed (${response.status}). Check the API server and env vars.`);
        return;
      }
      const body = (await response.json()) as { invoice_id?: string };
      setState("done");
      setMessage("Invoice processed. Opening review screen...");
      if (body.invoice_id) {
        router.push(`/invoices/${body.invoice_id}`);
      }
    } catch (err) {
      setState("error");
      setMessage(`Upload error: ${(err as Error).message}`);
    }
  }

  return (
    <form action={onSubmit} className="rounded-2xl bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold">Quick upload</h2>
      <p className="mt-2 text-sm text-slate-600">Upload a text-based PDF invoice.</p>
      <input name="file" type="file" accept="application/pdf,.txt" className="mt-6 block w-full rounded-xl border border-slate-200 p-3" />
      <button className="mt-4 rounded-xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-400" type="submit">
        {uploadButtonLabel(state)}
      </button>
      <p className="mt-4 text-sm text-slate-600">{message}</p>
    </form>
  );
}
