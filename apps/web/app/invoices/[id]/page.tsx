import { notFound } from "next/navigation";

type Confidence = { value: unknown; confidence: number };

type Invoice = {
  invoice_id: string;
  status: string;
  country_code?: string | null;
  validation: { valid: boolean; issues: { field: string; severity: string; message: string }[] };
  extracted: Record<string, Confidence | unknown>;
  formatted: { type: string };
};

const FIELD_ORDER: { key: string; label: string }[] = [
  { key: "vendor_name", label: "Vendor" },
  { key: "vendor_vat", label: "Vendor VAT" },
  { key: "vendor_iban", label: "Vendor IBAN" },
  { key: "invoice_number", label: "Invoice number" },
  { key: "invoice_date", label: "Invoice date" },
  { key: "due_date", label: "Due date" },
  { key: "subtotal", label: "Subtotal" },
  { key: "vat_amount", label: "VAT amount" },
  { key: "total_amount", label: "Total" },
  { key: "currency", label: "Currency" },
];

async function fetchInvoice(id: string): Promise<Invoice | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/invoices/${id}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Failed to load invoice: ${response.status}`);
  return response.json();
}

function confidenceColor(conf: number): string {
  if (conf >= 0.8) return "text-emerald-600";
  if (conf >= 0.5) return "text-amber-600";
  return "text-rose-600";
}

export default async function InvoiceReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const invoice = await fetchInvoice(id);
  if (!invoice) notFound();

  const validation = invoice.validation;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <p className="text-sm text-slate-500">Invoice {invoice.invoice_id}</p>
      <h1 className="mt-1 text-3xl font-bold">Review extracted fields</h1>
      <p className="mt-2 text-slate-600">
        Status: <span className="font-medium">{invoice.status}</span>
        {invoice.country_code ? (
          <span className="ml-3 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium uppercase tracking-wide text-slate-700">
            {invoice.country_code}
          </span>
        ) : null}
      </p>

      <section className="mt-6 rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Validation</h2>
        {validation.valid ? (
          <p className="mt-2 text-emerald-600">All required fields look good.</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {validation.issues.map((issue, idx) => (
              <li key={`${issue.field}-${idx}`} className={issue.severity === "error" ? "text-rose-600" : "text-amber-600"}>
                <strong>{issue.field}</strong>: {issue.message} ({issue.severity})
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6 rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Extracted fields</h2>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="py-2 font-medium">Field</th>
              <th className="py-2 font-medium">Value</th>
              <th className="py-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {FIELD_ORDER.map(({ key, label }) => {
              const item = invoice.extracted[key] as Confidence | undefined;
              const value = item?.value ?? "";
              const conf = item?.confidence ?? 0;
              return (
                <tr key={key} className="border-t border-slate-100">
                  <td className="py-2 font-medium">{label}</td>
                  <td className="py-2">{value === null || value === "" ? "—" : String(value)}</td>
                  <td className={`py-2 ${confidenceColor(conf)}`}>{(conf * 100).toFixed(0)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </main>
  );
}
