import Link from "next/link";
import { StatsCharts } from "../../components/stats-charts";
import { StatsStatCards } from "../../components/stats-stat-cards";

type Stats = {
  total: number;
  by_status: Record<string, number>;
  valid: number;
  invalid: number;
  hours_saved: number;
  accuracy_rate: number;
  daily_counts: { date: string; count: number }[];
  agent_performance: { agent: string; avg_ms: number }[];
};

async function fetchStats(): Promise<Stats> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/stats`, { cache: "no-store" });
    if (res.ok) return res.json();
  } catch {}
  return {
    total: 0,
    by_status: {},
    valid: 0,
    invalid: 0,
    hours_saved: 0,
    accuracy_rate: 0,
    daily_counts: [],
    agent_performance: [],
  };
}

export default async function StatsPage() {
  const stats = await fetchStats();

  return (
    <main className="page">
      <Link href="/" className="page-back">← Dashboard</Link>
      <h1 className="page-title">Statistics</h1>
      <p className="page-sub">Processing volume, pipeline performance, and accuracy metrics.</p>
      <StatsStatCards
        total={stats.total}
        hoursSaved={stats.hours_saved}
        accuracyRate={stats.accuracy_rate}
        valid={stats.valid}
      />
      <StatsCharts stats={stats} />
    </main>
  );
}
