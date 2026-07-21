"use client";
/**
 * SmartHire AI — Interview Assistant Page
 * Select resume + job → generate questions → view by category
 */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import Toast from "@/components/Toast";
import { api, ApiError } from "@/lib/api";

interface Question {
  id: number; question: string; category: string;
  difficulty: "easy"|"medium"|"hard"; hints?: string[]; sample_answer?: string;
}
interface Session {
  id: string; questions: Question[]; question_count: number; created_at: string;
}

const CATEGORIES = ["All", "Technical", "Behavioral", "Situational", "Culture Fit"];
const DIFF_COLOR: Record<string, string> = {
  easy: "var(--success)", medium: "var(--warning)", hard: "var(--danger)"
};
const DIFF_BG: Record<string, string> = {
  easy: "rgba(16,185,129,0.1)", medium: "rgba(245,158,11,0.1)", hard: "rgba(239,68,68,0.1)"
};

export default function InterviewPage() {
  const [resumes, setResumes] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [filter, setFilter] = useState("All");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "success"|"error"|"info" } | null>(null);

  const [form, setForm] = useState({
    resume_id: "", job_id: "", difficulty: "medium",
    question_count: 15, focus_areas: ""
  });

  useEffect(() => {
    api.get<any>("/resume/list").then(d => setResumes((d.items ?? []).filter((r: any) => r.status === "completed")));
    api.get<any>("/job/list").then(d => setJobs(d.items ?? []));
    api.get<any>("/interview/list").then(d => setSessions(d.items ?? []));
  }, []);

  async function generate() {
    if (!form.resume_id || !form.job_id) {
      setToast({ msg: "Select a resume and job", type: "error" }); return;
    }
    setLoading(true); setActiveSession(null);
    try {
      const focus = form.focus_areas.split(",").map(s => s.trim()).filter(Boolean);
      const res = await api.post<{ session_id: string; task_id: string }>("/interview/generate", {
        resume_id: form.resume_id, job_id: form.job_id,
        difficulty: form.difficulty, question_count: form.question_count,
        focus_areas: focus,
      });
      // Poll
      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 2500));
        const status = await api.get<any>(`/interview/status/${res.task_id}`);
        if (status.state === "SUCCESS") {
          const session = await api.get<Session>(`/interview/${res.session_id}`);
          setActiveSession(session);
          setSessions(prev => [{ id: session.id, question_count: session.question_count, created_at: session.created_at }, ...prev]);
          done = true;
          setToast({ msg: `${session.question_count} questions generated!`, type: "success" });
        } else if (status.state === "FAILURE") {
          setToast({ msg: "Generation failed", type: "error" }); done = true;
        }
      }
    } catch (err) {
      setToast({ msg: err instanceof ApiError ? err.detail : "Error", type: "error" });
    } finally { setLoading(false); }
  }

  async function loadSession(id: string) {
    const session = await api.get<Session>(`/interview/${id}`);
    setActiveSession(session);
    setFilter("All");
  }

  const filteredQ = activeSession?.questions.filter(q =>
    filter === "All" || q.category === filter
  ) ?? [];

  return (
    <AppShell>
      <div style={{ display: "flex", gap: "1.5rem", height: "calc(100vh - 4rem)" }}>

        {/* Left: Controls + History */}
        <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "1rem", flexShrink: 0 }}>
          <h1 style={{ fontSize: "1.25rem" }}>Interview Prep</h1>

          {/* Generator Form */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <h4>Generate Questions</h4>
            <div className="form-group">
              <label className="form-label">Resume</label>
              <select className="form-input" value={form.resume_id} onChange={e => setForm(p=>({...p,resume_id:e.target.value}))}>
                <option value="">Select...</option>
                {resumes.map(r => <option key={r.id} value={r.id}>{r.filename.slice(0,28)}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Job</label>
              <select className="form-input" value={form.job_id} onChange={e => setForm(p=>({...p,job_id:e.target.value}))}>
                <option value="">Select...</option>
                {jobs.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Difficulty</label>
              <select className="form-input" value={form.difficulty} onChange={e => setForm(p=>({...p,difficulty:e.target.value}))}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Count ({form.question_count})</label>
              <input type="range" min={5} max={30} value={form.question_count}
                onChange={e => setForm(p=>({...p,question_count:+e.target.value}))}
                style={{ width: "100%", accentColor: "var(--accent)" }} />
            </div>
            <div className="form-group">
              <label className="form-label">Focus Areas (comma-separated)</label>
              <input className="form-input" placeholder="system design, algorithms"
                value={form.focus_areas} onChange={e => setForm(p=>({...p,focus_areas:e.target.value}))} />
            </div>
            <button className="btn btn-primary" onClick={generate} disabled={loading}
              style={{ width: "100%", justifyContent: "center" }}>
              {loading ? <span className="animate-spin" style={{display:"inline-block"}}>⟳</span> : "Generate"}
            </button>
          </div>

          {/* Session History */}
          {sessions.length > 0 && (
            <div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>PAST SESSIONS</p>
              {sessions.slice(0,8).map(s => (
                <button key={s.id} onClick={() => loadSession(s.id)}
                  className="btn btn-ghost btn-sm"
                  style={{ width: "100%", justifyContent: "space-between", marginBottom: "2px" }}>
                  <span>{s.question_count} questions</span>
                  <span style={{ fontSize: "0.6875rem" }}>{new Date(s.created_at).toLocaleDateString()}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Questions */}
        <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: "1rem" }}>
          {!activeSession && !loading && (
            <div className="card flex-center" style={{ flex: 1, flexDirection: "column", gap: "1rem" }}>
              <div style={{ fontSize: "3rem" }}>💬</div>
              <h3>No questions yet</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Select a resume and job, then click Generate
              </p>
            </div>
          )}

          {loading && (
            <div className="card flex-center" style={{ flex: 1, flexDirection: "column", gap: "1rem" }}>
              <span className="animate-spin" style={{ fontSize: "2rem", display: "inline-block" }}>⟳</span>
              <p style={{ color: "var(--text-muted)" }}>AI is crafting your questions…</p>
            </div>
          )}

          {activeSession && (
            <>
              {/* Category Filter */}
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {CATEGORIES.map(cat => (
                  <button key={cat} onClick={() => setFilter(cat)}
                    className={`btn btn-sm ${filter === cat ? "btn-primary" : "btn-secondary"}`}>
                    {cat}
                    {cat === "All"
                      ? ` (${activeSession.questions.length})`
                      : ` (${activeSession.questions.filter(q => q.category === cat).length})`}
                  </button>
                ))}
              </div>

              {/* Question Cards */}
              {filteredQ.map(q => (
                <div key={q.id} className="card" style={{ cursor: "pointer" }}
                  onClick={() => setExpanded(prev => {
                    const next = new Set(prev);
                    next.has(q.id) ? next.delete(q.id) : next.add(q.id);
                    return next;
                  })}>
                  <div className="flex-between">
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", flexShrink: 0 }}>#{q.id}</span>
                      <span className="badge" style={{ background: DIFF_BG[q.difficulty], color: DIFF_COLOR[q.difficulty], flexShrink: 0 }}>
                        {q.difficulty}
                      </span>
                      <span className="badge badge-muted" style={{ flexShrink: 0 }}>{q.category}</span>
                    </div>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                      {expanded.has(q.id) ? "▲" : "▼"}
                    </span>
                  </div>
                  <p style={{ marginTop: "0.625rem", fontSize: "0.9375rem", color: "var(--text-primary)", lineHeight: 1.5 }}>
                    {q.question}
                  </p>
                  {expanded.has(q.id) && (
                    <div className="animate-fade-in" style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {q.hints && q.hints.length > 0 && (
                        <div style={{ padding: "0.75rem", background: "var(--bg-secondary)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--accent)" }}>
                          <p style={{ fontSize: "0.75rem", color: "var(--accent)", fontWeight: 600, marginBottom: "0.375rem" }}>HINTS</p>
                          {q.hints.map((h, i) => <p key={i} style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>• {h}</p>)}
                        </div>
                      )}
                      {q.sample_answer && (
                        <div style={{ padding: "0.75rem", background: "var(--bg-secondary)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--success)" }}>
                          <p style={{ fontSize: "0.75rem", color: "var(--success)", fontWeight: 600, marginBottom: "0.375rem" }}>SAMPLE ANSWER OUTLINE</p>
                          <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{q.sample_answer}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppShell>
  );
}
