"use client";

import Link from "next/link";
import { CountUp } from "./count-up";

type Props = {
  total: number;
  review: number;
  approved: number;
};

export function StatCards({ total, review, approved }: Props) {
  const cards = [
    { label: "Total invoices", value: total, suffix: "", href: "/invoices" },
    { label: "Review queue", value: review, suffix: "", href: "/invoices" },
    { label: "Approved", value: approved, suffix: "", href: "/invoices" },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: "16px",
        marginTop: "32px",
      }}
    >
      {cards.map(({ label, value, suffix, href }, i) => (
        <Link
          key={label}
          href={href}
          className={`stat-card fade-up-${i + 1}`}
          style={{ textDecoration: "none" }}
        >
          <div className="stat-label">{label}</div>
          <div className="stat-value">
            <CountUp to={value} suffix={suffix} duration={800} />
          </div>
        </Link>
      ))}
    </div>
  );
}
