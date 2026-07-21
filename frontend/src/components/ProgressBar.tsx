"use client";
/**
 * SmartHire AI — ProgressBar Component
 */
interface ProgressBarProps {
  label: string;
  score: number;
  weight: string;
}

function scoreColor(score: number) {
  if (score >= 75) return "var(--score-high)";
  if (score >= 50) return "var(--score-mid)";
  return "var(--score-low)";
}

export default function ProgressBar({ label, score, weight }: ProgressBarProps) {
  const color = scoreColor(score);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
      <div className="flex-between">
        <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{label}</span>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{weight}</span>
          <span style={{ fontSize: "0.875rem", fontWeight: 600, color }}>{Math.round(score)}</span>
        </div>
      </div>
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
    </div>
  );
}
