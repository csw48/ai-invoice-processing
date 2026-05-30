import Link from "next/link";
import { UploadPanel } from "../components/upload-panel";
import { StatCards } from "../components/stat-cards";

type Stats = { total: number; by_status: Record<string, number>; valid: number; invalid: number };

async function fetchStats(): Promise<Stats> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${apiUrl}/api/stats`, { cache: "no-store" });
    if (res.ok) return res.json();
  } catch {}
  return { total: 0, by_status: {}, valid: 0, invalid: 0 };
}

export default async function Dashboard() {
  const stats = await fetchStats();

  return (
    <main className="page">
      {/* Hero */}
      <section className="fade-up">
        <p
          className="page-sub"
          style={{
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--accent)",
            marginBottom: "8px",
          }}
        >
          Slovak SMB invoice automation
        </p>
        <h1 className="page-title">
          Upload invoices, verify AI extraction, export to Pohoda.
        </h1>
        <p className="page-sub">
          A focused MVP for accountants processing 50–500 invoices/month.
          Supabase stores invoices and vendor knowledge; FastAPI runs the
          extraction pipeline.
        </p>
      </section>

      {/* Animated stat cards */}
      <StatCards
        total={stats.total}
        review={stats.by_status["review"] ?? 0}
        approved={stats.by_status["approved"] ?? 0}
      />

      {/* 2-col action area */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1.2fr",
          gap: "1.5rem",
          marginTop: "2rem",
        }}
      >
        <UploadPanel />

        <div className="card">
          <h2 className="card-title">Review workflow</h2>
          <ol
            style={{
              marginTop: "1rem",
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            <li>1. Extract fields from PDF text with confidence scores.</li>
            <li>
              2. Validate required fields, Slovak VAT format, currency, and VAT
              math.
            </li>
            <li>3. Enrich from vendor knowledge base in Supabase pgvector.</li>
            <li>
              4. Export JSON/CSV now; Pohoda XML connector scaffold included.
            </li>
          </ol>
          <Link
            href="/invoices"
            className="btn btn-ghost"
            style={{ marginTop: "1.5rem", display: "inline-block" }}
          >
            View all invoices →
          </Link>
        </div>
      </section>
    </main>
  );
}
