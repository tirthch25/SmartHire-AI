"use client";
/**
 * SmartHire AI — Login / Register Page
 */
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, register } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import Toast from "@/components/Toast";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const [form, setForm] = useState({ email: "", password: "", full_name: "" });

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        await login({ email: form.email, password: form.password });
        router.push("/dashboard");
      } else {
        await register({ email: form.email, password: form.password, full_name: form.full_name });
        setToast({ msg: "Account created! Please sign in.", type: "success" });
        setMode("login");
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Something went wrong";
      setToast({ msg, type: "error" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--bg-primary)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "2rem",
    }}>
      <div style={{ width: "100%", maxWidth: "400px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div style={{
            width: "48px", height: "48px",
            background: "var(--accent)",
            borderRadius: "12px",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1.5rem", fontWeight: 700, color: "#fff",
            margin: "0 auto 1rem",
          }}>S</div>
          <h1 style={{ fontSize: "1.5rem", marginBottom: "0.375rem" }}>SmartHire AI</h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
            {mode === "login" ? "Sign in to your account" : "Create your account"}
          </p>
        </div>

        {/* Tab Toggle */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          background: "var(--bg-secondary)",
          borderRadius: "var(--radius)",
          padding: "3px",
          marginBottom: "1.5rem",
          border: "1px solid var(--border)",
        }}>
          {(["login", "register"] as Mode[]).map(m => (
            <button key={m} onClick={() => setMode(m)} style={{
              padding: "0.5rem",
              borderRadius: "calc(var(--radius) - 2px)",
              border: "none",
              cursor: "pointer",
              fontSize: "0.875rem",
              fontWeight: 500,
              background: mode === m ? "var(--bg-card)" : "transparent",
              color: mode === m ? "var(--text-primary)" : "var(--text-muted)",
              transition: "all var(--transition)",
            }}>
              {m === "login" ? "Sign In" : "Register"}
            </button>
          ))}
        </div>

        {/* Form */}
        <div className="card">
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.125rem" }}>
            {mode === "register" && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  className="form-input"
                  placeholder="Jane Smith"
                  value={form.full_name}
                  onChange={handleChange}
                  required
                  autoComplete="name"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                id="email"
                name="email"
                type="email"
                className="form-input"
                placeholder="jane@example.com"
                value={form.email}
                onChange={handleChange}
                required
                autoComplete="email"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                className="form-input"
                placeholder={mode === "register" ? "Min 8 chars, 1 upper, 1 digit" : "••••••••"}
                value={form.password}
                onChange={handleChange}
                required
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </div>

            <button id="submit-btn" type="submit" className="btn btn-primary btn-lg" disabled={loading}
              style={{ width: "100%", justifyContent: "center", marginTop: "0.25rem" }}>
              {loading
                ? <span className="animate-spin" style={{ display: "inline-block" }}>⟳</span>
                : mode === "login" ? "Sign In" : "Create Account"
              }
            </button>
          </form>
        </div>

        <p style={{ textAlign: "center", fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "1.25rem" }}>
          {mode === "login"
            ? <>New here? <button onClick={() => setMode("register")} style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", fontSize: "0.8125rem" }}>Create an account</button></>
            : <>Already have an account? <button onClick={() => setMode("login")} style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", fontSize: "0.8125rem" }}>Sign in</button></>
          }
        </p>
      </div>

      {toast && (
        <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />
      )}
    </div>
  );
}
