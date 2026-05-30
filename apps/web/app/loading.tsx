export default function DashboardLoading() {
  return (
    <main className="page">
      <Skeleton style={{ width: "160px", height: "11px", marginBottom: "8px" }} />
      <Skeleton style={{ width: "480px", height: "42px", marginBottom: "8px" }} />
      <Skeleton style={{ width: "320px", height: "16px", marginBottom: "32px" }} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "16px", marginBottom: "32px" }}>
        {[0, 1, 2].map((i) => (
          <div key={i} className="stat-card" style={{ opacity: 1 }}>
            <Skeleton style={{ width: "80px", height: "10px", marginBottom: "14px" }} />
            <Skeleton style={{ width: "60px", height: "44px" }} />
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "24px" }}>
        <div className="card"><Skeleton style={{ width: "100%", height: "220px" }} /></div>
        <div className="card"><Skeleton style={{ width: "100%", height: "220px" }} /></div>
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
        ...style,
      }}
    />
  );
}
