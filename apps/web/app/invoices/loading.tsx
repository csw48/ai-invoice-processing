export default function InvoicesLoading() {
  return (
    <main className="page">
      <Skeleton style={{ width: "100px", height: "11px", marginBottom: "20px" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "24px" }}>
        <Skeleton style={{ width: "160px", height: "42px" }} />
        <Skeleton style={{ width: "120px", height: "36px" }} />
      </div>

      <div className="table-wrap">
        <div style={{ padding: "11px 20px", borderBottom: "1px solid var(--border)", background: "var(--surface-raised)", display: "flex", gap: "40px" }}>
          {["Vendor", "Invoice #", "Date", "Total", "Status"].map((h) => (
            <Skeleton key={h} style={{ width: "70px", height: "10px" }} />
          ))}
        </div>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{ padding: "14px 20px", borderBottom: "1px solid var(--border-subtle)", display: "flex", gap: "40px", alignItems: "center" }}>
            <Skeleton style={{ width: "140px", height: "13px" }} />
            <Skeleton style={{ width: "90px", height: "13px" }} />
            <Skeleton style={{ width: "80px", height: "13px" }} />
            <Skeleton style={{ width: "60px", height: "13px" }} />
            <Skeleton style={{ width: "72px", height: "20px", borderRadius: "100px" }} />
          </div>
        ))}
      </div>
    </main>
  );
}

function Skeleton({ style }: { style?: React.CSSProperties }) {
  return (
    <div
      style={{
        borderRadius: "var(--r-sm)",
        background: "linear-gradient(90deg, var(--surface-raised) 25%, var(--surface-hover) 50%, var(--surface-raised) 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s ease-in-out infinite",
        flexShrink: 0,
        ...style,
      }}
    />
  );
}
