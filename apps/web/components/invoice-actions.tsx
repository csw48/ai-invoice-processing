"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuthHeaders } from "../lib/api-auth";

type ExportResult = {
  invoice_id: string;
  status: string;
  webhook_delivered?: boolean;
  export: {
    type: "json" | "csv" | "pohoda" | "webhook";
    payload: string | object;
  };
};

type Props = {
  invoiceId: string;
  validationValid: boolean;
  currentStatus: string;
  apiUrl: string;
  compact?: boolean;
  duplicate?: boolean;
};

function downloadExport(payload: string | object, type: string, invoiceId: string) {
  const ext = type === "csv" ? "csv" : type === "pohoda" ? "xml" : "json";
  const mime = type === "csv" ? "text/csv" : type === "pohoda" ? "application/xml" : "application/json";
  const content = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `invoice-${invoiceId.slice(0, 8)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function InvoiceActions({
  invoiceId,
  validationValid,
  currentStatus,
  apiUrl,
  compact = false,
  duplicate = false,
}: Props) {
  const router = useRouter();
  const authHeaders = useAuthHeaders();
  const [loading, setLoading] = useState<"approve" | "export" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);

  const isApproved =
    currentStatus === "approved" || currentStatus === "exported";

  async function handleApprove() {
    setLoading("approve");
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${invoiceId}/approve`, {
        method: "PUT",
        headers: await authHeaders(),
      });
      if (res.status === 422) {
        setError("Cannot approve — fix validation errors first.");
        return;
      }
      if (!res.ok) {
        setError(`Approval failed (${res.status}). Please try again.`);
        return;
      }
      router.refresh();
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(null);
    }
  }

  async function handleExport() {
    setLoading("export");
    setError(null);
    setExportResult(null);
    try {
      const res = await fetch(`${apiUrl}/api/export/${invoiceId}`, {
        method: "POST",
        headers: await authHeaders(),
      });
      if (res.status === 422) {
        setError("Cannot export — fix validation errors first.");
        return;
      }
      if (res.status === 502) {
        setError("Webhook delivery failed after retries — invoice not exported.");
        return;
      }
      if (!res.ok) {
        setError(`Export failed (${res.status}). Please try again.`);
        return;
      }
      const data: ExportResult = await res.json();
      setExportResult(data);
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setLoading(null);
    }
  }

  const isInFlight = loading !== null;

  if (compact) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end" }}>
        {duplicate && !isApproved && (
          <span style={{ fontSize: "11px", color: "var(--warning)", fontWeight: 600 }}>
            Possible duplicate
          </span>
        )}
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {!isApproved && (
            <button onClick={handleApprove} disabled={isInFlight} className="btn btn-success" style={{ padding: "6px 14px", fontSize: "13px" }}>
              {loading === "approve" ? "…" : "Approve"}
            </button>
          )}
          <button onClick={handleExport} disabled={isInFlight} className="btn btn-ghost" style={{ padding: "6px 14px", fontSize: "13px" }}>
            {loading === "export" ? "…" : "Export"}
          </button>
          {error && <span style={{ color: "var(--error)", fontSize: "12px" }}>{error}</span>}
        </div>
      </div>
    );
  }

  return (
    <section className="card" style={{ marginTop: "24px" }}>
      <h2 className="card-title">Actions</h2>

      <div style={{ marginTop: "16px", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
        {isApproved ? (
          <span className="badge badge-approved">Approved</span>
        ) : (
          <button
            onClick={handleApprove}
            disabled={isInFlight}
            className="btn btn-success"
          >
            {loading === "approve" ? "..." : "Approve"}
          </button>
        )}

        <button
          onClick={handleExport}
          disabled={isInFlight}
          className="btn btn-ghost"
        >
          {loading === "export" ? "..." : "Export"}
        </button>
      </div>

      {duplicate && !isApproved && (
        <p style={{ marginTop: "12px", color: "var(--warning)", fontSize: "13px", fontWeight: 600 }}>
          Possible duplicate — another invoice with the same number and vendor may already exist.
        </p>
      )}
      {error && (
        <p style={{ marginTop: "12px", color: "var(--error)", fontSize: "13px" }}>{error}</p>
      )}

      {exportResult && (
        <div style={{ marginTop: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px", flexWrap: "wrap" }}>
            <span style={{ fontSize: "13px" }}>Export result</span>
            <span className="badge badge-exported">{exportResult.export.type}</span>
            {exportResult.webhook_delivered !== undefined && (
              <span className="badge" style={{ color: exportResult.webhook_delivered ? "var(--success)" : "var(--error)" }}>
                {exportResult.webhook_delivered ? "delivered" : "not delivered"}
              </span>
            )}
            {exportResult.export.type !== "webhook" && exportResult.export.payload !== undefined && (
              <button
                className="btn btn-accent btn-sm"
                onClick={() => downloadExport(exportResult.export.payload!, exportResult.export.type, exportResult.invoice_id)}
              >
                Download .{exportResult.export.type === "pohoda" ? "xml" : exportResult.export.type === "csv" ? "csv" : "json"}
              </button>
            )}
          </div>
          {exportResult.export.type !== "pohoda" && exportResult.export.type !== "csv" && (
            <pre className="code-block">
              {JSON.stringify(exportResult.export.payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}
