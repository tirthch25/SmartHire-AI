"use client";
/**
 * SmartHire AI — Profile Page
 * View account info, update name/password, show usage stats, delete account.
 */
import { useEffect, useState, FormEvent } from "react";
import AppShell from "@/components/AppShell";
import Toast from "@/components/Toast";
import { api, ApiError } from "@/lib/api";
import { getMe, type User } from "@/lib/auth";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success"|"error"|"info" } | null>(null);
  const [form, setForm] = useState({ full_name: "", current_password: "", new_password: "" });

  useEffect(() => {
    Promise.all([getMe(), api.get<any>("/dashboard/stats")]).then(([u, s]) => {
      setUser(u); setStats(s);
      setForm(f => ({ ...f, full_name: u.full_name }));
    }).finally(() => setLoading(false));
  }, []);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: any = {};
      if (form.full_name !== user?.full_name) payload.full_name = form.full_name;
      if (form.new_password) {
        if (!form.current_password) { setToast({ msg: "Enter current password to change it", type: "error" }); return; }
        payload.current_password = form.current_password;
        payload.new_password = form.new_password;
      }
      if (Object.keys(payload).length === 0) { setToast({ msg: "No changes to save", type: "info" }); return; }
      const updated = await api.put<User>("/auth/me", payload);
      setUser(updated);
      setToast({ msg: "Profile updated!", type: "success" });
      setForm(f => ({ ...f, current_password: "", new_password: "" }));
    } catch (err) {
      setToast({ msg: err instanceof ApiError ? err.detail : "Update failed", type: "error" });
    } finally { setSaving(false); }
  }

  if (loading) return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: "60px", borderRadius: "var(--radius-lg)" }} />
        ))}
      </div>
    </AppShell>
  );

  return (
    <AppShell>
      <div style={{ maxWidth: "640px", display: "flex", flexDirection: "column", gap: "2rem" }}>
        <div>
          <h1>Profile</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.25rem" }}>
            Manage your account settings
          </p>
        </div>

        {/* Account Info */}
        <div className="card">
          <h3 style={{ marginBottom: "1.5rem" }}>Account Information</h3>
          <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "1.125rem" }}>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" value={user?.email ?? ""} disabled
                style={{ opacity: 0.6, cursor: "not-allowed" }} />
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Email cannot be changed</span>
            </div>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input id="full_name" className="form-input" value={form.full_name}
                onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
            </div>

            <div className="divider" />
            <h4>Change Password</h4>

            <div className="form-group">
              <label className="form-label">Current Password</label>
              <input id="current_password" type="password" className="form-input"
                placeholder="Leave blank to keep unchanged"
                value={form.current_password}
                onChange={e => setForm(f => ({ ...f, current_password: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">New Password</label>
              <input id="new_password" type="password" className="form-input"
                placeholder="Min 8 chars, 1 upper, 1 digit"
                value={form.new_password}
                onChange={e => setForm(f => ({ ...f, new_password: e.target.value }))} />
            </div>

            <button type="submit" className="btn btn-primary" disabled={saving}
              style={{ alignSelf: "flex-start" }}>
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </form>
        </div>

        {/* Usage Stats */}
        {stats && (
          <div className="card">
            <h3 style={{ marginBottom: "1rem" }}>Usage Summary</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1rem" }}>
              {[
                { label: "Resumes Uploaded",   value: stats.total_resumes },
                { label: "ATS Analyses Run",   value: stats.total_analyses },
                { label: "Jobs Saved",         value: stats.total_jobs },
                { label: "Cover Letters",      value: stats.total_cover_letters },
                { label: "Avg ATS Score",      value: `${stats.average_ats_score?.toFixed(1) ?? "—"}` },
                { label: "Best ATS Score",     value: `${stats.best_ats_score?.toFixed(1) ?? "—"}` },
              ].map(({ label, value }) => (
                <div key={label} style={{
                  padding: "1rem",
                  background: "var(--bg-secondary)",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--border)",
                }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)" }}>{value}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>{label}</div>
                </div>
              ))}
            </div>
            {stats.last_upload && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.875rem" }}>
                Last upload: {new Date(stats.last_upload).toLocaleDateString()}
              </p>
            )}
          </div>
        )}

        {/* Danger Zone */}
        <div className="card" style={{ border: "1px solid var(--danger)" }}>
          <h3 style={{ color: "var(--danger)", marginBottom: "0.5rem" }}>Danger Zone</h3>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
            Permanently delete your account and all associated data. This cannot be undone.
          </p>
          <button
            className="btn btn-danger btn-sm"
            onClick={() => {
              if (confirm("Are you sure? This will permanently delete your account.")) {
                setToast({ msg: "Account deletion is not yet available in this build", type: "info" });
              }
            }}
          >
            Delete Account
          </button>
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppShell>
  );
}
