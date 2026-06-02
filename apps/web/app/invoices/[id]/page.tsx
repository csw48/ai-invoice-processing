import Link from "next/link";
import { notFound } from "next/navigation";
import InvoiceActions from "../../../components/invoice-actions";
import InvoiceReviewClient from "../../../components/invoice-review-client";
import { serverAuthHeaders } from "../../../lib/server-auth";

type Confidence = { value: unknown; confidence: number };

type Invoice = {
  invoice_id: string;
  status: string;
  country_code?: string | null;
  file_path?: string | null;
  raw_text?: string | null;
  word_positions?: Array<{ page: number; text: string; x0: number; y0: number; x1: number; y1: number }> | null;
  validation: { valid: boolean; issues: { field: string; severity: string; message: string }[] };
  extracted: Record<string, Confidence | unknown>;
  enriched: { vendor_metadata: Record<string, unknown>; duplicate: boolean; category: string | null };
  formatted: { type: string; payload?: Record<string, unknown> };
};

async function fetchInvoice(id: string): Promise<Invoice | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/invoices/${id}`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Failed to load invoice: ${response.status}`);
  return response.json();
}

export default async function InvoiceReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const invoice = await fetchInvoice(id);
  if (!invoice) notFound();

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const hasFile = !!invoice.file_path && !invoice.file_path.startsWith("memory://");
  const fileUrl = hasFile ? `${apiUrl}/api/invoices/${invoice.invoice_id}/file` : null;

  const vendorName = (invoice.extracted as Record<string, Confidence>).vendor_name?.value;

  return (
    <div className="review-page">
      {/* Top bar */}
      <div className="review-topbar">
        <Link href="/invoices" style={{ color: "var(--muted)", fontSize: "13px", textDecoration: "none" }}>
          ← Invoices
        </Link>
        <span style={{ color: "var(--border)" }}>|</span>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text)" }}>
          {vendorName ? String(vendorName) : `Invoice ${invoice.invoice_id.slice(0, 8)}…`}
        </span>
        <span className={`badge badge-${invoice.status}`}>{invoice.status}</span>
        {invoice.country_code && <span className="mono" style={{ fontSize: "12px" }}>{invoice.country_code}</span>}
        <div style={{ marginLeft: "auto" }}>
          <InvoiceActions
            invoiceId={invoice.invoice_id}
            validationValid={invoice.validation.valid}
            currentStatus={invoice.status}
            apiUrl={apiUrl}
            compact
            duplicate={invoice.enriched.duplicate}
          />
        </div>
      </div>

      {/* Split review panel (client component handles interaction) */}
      <InvoiceReviewClient invoice={invoice} fileUrl={fileUrl} apiUrl={apiUrl} />
    </div>
  );
}
