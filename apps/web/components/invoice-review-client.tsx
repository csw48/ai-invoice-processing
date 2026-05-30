"use client";

import { useState } from "react";
import InvoiceActions from "./invoice-actions";
import InvoicePdfPanel from "./invoice-pdf-panel";
import { useAuthHeaders } from "../lib/api-auth";

type Confidence = { value: unknown; confidence: number };
type Issue = { field: string; severity: string; message: string };

type LineItem = { description: string; qty: number; unit_price: number; vat_rate: number; total: number };

type Party = { company_name: string | null; address: string | null; vat_id: string | null };
type Classification = {
  document_type: string;
  type_reasoning: string;
  sender: Party;
  recipient: Party;
};

type Invoice = {
  invoice_id: string;
  status: string;
  classification?: Classification | null;
  country_code?: string | null;
  file_path?: string | null;
  raw_text?: string | null;
  word_positions?: Array<{ page: number; text: string; x0: number; y0: number; x1: number; y1: number }> | null;
  validation: { valid: boolean; issues: Issue[] };
  extracted: Record<string, Confidence | unknown> & { line_items?: LineItem[] };
  enriched: { vendor_metadata: Record<string, unknown>; duplicate: boolean; category: string | null };
  formatted: { type: string };
};

const FIELD_COLORS: Record<string, string> = {
  vendor_name: "#818cf8", vendor_vat: "#a78bfa", vendor_iban: "#60a5fa",
  invoice_number: "#34d399", invoice_date: "#f59e0b", due_date: "#fb923c",
  subtotal: "#10b981", vat_amount: "#6ee7b7", total_amount: "#ef4444", currency: "#94a3b8",
};

const FIELD_ORDER: { key: string; label: string }[] = [
  { key: "vendor_name", label: "Vendor" },
  { key: "vendor_ico", label: "IČO" },
  { key: "vendor_vat", label: "IČ DPH" },
  { key: "vendor_iban", label: "IBAN" },
  { key: "invoice_number", label: "Invoice number" },
  { key: "invoice_date", label: "Invoice date" },
  { key: "due_date", label: "Due date" },
  { key: "subtotal", label: "Subtotal" },
  { key: "vat_amount", label: "VAT amount" },
  { key: "total_amount", label: "Total" },
  { key: "currency", label: "Currency" },
  { key: "po_number", label: "PO number" },
  { key: "cost_center", label: "Cost center" },
];

function ConfBadge({ conf }: { conf: number }) {
  const pct = Math.round(conf * 100);
  const color = conf >= 0.85 ? "var(--success)" : conf >= 0.6 ? "#f59e0b" : "var(--error)";
  return (
    <span style={{ fontSize: "11px", fontWeight: 600, color, background: `${color}18`, border: `1px solid ${color}40`, borderRadius: "4px", padding: "1px 6px", whiteSpace: "nowrap" }}>
      {pct}%
    </span>
  );
}

