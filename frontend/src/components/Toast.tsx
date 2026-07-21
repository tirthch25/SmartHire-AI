"use client";
/**
 * SmartHire AI — Toast Notification Component
 */
import { useEffect } from "react";

export type ToastType = "success" | "error" | "info" | "warning";

interface ToastProps {
  message: string;
  type?: ToastType;
  onClose: () => void;
  duration?: number;
}

const ICONS: Record<ToastType, string> = {
  success: "✓",
  error: "✕",
  info: "ℹ",
  warning: "⚠",
};

const COLORS: Record<ToastType, string> = {
  success: "var(--success)",
  error: "var(--danger)",
  info: "var(--accent)",
  warning: "var(--warning)",
};

export default function Toast({ message, type = "info", onClose, duration = 4000 }: ToastProps) {
  useEffect(() => {
    const t = setTimeout(onClose, duration);
    return () => clearTimeout(t);
  }, [onClose, duration]);

  const color = COLORS[type];

  return (
    <div className="animate-fade-in" style={{
      position: "fixed",
      bottom: "1.5rem",
      right: "1.5rem",
      zIndex: 9999,
      background: "var(--bg-card)",
      border: `1px solid ${color}`,
      borderRadius: "var(--radius-lg)",
      padding: "0.875rem 1.25rem",
      display: "flex",
      alignItems: "center",
      gap: "0.75rem",
      boxShadow: "var(--shadow-lg)",
      maxWidth: "360px",
    }}>
      <span style={{
        width: "24px", height: "24px",
        borderRadius: "50%",
        background: `${color}22`,
        color,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "0.875rem", fontWeight: 700, flexShrink: 0,
      }}>
        {ICONS[type]}
      </span>
      <span style={{ fontSize: "0.875rem", color: "var(--text-primary)", flex: 1 }}>{message}</span>
      <button onClick={onClose} style={{
        background: "none", border: "none",
        color: "var(--text-muted)", cursor: "pointer",
        fontSize: "1rem", padding: "0", lineHeight: 1,
      }}>✕</button>
    </div>
  );
}
