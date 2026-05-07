import { UploadPanel } from "../components/upload-panel";

const stats = [
  { label: "Invoices this month", value: "0" },
  { label: "Hours saved", value: "0" },
  { label: "Review queue", value: "0" },
];

export default function Dashboard() {
  return (
    <main className="mx-auto max-w-6xl p-8">
      <section className="rounded-3xl bg-slate-950 p-8 text-white shadow-xl">
        <p className="text-sm uppercase tracking-widest text-cyan-300">Slovak SMB invoice automation</p>
        <h1 className="mt-4 text-4xl font-bold">Upload invoices, verify AI extraction, export to Pohoda.</h1>
        <p className="mt-4 max-w-2xl text-slate-300">
          A focused MVP for accountants processing 50–500 invoices/month. Supabase stores invoices and vendor knowledge; FastAPI runs the extraction pipeline.
        </p>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {stats.map((item) => (
          <div key={item.label} className="rounded-2xl bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-500">{item.label}</p>
            <p className="mt-2 text-3xl font-semibold">{item.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <UploadPanel />
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold">Review workflow</h2>
          <ol className="mt-4 space-y-3 text-slate-700">
            <li>1. Extract fields from PDF text with confidence scores.</li>
            <li>2. Validate required fields, Slovak VAT format, currency, and VAT math.</li>
            <li>3. Enrich from vendor knowledge base in Supabase pgvector.</li>
            <li>4. Export JSON/CSV now; Pohoda XML connector scaffold included.</li>
          </ol>
        </div>
      </section>
    </main>
  );
}
