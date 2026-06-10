"use client";

type Stats = {
  total: number;
  by_status: Record<string, number>;
  valid: number;
  invalid: number;
  hours_saved: number;
  accuracy_rate: number;
  extraction_accuracy?: number | null;
  field_corrections?: { field: string; count: number; rate: number }[];
  daily_counts: { date: string; count: number }[];
  agent_performance: { agent: string; avg_ms: number }[];
};

export function StatsCharts({ stats }: { stats: Stats }) {
  return (
    <div style={{ marginTop: "32px", display: "flex", flexDirection: "column", gap: "24px" }}>
      <VolumeChart data={stats.daily_counts ?? []} />
      <FieldCorrectionsChart
        data={stats.field_corrections ?? []}
        extractionAccuracy={stats.extraction_accuracy ?? null}
      />
      <AgentPerformanceChart data={stats.agent_performance ?? []} />
    </div>
  );
}

const FIELD_LABELS: Record<string, string> = {
  vendor_name: "Vendor", vendor_ico: "IČO", vendor_vat: "IČ DPH", vendor_iban: "IBAN",
  invoice_number: "Invoice number", invoice_date: "Invoice date", delivered_at: "Delivery date",
  due_date: "Due date", subtotal: "Subtotal", vat_amount: "VAT amount", total_amount: "Total",
  amount_due: "Amount due", currency: "Currency", po_number: "PO number", cost_center: "Cost center",
  recipient_name: "Recipient", recipient_vat: "Recipient IČ DPH", recipient_address: "Recipient address",
  recipient_postcode: "Recipient postcode", recipient_city: "Recipient city", recipient_country: "Recipient country",
};

function FieldCorrectionsChart({
  data,
  extractionAccuracy,
}: {
  data: { field: string; count: number; rate: number }[];
  extractionAccuracy: number | null;
}) {
  const subtitle =
    extractionAccuracy !== null
      ? `${Math.round(extractionAccuracy * 100)}% of extracted invoices needed no manual correction`
      : null;

  if (data.length === 0) {
    return (
      <div className="card">
        <p className="card-title">Extraction Accuracy</p>
        {subtitle && (
          <p style={{ marginTop: "4px", fontSize: "12px", color: "var(--text-muted)" }}>{subtitle}</p>
        )}
        <div className="empty-state">No manual corrections recorded yet</div>
      </div>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="card">
      <p className="card-title">Extraction Accuracy</p>
      {subtitle && (
        <p style={{ marginTop: "4px", fontSize: "12px", color: "var(--text-muted)" }}>{subtitle}</p>
      )}
      <p style={{ marginTop: "12px", fontSize: "11px", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)" }}>
        Most corrected fields
      </p>
      <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "14px" }}>
        {data.map(({ field, count, rate }) => (
          <div
            key={field}
            style={{
              display: "grid",
              gridTemplateColumns: "140px 1fr 110px",
              gap: "12px",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              {FIELD_LABELS[field] ?? field}
            </span>
            <div style={{ height: "6px", background: "var(--surface-raised)", borderRadius: "3px", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${((count / maxCount) * 100).toFixed(1)}%`,
                  background: "var(--warning)",
                  borderRadius: "3px",
                  transition: "width 0.6s ease",
                }}
              />
            </div>
            <span className="mono" style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "right" }}>
              {count}× ({Math.round(rate * 100)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VolumeChart({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) {
    return (
      <div className="card">
        <p className="card-title">Invoice Volume</p>
        <div className="empty-state">No data yet — upload invoices to see volume trends</div>
      </div>
    );
  }

  const W = 800;
  const H = 160;
  const PAD = { top: 10, right: 10, bottom: 30, left: 30 };
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  const points = data.map((d, i) => {
    const x =
      PAD.left + (i / Math.max(data.length - 1, 1)) * (W - PAD.left - PAD.right);
    const y =
      PAD.top + (1 - d.count / maxCount) * (H - PAD.top - PAD.bottom);
    return { x, y, ...d };
  });

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");

  const areaPath =
    linePath +
    ` L ${points[points.length - 1].x} ${H - PAD.bottom}` +
    ` L ${points[0].x} ${H - PAD.bottom} Z`;

  const labelIndices = [0, Math.floor(data.length / 2), data.length - 1].filter(
    (v, i, a) => a.indexOf(v) === i
  );

  return (
    <div className="card">
      <p className="card-title">Invoice Volume</p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "180px", overflow: "visible", marginTop: "16px" }}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Area fill */}
        <path d={areaPath} fill="url(#areaGradient)" />

        {/* Line */}
        <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="1.5" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3" fill="var(--accent)" />
        ))}

        {/* X-axis baseline */}
        <line
          x1={PAD.left}
          y1={H - PAD.bottom}
          x2={W - PAD.right}
          y2={H - PAD.bottom}
          stroke="var(--border)"
          strokeWidth="1"
        />

        {/* X-axis labels */}
        {labelIndices.map((idx) => (
          <text
            key={idx}
            x={points[idx].x}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fontSize="10"
            fill="var(--text-faint)"
            fontFamily="var(--font-mono)"
          >
            {data[idx].date.slice(5)}
          </text>
        ))}

        {/* Y-axis labels: 0 at bottom, maxCount at top */}
        <text
          x={PAD.left - 5}
          y={H - PAD.bottom}
          textAnchor="end"
          fontSize="9"
          fill="var(--text-faint)"
          fontFamily="var(--font-mono)"
        >
          0
        </text>
        <text
          x={PAD.left - 5}
          y={PAD.top + 4}
          textAnchor="end"
          fontSize="9"
          fill="var(--text-faint)"
          fontFamily="var(--font-mono)"
        >
          {maxCount}
        </text>
      </svg>
    </div>
  );
}

function AgentPerformanceChart({
  data,
}: {
  data: { agent: string; avg_ms: number }[];
}) {
  if (data.length === 0) {
    return (
      <div className="card">
        <p className="card-title">Pipeline Performance</p>
        <div className="empty-state">No pipeline data yet — process invoices to see agent timing</div>
      </div>
    );
  }

  const maxMs = Math.max(...data.map((d) => d.avg_ms), 1);

  return (
    <div className="card">
      <p className="card-title">Pipeline Performance</p>
      <div
        style={{
          marginTop: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
      >
        {data.map(({ agent, avg_ms }) => (
          <div
            key={agent}
            style={{
              display: "grid",
              gridTemplateColumns: "90px 1fr 60px",
              gap: "12px",
              alignItems: "center",
            }}
          >
            <span
              className="mono"
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                textTransform: "capitalize",
              }}
            >
              {agent}
            </span>
            <div
              style={{
                height: "6px",
                background: "var(--surface-raised)",
                borderRadius: "3px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${((avg_ms / maxMs) * 100).toFixed(1)}%`,
                  background: "var(--accent)",
                  borderRadius: "3px",
                  transition: "width 0.6s ease",
                }}
              />
            </div>
            <span
              className="mono"
              style={{
                fontSize: "11px",
                color: "var(--accent)",
                textAlign: "right",
              }}
            >
              {avg_ms}ms
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
