"use client";

import { CountUp } from "./count-up";

type Props = {
  total: number;
  hoursSaved: number;
  accuracyRate: number;
  valid: number;
};

export function StatsStatCards({ total, hoursSaved, accuracyRate, valid }: Props) {
  const cards = [
    { label: "Total Processed", value: total, suffix: "", decimals: 0 },
    { label: "Hours Saved", value: hoursSaved, suffix: "h", decimals: 1 },
    { label: "Accuracy Rate", value: accuracyRate * 100, suffix: "%", decimals: 0 },
    { label: "Valid Invoices", value: valid, suffix: "", decimals: 0 },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginTop: '32px' }}>
      {cards.map(({ label, value, suffix, decimals }, i) => (
        <div key={label} className={`stat-card fade-up-${i + 1}`}>
          <div className="stat-label">{label}</div>
          <div className="stat-value">
            <CountUp to={value} suffix={suffix} decimals={decimals} duration={900} />
          </div>
        </div>
      ))}
    </div>
  );
}
