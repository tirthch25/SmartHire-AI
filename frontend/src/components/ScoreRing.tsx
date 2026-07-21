"use client";
/**
 * SmartHire AI — Score Ring Component
 * Circular SVG score indicator with color-coded rings.
 */

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

function scoreColor(score: number) {
  if (score >= 75) return "var(--score-high)";
  if (score >= 50) return "var(--score-mid)";
  return "var(--score-low)";
}

export default function ScoreRing({ score, size = 80, strokeWidth = 6, label }: ScoreRingProps) {
  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.375rem" }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke="var(--bg-hover)"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.8s ease" }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: size > 60 ? "1.25rem" : "0.875rem",
          fontWeight: 700,
          color,
        }}>
          {Math.round(score)}
        </div>
      </div>
      {label && (
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textAlign: "center" }}>
          {label}
        </span>
      )}
    </div>
  );
}
