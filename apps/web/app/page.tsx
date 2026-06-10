import Link from "next/link";
import { UploadPanel } from "../components/upload-panel";
import { StatCards } from "../components/stat-cards";

type Stats = {
  total: number;
  by_status: Record<string, number>;
  valid: number;
  invalid: number;
  hours_saved: number;
  extraction_accuracy: number | null;
};

async function fetchStats(): Promise<Stats> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${apiUrl}/api/stats`, { cache: "no-store" });
    if (res.ok) return res.json();
  } catch {}
  return { total: 0, by_status: {}, valid: 0, invalid: 0, hours_saved: 0, extraction_accuracy: null };
}

export default async function Dashboard() {
  const stats = await fetchStats();

  return (
    <main className="page">
      {/* Hero */}
      <section className="fade-up">
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
        needsReview={(stats.by_status["review"] ?? 0) + (stats.by_status["processing"] ?? 0)}
        approved={(stats.by_status["approved"] ?? 0) + (stats.by_status["exported"] ?? 0)}
        hoursSaved={stats.hours_saved}
        extractionAccuracy={stats.extraction_accuracy}
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
            <li>1. AI extracts all fields with per-field confidence scores.</li>
            <li>2. Validates required fields, VAT format, math, and duplicates.</li>
            <li>3. Enriches from vendor knowledge base — auto-learns on approve.</li>
            <li>4. Export as Pohoda XML, CSV, JSON, or POST to a webhook.</li>
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
