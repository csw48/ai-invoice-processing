"use client";

import { useState } from "react";

type UploadState = "idle" | "uploading" | "done" | "error";

export function uploadButtonLabel(state: UploadState): string {
  if (state === "uploading") return "Processing...";
  if (state === "done") return "Processed";
  if (state === "error") return "Try again";
  return "Upload invoice";
}

export function UploadPanel() {
  const [state, setState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("PDF upload endpoint is ready for local API testing.");

  async function onSubmit(formData: FormData) {
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setState("error");
      setMessage("Choose a PDF invoice first.");
      return;
    }

    setState("uploading");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/invoices/upload`, { method: "POST", body: formData });
    if (!response.ok) {
      setState("error");
      setMessage("Upload failed. Check the API server and environment variables.");
      return;
    }
    setState("done");
    setMessage("Invoice processed. Review screen is the next feature slice.");
  }

  return (
    <form action={onSubmit} className="rounded-2xl bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold">Quick upload</h2>
      <p className="mt-2 text-sm text-slate-600">Upload a text-based PDF invoice for the MVP pipeline.</p>
      <input name="file" type="file" accept="application/pdf,.txt" className="mt-6 block w-full rounded-xl border border-slate-200 p-3" />
      <button className="mt-4 rounded-xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-400" type="submit">
        {uploadButtonLabel(state)}
      </button>
      <p className="mt-4 text-sm text-slate-600">{message}</p>
    </form>
  );
}
