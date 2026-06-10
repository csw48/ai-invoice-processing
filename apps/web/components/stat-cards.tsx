"use client";

import Link from "next/link";
import { CountUp } from "./count-up";

type Props = {
  total: number;
  needsReview: number;
  approved: number;
  hoursSaved: number;
  extractionAccuracy: number | null;
};

export function StatCards({ total, needsReview, approved, hoursSaved, extractionAccuracy }: Props) {
  const cards = [
    { label: "Total invoices", value: total, suffix: "", decimals: 0, href: "/invoices" },
    { label: "Needs review", value: needsReview, suffix: "", decimals: 0, href: "/invoices?needs_review=true" },
    { label: "Approved / exported", value: approved, suffix: "", decimals: 0, href: "/invoices?status=exported" },
    { label: "Hours saved", value: hoursSaved, suffix: "h", decimals: 1, href: "/stats" },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "16px",
        marginTop: "32px",
      }}
    >
      {cards.map(({ label, value, suffix, decimals, href }, i) => (
        <Link
          key={label}
          href={href}
          className={`stat-card fade-up-${i + 1}`}
          style={{ textDecoration: "none" }}
        >
          <div className="stat-label">{label}</div>
          <div className="stat-value">
            <CountUp to={value} suffix={suffix} decimals={decimals} duration={800} />
          </div>
        </Link>
      ))}
      {extractionAccuracy !== null && (
        <Link
          href="/stats"
          className="stat-card fade-up-5"
          style={{ textDecoration: "none" }}
        >
          <div className="stat-label">Extraction accuracy</div>
          <div className="stat-value">
            <CountUp to={Math.round(extractionAccuracy * 100)} suffix="%" decimals={0} duration={800} />
          </div>
        </Link>
      )}
    </div>
  );
}