export default function InvoiceReviewClient({
  invoice,
  fileUrl,
  apiUrl,
}: {
  invoice: Invoice;
  fileUrl: string | null;
  apiUrl: string;
}) {
  const authHeaders = useAuthHeaders();
  const [activeTab, setActiveTab] = useState<"pdf" | "text">(fileUrl ? "pdf" : "text");
  const [activeHighlight, setActiveHighlight] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editValues, setEditValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      FIELD_ORDER.map(({ key }) => {
        const item = (invoice.extracted as Record<string, Confidence>)[key];
        const val = item?.value;
        return [key, val === null || val === undefined ? "" : String(val)];
      })
    )
  );

  const validation = invoice.validation;
  const classification = invoice.classification ?? null;
  const isNonInvoice =
    !!classification &&
    classification.document_type !== "invoice" &&
    classification.document_type !== "credit_note";
  const errorFields = new Set(validation.issues.filter((i) => i.severity === "error").map((i) => i.field));
  const warnFields = new Set(validation.issues.filter((i) => i.severity === "warning").map((i) => i.field));

  type FieldHighlight = { field: string; value: string; color: string; active: boolean };
  const fieldHighlights: FieldHighlight[] = FIELD_ORDER
    .map(({ key }) => {
      const item = (invoice.extracted as Record<string, Confidence>)[key];
      const val = item?.value;
      if (val === null || val === undefined || val === "") return null;
      return { field: key, value: String(val), color: FIELD_COLORS[key] ?? "#94a3b8", active: activeHighlight === String(val) };
    })
    .filter((v): v is FieldHighlight => v !== null);

  function handleFieldClick(key: string) {
    const item = (invoice.extracted as Record<string, Confidence>)[key];
    const val = item?.value;
    if (val !== null && val !== undefined && val !== "") {
      setActiveHighlight(String(val));
      setActiveTab(fileUrl ? "pdf" : "text");
    }
  }

  async function handleSaveFields() {
    const changed: Record<string, string | null> = {};
    for (const { key } of FIELD_ORDER) {
      const item = (invoice.extracted as Record<string, Confidence>)[key];
      const previous = item?.value === null || item?.value === undefined ? "" : String(item.value);
      const next = editValues[key] ?? "";
      if (next !== previous) changed[key] = next === "" ? null : next;
    }

    if (Object.keys(changed).length === 0) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(`${apiUrl}/api/invoices/${invoice.invoice_id}/fields`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...(await authHeaders()) },
        body: JSON.stringify(changed),
      });
      if (res.ok) {
        window.location.reload();
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
      {/* Left: PDF + raw text panel */}
      <div style={{ flex: "0 0 55%", borderRight: "1px solid var(--border)", background: "#f0f0f0", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <InvoicePdfPanel
          fileUrl={fileUrl}
          rawText={invoice.raw_text ?? null}
          fieldHighlights={fieldHighlights}
          activeHighlight={activeHighlight}
          externalTab={activeTab}
          onTabChange={setActiveTab}
        />
      </div>

      {/* Right: Fields panel */}
      <div style={{ flex: 1, overflow: "auto", padding: "20px", background: "var(--bg)" }}>
        {/* Classification banner */}
        {isNonInvoice ? (
          <div style={{ marginBottom: "16px", padding: "10px 14px", background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "13px" }}>
            <strong style={{ textTransform: "uppercase" }}>{classification!.document_type}</strong> — not an invoice, extraction skipped.
            {classification!.type_reasoning && (
              <div style={{ marginTop: "4px", color: "var(--muted)" }}>{classification!.type_reasoning}</div>
            )}
          </div>
        ) : !validation.valid ? (
          <div style={{ marginBottom: "16px", padding: "10px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", fontSize: "13px" }}>
            <strong style={{ color: "var(--error)" }}>
              {validation.issues.filter((i) => i.severity === "error").length} error
              {validation.issues.filter((i) => i.severity === "error").length !== 1 ? "s" : ""}
            </strong>{" "}— review highlighted fields
          </div>
        ) : (
          <div style={{ marginBottom: "16px", padding: "10px 14px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "8px", fontSize: "13px", color: "var(--success)", fontWeight: 600 }}>
            All required fields extracted successfully
          </div>
        )}

        {/* Classification */}
        {classification && (classification.sender.company_name || classification.recipient.company_name) && (
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "12px" }}>
              Classification
              <span style={{ marginLeft: "8px", fontWeight: 400, textTransform: "none", letterSpacing: 0, color: "var(--muted)", fontSize: "10px" }}>
                {classification.document_type}
              </span>
            </h3>
            <div style={{ display: "flex", gap: "8px" }}>
              {(["sender", "recipient"] as const).map((role) => {
                const party = classification[role];
                return (
                  <div key={role} style={{ flex: 1, padding: "10px 12px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "13px" }}>
                    <div style={{ color: "var(--muted)", fontWeight: 500, textTransform: "capitalize", marginBottom: "4px" }}>{role}</div>
                    <div style={{ fontWeight: 600, color: "var(--text)" }}>{party.company_name ?? "—"}</div>
                    {party.address && <div style={{ color: "var(--muted)", marginTop: "2px" }}>{party.address}</div>}
                    {party.vat_id && <div className="mono" style={{ color: "var(--muted)", marginTop: "2px", fontSize: "12px" }}>{party.vat_id}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Entities */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "12px" }}>
            Entities
            <span style={{ marginLeft: "8px", fontWeight: 400, textTransform: "none", letterSpacing: 0, color: "var(--muted)", fontSize: "10px" }}>
              click a field to locate in document
            </span>
          </h3>
          <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
            {!editing ? (
              <button className="btn btn-ghost" style={{ fontSize: "12px", padding: "5px 12px" }} onClick={() => setEditing(true)}>
                Edit fields
              </button>
            ) : (
              <>
                <button className="btn btn-primary" style={{ fontSize: "12px", padding: "5px 12px" }} onClick={handleSaveFields} disabled={saving}>
                  {saving ? "Saving..." : "Save changes"}
                </button>
                <button className="btn btn-ghost" style={{ fontSize: "12px", padding: "5px 12px" }} onClick={() => setEditing(false)} disabled={saving}>
                  Cancel
                </button>
              </>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {FIELD_ORDER.map(({ key, label }) => {
              const item = (invoice.extracted as Record<string, Confidence>)[key];
              const val = item?.value;
              const conf = item?.confidence ?? 0;
              const hasError = errorFields.has(key);
              const hasWarn = warnFields.has(key);
              const hasValue = val !== null && val !== undefined && val !== "";
              const isActive = activeHighlight === String(val) && hasValue;

              if (!hasValue && !hasError && !hasWarn) return null;

              const borderColor = isActive
                ? "var(--accent)"
                : hasError
                ? "var(--error)"
                : hasWarn
                ? "#f59e0b"
                : "var(--border)";

              return (
                <div
                  key={key}
                  onClick={() => handleFieldClick(key)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    background: isActive ? "#eff6ff" : "var(--surface)",
                    border: `1px solid ${borderColor}`,
                    borderRadius: "8px",
                    fontSize: "13px",
                    cursor: hasValue ? "pointer" : "default",
                    transition: "background 0.15s, border-color 0.15s",
                  }}
                >
                  <div style={{ flex: "0 0 120px", color: "var(--muted)", fontWeight: 500 }}>{label}</div>
                  <div style={{ flex: 1, fontWeight: 500, color: hasValue ? "var(--text)" : "var(--muted)" }}>
                    {editing ? (
                      <input
                        value={editValues[key] ?? ""}
                        onClick={(event) => event.stopPropagation()}
                        onChange={(event) => setEditValues((prev) => ({ ...prev, [key]: event.target.value }))}
                        style={{
                          width: "100%",
                          border: "1px solid var(--border)",
                          borderRadius: "6px",
                          padding: "6px 8px",
                          background: "var(--bg)",
                          color: "var(--text)",
                          fontSize: "13px",
                        }}
                      />
                    ) : hasValue ? String(val) : <span style={{ color: "var(--error)", fontStyle: "italic" }}>missing</span>}
                  </div>
                  {conf > 0 && <ConfBadge conf={conf} />}
                  {hasError && <span style={{ fontSize: "11px", color: "var(--error)" }}>required</span>}
                </div>
              );
            })}
          </div>
        </div>

        {/* Line Items */}
        {(invoice.extracted.line_items ?? []).length > 0 && (
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "12px" }}>
              Line Items
            </h3>
            <div style={{ border: "1px solid var(--border)", borderRadius: "8px", overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                <thead>
                  <tr style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ textAlign: "left", padding: "8px 10px", color: "var(--muted)", fontWeight: 600 }}>Description</th>
                    <th style={{ textAlign: "right", padding: "8px 10px", color: "var(--muted)", fontWeight: 600, whiteSpace: "nowrap" }}>Qty</th>
                    <th style={{ textAlign: "right", padding: "8px 10px", color: "var(--muted)", fontWeight: 600, whiteSpace: "nowrap" }}>Unit price</th>
                    <th style={{ textAlign: "right", padding: "8px 10px", color: "var(--muted)", fontWeight: 600, whiteSpace: "nowrap" }}>VAT %</th>
                    <th style={{ textAlign: "right", padding: "8px 10px", color: "var(--muted)", fontWeight: 600 }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(invoice.extracted.line_items ?? []).map((item, i) => (
                    <tr key={i} style={{ borderBottom: i < (invoice.extracted.line_items?.length ?? 0) - 1 ? "1px solid var(--border)" : "none", background: i % 2 === 0 ? "var(--bg)" : "var(--surface)" }}>
                      <td style={{ padding: "8px 10px", color: "var(--text)" }}>{item.description || "—"}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", color: "var(--text)" }}>{item.qty}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", color: "var(--text)" }}>{item.unit_price?.toFixed(2)}</td>
                      <td style={{ padding: "8px 10px", textAlign: "right", color: "var(--text)" }}>
                        {item.vat_rate ? `${Math.round(item.vat_rate <= 1 ? item.vat_rate * 100 : item.vat_rate)}%` : "—"}
                      </td>
                      <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 600, color: "var(--text)" }}>{item.total?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Enrichment */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "12px" }}>Enrichment</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ padding: "10px 12px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "13px", display: "flex", gap: "10px", alignItems: "center" }}>
              <span style={{ flex: "0 0 120px", color: "var(--muted)", fontWeight: 500 }}>Duplicate</span>
              <span style={{ color: invoice.enriched.duplicate ? "var(--error)" : "var(--success)", fontWeight: 600 }}>
                {invoice.enriched.duplicate ? "Yes — possible duplicate" : "No"}
              </span>
            </div>
            {invoice.enriched.category && (
              <div style={{ padding: "10px 12px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "13px", display: "flex", gap: "10px", alignItems: "center" }}>
                <span style={{ flex: "0 0 120px", color: "var(--muted)", fontWeight: 500 }}>Category</span>
                <span>{invoice.enriched.category}</span>
              </div>
            )}
          </div>
        </div>

        {/* Output */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "12px" }}>Output</h3>
          <div style={{ padding: "10px 12px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "13px" }}>
            <span style={{ color: "var(--muted)", fontWeight: 500 }}>Connector: </span>
            <span className="mono">{invoice.formatted.type}</span>
          </div>
        </div>

        {/* Reprocess */}
        <ReprocessButton invoiceId={invoice.invoice_id} apiUrl={apiUrl} />
      </div>
    </div>
  );
}

function ReprocessButton({ invoiceId, apiUrl }: { invoiceId: string; apiUrl: string }) {
  const authHeaders = useAuthHeaders();
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"ai" | "ocr" | null>(null);
  const [done, setDone] = useState(false);

  async function handleReprocess(forceOcr = false) {
    setLoading(true);
    setMode(forceOcr ? "ocr" : "ai");
    try {
      const url = `${apiUrl}/api/invoices/${invoiceId}/reprocess${forceOcr ? "?force_ocr=true" : ""}`;
      const res = await fetch(url, { method: "POST", headers: await authHeaders() });
      if (res.ok) {
        setDone(true);
        setTimeout(() => window.location.reload(), 800);
      }
    } finally {
      setLoading(false);
      setMode(null);
    }
  }

  return (
    <div>
      <button
        onClick={() => handleReprocess(false)}
        disabled={loading}
        className="btn btn-ghost"
        style={{ fontSize: "12px", padding: "5px 12px", opacity: done ? 0.5 : 1 }}
      >
        {loading && mode === "ai" ? "Re-processing…" : done ? "Done — reloading…" : "Re-process with AI"}
      </button>
      <button
        onClick={() => handleReprocess(true)}
        disabled={loading}
        className="btn btn-ghost"
        style={{ marginLeft: "8px", fontSize: "12px", padding: "5px 12px", opacity: done ? 0.5 : 1 }}
      >
        {loading && mode === "ocr" ? "OCR processing…" : "Re-process with OCR"}
      </button>
      <span style={{ marginLeft: "8px", fontSize: "11px", color: "var(--muted)" }}>
        OCR forces image text recognition before AI extraction
      </span>
    </div>
  );
}
