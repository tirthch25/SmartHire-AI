"use client";
/**
 * SmartHire AI — Authenticated App Shell Layout
 * Wraps all dashboard pages with sidebar + main content area.
 */
import Sidebar from "@/components/Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <main style={{
        flex: 1,
        overflow: "auto",
        background: "var(--bg-primary)",
        padding: "2rem 2.5rem",
      }}>
        {children}
      </main>
    </div>
  );
}
