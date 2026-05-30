export default function StatsLoading() {
  return (
    <main className="page">
      <Skeleton style={{ width: "100px", height: "11px", marginBottom: "20px" }} />
      <Skeleton style={{ width: "200px", height: "42px", marginBottom: "8px" }} />
      <Skeleton style={{ width: "340px", height: "16px", marginBottom: "32px" }} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "24px" }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="stat-card">
            <Skeleton style={{ width: "80px", height: "10px", marginBottom: "14px" }} />
            <Skeleton style={{ width: "70px", height: "44px" }} />
          </div>
        ))}
      </div>

      <div className="card" style={{ marginBottom: "24px" }}>
        <Skeleton style={{ width: "160px", height: "20px", marginBottom: "24px" }} />
        <Skeleton style={{ width: "100%", height: "180px" }} />
      </div>

      <div className="card">
        <Skeleton style={{ width: "180px", height: "20px", marginBottom: "24px" }} />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "90px 1fr 60px", gap: "12px", alignItems: "center", marginBottom: "14px" }}>
            <Skeleton style={{ height: "12px" }} />
            <Skeleton style={{ height: "6px" }} />
            <Skeleton style={{ height: "12px" }} />
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
        ...style,
      }}
    />
  );
}
