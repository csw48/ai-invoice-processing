import Link from "next/link";
import { serverAuthHeaders } from "../../lib/server-auth";

type Confidence = { value: unknown; confidence: number };

type Invoice = {
  invoice_id: string;
  status: string;
  country_code?: string | null;
  validation: { valid: boolean; issues?: { field: string; severity: string; message: string }[] };
  extracted: Record<string, Confidence | unknown>;
  enriched?: { duplicate?: boolean };
};

function currencySymbol(code: string): string {
  const symbols: Record<string, string> = { EUR: "€", CZK: "Kč", USD: "$", GBP: "£", HUF: "Ft", PLN: "zł" };
  return symbols[code] ?? code;
}

function statusBadge(status: string): string {
  switch (status) {
    case "review":     return "badge badge-review";
    case "approved":   return "badge badge-approved";
    case "exported":   return "badge badge-exported";
    case "processing": return "badge badge-processing";
    case "error":      return "badge badge-error";
    case "redirect":   return "badge badge-redirect";
    case "discarded":  return "badge badge-discarded";
    default:           return "badge badge-processing";
  }
}

type InvoiceFilters = {
  status?: string;
  needs_review?: string;
  q?: string;
  page?: string;
};

type PagedInvoices = {
  items: Invoice[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
};

const EMPTY_PAGE: PagedInvoices = { items: [], total: 0, page: 1, per_page: 50, pages: 1 };

async function fetchInvoices(filters: InvoiceFilters): Promise<PagedInvoices> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.needs_review === "true") params.set("needs_review", "true");
  if (filters.q) params.set("q", filters.q);
  if (filters.page && Number(filters.page) > 1) params.set("page", filters.page);
  const query = params.toString();
  const res = await fetch(`${apiUrl}/api/invoices/${query ? `?${query}` : ""}`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  if (!res.ok) return EMPTY_PAGE;
  return res.json();
}

function field(invoice: Invoice, key: string): string {
  const item = invoice.extracted[key] as Confidence | undefined;
  const v = item?.value;
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

function attention(invoice: Invoice): string {
  const errors = invoice.validation.issues?.filter((issue) => issue.severity === "error").length ?? 0;
  const warnings = invoice.validation.issues?.filter((issue) => issue.severity === "warning").length ?? 0;
  if (errors > 0) return `${errors} error${errors === 1 ? "" : "s"}`;
  if (invoice.enriched?.duplicate) return "duplicate";
  if (warnings > 0) return `${warnings} warning${warnings === 1 ? "" : "s"}`;
  return "clear";
}

function filterHref(filters: InvoiceFilters) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.needs_review === "true") params.set("needs_review", "true");
  if (filters.q) params.set("q", filters.q);
  if (filters.page && Number(filters.page) > 1) params.set("page", filters.page);
  const query = params.toString();
  return `/invoices${query ? `?${query}` : ""}`;
}

function pageHref(filters: InvoiceFilters, page: number) {
  return filterHref({ ...filters, page: String(page) });
}

function chipClass(active: boolean) {
  return active ? "btn btn-accent btn-sm" : "btn btn-ghost btn-sm";
}

export default async function InvoiceListPage({
  searchParams,
}: {
  searchParams: Promise<InvoiceFilters>;
}) {
  const filters = await searchParams;
  const paged = await fetchInvoices(filters);
  const invoices = paged.items;
  const activeFilter = filters.needs_review === "true" ? "needs_review" : filters.status ?? "all";

  return (
    <main className="page">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <Link href="/" className="page-back">← Dashboard</Link>
          <h1 className="page-title">Invoices</h1>
        </div>
        <Link href="/" className="btn btn-accent">Upload invoice</Link>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          margin: "22px 0",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <Link href={filterHref({ q: filters.q })} className={chipClass(activeFilter === "all")}>All</Link>
          <Link href={filterHref({ needs_review: "true", q: filters.q })} className={chipClass(activeFilter === "needs_review")}>Needs review</Link>
          <Link href={filterHref({ status: "review", q: filters.q })} className={chipClass(activeFilter === "review")}>Review</Link>
          <Link href={filterHref({ status: "approved", q: filters.q })} className={chipClass(activeFilter === "approved")}>Approved</Link>
          <Link href={filterHref({ status: "exported", q: filters.q })} className={chipClass(activeFilter === "exported")}>Exported</Link>
          <Link href={filterHref({ status: "redirect", q: filters.q })} className={chipClass(activeFilter === "redirect")}>Redirected</Link>
          <Link href={filterHref({ status: "discarded", q: filters.q })} className={chipClass(activeFilter === "discarded")}>Discarded</Link>
        </div>

        <form action="/invoices" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {filters.status && <input type="hidden" name="status" value={filters.status} />}
          {filters.needs_review === "true" && <input type="hidden" name="needs_review" value="true" />}
          <input
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="Search vendor or invoice #"
            className="input"
            style={{ height: "34px", minWidth: "210px" }}
          />
          <button className="btn btn-ghost btn-sm" type="submit">Search</button>
          {filters.q && <Link href={filterHref({ status: filters.status, needs_review: filters.needs_review })} className="btn btn-ghost btn-sm">Clear</Link>}
        </form>
      </div>

      {invoices.length === 0 ? (
        <div className="empty-state">
          No invoices match this queue. <Link href="/">Upload one to get started.</Link>
        </div>
      ) : (
        <div className="table-wrap fade-up">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Invoice #</th>
                <th>Date</th>
                <th>Total</th>
                <th>Country</th>
                <th>Status</th>
                <th>Attention</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.invoice_id}>
                  <td className="td-primary">{field(inv, "vendor_name")}</td>
                  <td className="td-mono">{field(inv, "invoice_number")}</td>
                  <td>{field(inv, "invoice_date")}</td>
                  <td className="td-mono">
                    {field(inv, "currency") && (
                      <span style={{ color: "var(--muted)", fontSize: "11px", marginRight: "2px" }}>
                        {currencySymbol(field(inv, "currency"))}
                      </span>
                    )}
                    {field(inv, "total_amount")}
                  </td>
                  <td>
                    {inv.country_code ? (
                      <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                        {inv.country_code}
                      </span>
                    ) : "—"}
                  </td>
                  <td>
                    <span className={statusBadge(inv.status)}>{inv.status}</span>
                  </td>
                  <td>
                    {attention(inv) === "clear" ? (
                      <span style={{ color: "var(--success)", fontWeight: 600 }}>clear</span>
                    ) : (
                      <span style={{ color: inv.validation.valid ? "var(--warning)" : "var(--error)", fontWeight: 600 }}>
                        {attention(inv)}
                      </span>
                    )}
                  </td>
                  <td className="td-action">
                    <Link href={`/invoices/${inv.invoice_id}`} className="btn btn-ghost btn-sm">
                      Review
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {paged.pages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", marginTop: "20px" }}>
          {paged.page > 1 && (
            <Link href={pageHref(filters, paged.page - 1)} className="btn btn-ghost btn-sm">← Prev</Link>
          )}
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Page {paged.page} of {paged.pages} &nbsp;·&nbsp; {paged.total} invoices
          </span>
          {paged.page < paged.pages && (
            <Link href={pageHref(filters, paged.page + 1)} className="btn btn-ghost btn-sm">Next →</Link>
          )}
        </div>
      )}
    </main>
  );
}
