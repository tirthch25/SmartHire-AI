"use client";

/**
 * SmartHire AI — Sidebar Navigation Component
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";

const NAV_ITEMS = [
  { href: "/dashboard",     label: "Dashboard",        icon: "⊞" },
  { href: "/resume",        label: "Resumes",           icon: "📄" },
  { href: "/jobs",          label: "Job Match",         icon: "🎯" },
  { href: "/interview",     label: "Interview Prep",    icon: "💬" },
  { href: "/cover-letter",  label: "Cover Letters",     icon: "✉️" },
  { href: "/profile",       label: "Profile",           icon: "👤" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <aside style={{
      width: "220px",
      minHeight: "100vh",
      background: "var(--bg-secondary)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      padding: "1.25rem 0",
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "0 1.25rem 1.5rem" }}>
        <Link href="/dashboard" style={{ textDecoration: "none" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
            <div style={{
              width: "32px", height: "32px",
              background: "var(--accent)",
              borderRadius: "8px",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1rem", fontWeight: 700, color: "#fff",
            }}>S</div>
            <span style={{ fontWeight: 600, fontSize: "0.9375rem", color: "var(--text-primary)" }}>
              SmartHire AI
            </span>
          </div>
        </Link>
      </div>

      <div style={{ height: "1px", background: "var(--border)", margin: "0 1.25rem 1rem" }} />

      {/* Nav items */}
      <nav style={{ flex: 1, display: "flex", flexDirection: "column", gap: "2px", padding: "0 0.75rem" }}>
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link key={href} href={href} style={{
              display: "flex",
              alignItems: "center",
              gap: "0.625rem",
              padding: "0.5rem 0.625rem",
              borderRadius: "var(--radius)",
              fontSize: "0.875rem",
              fontWeight: active ? 500 : 400,
              color: active ? "var(--text-primary)" : "var(--text-secondary)",
              background: active ? "var(--bg-hover)" : "transparent",
              textDecoration: "none",
              transition: "all var(--transition)",
            }}>
              <span style={{ fontSize: "1rem", lineHeight: 1 }}>{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div style={{ padding: "1rem 0.75rem 0" }}>
        <div style={{ height: "1px", background: "var(--border)", marginBottom: "0.75rem" }} />
        <button
          onClick={handleLogout}
          className="btn btn-ghost btn-sm"
          style={{ width: "100%", justifyContent: "flex-start", gap: "0.625rem" }}
        >
          <span>↩</span> Sign out
        </button>
      </div>
    </aside>
  );
}
