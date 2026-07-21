"use client";
/**
 * SmartHire AI — Home Page
 * Redirects authenticated users to dashboard, otherwise to login.
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(isAuthenticated() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--bg-primary)",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{
          width: "48px", height: "48px",
          background: "var(--accent)",
          borderRadius: "12px",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.5rem", fontWeight: 700, color: "#fff",
          margin: "0 auto 1rem",
        }}>S</div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>Loading SmartHire AI…</p>
      </div>
    </div>
  );
}
