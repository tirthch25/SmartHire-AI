"use client";
/**
 * SmartHire AI — Cover Letter Generator Page
 * Select resume + job → choose tone + highlights → generate → edit → export PDF
 */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import Toast from "@/components/Toast";
import { api, ApiError } from "@/lib/api";

const TONES = ["professional", "confident", "enthusiastic", "formal"];

interface Letter {
  id: string; content: string; tone: string; word_count: number;
  job_id?: string; resume_id?: string; created_at: string;
}

export default function CoverLetterPage() {
  const [resumes, setResumes] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [letters, setLetters] = useState<any[]>([]);
  const [activeLetter, setActiveLetter] = useState<Letter | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [toast, setToast] = useState<{ msg: string; type: "success"|"error"|"info" } | null>(null);

  const [form, setForm] = useState({
    resume_id: "", job_id: "", tone: "professional",
    word_limit: 400, highlights: ""
  });

  useEffect(() => {
    api.get<any>("/resume/list").then(d => setResumes((d.items ?? []).filter((r: any) => r.status === "completed")));
    api.get<any>("/job/list").then(d => setJobs(d.items ?? []));
    api.get<any>("/cover-letter/list").then(d => setLetters(d.items ?? []));
  }, []);

  async function generate() {
    if (!form.resume_id || !form.job_id) {
      setToast({ msg: "Select a resume and job", type: "error" }); return;
    }
    setLoading(true); setActiveLetter(null);
    try {
      const highlights = form.highlights.split("\n").map(s=>s.trim()).filter(Boolean);
      const res = await api.post<{ letter_id: string; task_id: string }>("/cover-letter/generate", {
        resume_id: form.resume_id, job_id: form.job_id,
        tone: form.tone, word_limit: form.word_limit, highlights,
      });
      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 2500));
        const status = await api.get<any>(`/cover-letter/status/${res.task_id}`);
        if (status.state === "SUCCESS") {
          const letter = await api.get<Letter>(`/cover-letter/${res.letter_id}`);
          setActiveLetter(letter); setEditContent(letter.content);
          setLetters(prev => [{ id: letter.id, tone: letter.tone, word_count: letter.word_count, created_at: letter.created_at }, ...prev]);
          done = true;
          setToast({ msg: "Cover letter generated!", type: "success" });
        } else if (status.state === "FAILURE") {
          setToast({ msg: "Generation failed", type: "error" }); done = true;
        }
      }
    } catch (err) {
      setToast({ msg: err instanceof ApiError ? err.detail : "Error", type: "error" });
    } finally { setLoading(false); }
  }

  async function saveEdits() {
    if (!activeLetter) return;
    const updated = await api.put<Letter>(`/cover-letter/${activeLetter.id}`, { content: editContent });
    setActiveLetter(updated); setEditing(false);
    setToast({ msg: "Changes saved", type: "success" });
  }

  async function exportPDF() {
    if (!activeLetter) return;
    const res = await api.get<{ download_url: string }>(`/cover-letter/${activeLetter.id}/export`);
    window.open(res.download_url, "_blank");
  }

  async function loadLetter(id: string) {
    const letter = await api.get<Letter>(`/cover-letter/${id}`);
    setActiveLetter(letter); setEditContent(letter.content); setEditing(false);
  }

  return (
    <AppShell>
      <div style={{ display: "flex", gap: "1.5rem", height: "calc(100vh - 4rem)" }}>

        {/* Left Panel */}
        <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "1rem", flexShrink: 0 }}>
          <h1 style={{ fontSize: "1.25rem" }}>Cover Letters</h1>

          {/* Generator Form */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <h4>Generate</h4>
            <div className="form-group">
              <label className="form-label">Resume</label>
              <select className="form-input" value={form.resume_id} onChange={e=>setForm(p=>({...p,resume_id:e.target.value}))}>
                <option value="">Select...</option>
                {resumes.map(r => <option key={r.id} value={r.id}>{r.filename.slice(0,28)}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Job</label>
              <select className="form-input" value={form.job_id} onChange={e=>setForm(p=>({...p,job_id:e.target.value}))}>
                <option value="">Select...</option>
                {jobs.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Tone</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.375rem" }}>
                {TONES.map(t => (
                  <button key={t} onClick={() => setForm(p=>({...p,tone:t}))}
                    className={`btn btn-sm ${form.tone === t ? "btn-primary" : "btn-secondary"}`}
                    style={{ textTransform: "capitalize" }}>{t}</button>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Word Limit: {form.word_limit}</label>
              <input type="range" min={100} max={800} step={50} value={form.word_limit}
                onChange={e=>setForm(p=>({...p,word_limit:+e.target.value}))}
                style={{ width: "100%", accentColor: "var(--accent)" }} />
            </div>
            <div className="form-group">
              <label className="form-label">Highlights (one per line)</label>
              <textarea className="form-input form-textarea" rows={3}
                placeholder="5 years Python experience&#10;Led team of 8 engineers"
                value={form.highlights} onChange={e=>setForm(p=>({...p,highlights:e.target.value}))} />
            </div>
            <button className="btn btn-primary" onClick={generate} disabled={loading}
              style={{ width: "100%", justifyContent: "center" }}>
              {loading ? <span className="animate-spin" style={{display:"inline-block"}}>⟳</span> : "Generate Letter"}
            </button>
          </div>

          {/* History */}
          {letters.length > 0 && (
            <div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>PAST LETTERS</p>
              {letters.slice(0,6).map(l => (
                <button key={l.id} onClick={() => loadLetter(l.id)}
                  className="btn btn-ghost btn-sm"
                  style={{ width: "100%", justifyContent: "space-between", marginBottom: "2px" }}>
                  <span style={{ textTransform: "capitalize" }}>{l.tone} · {l.word_count}w</span>
                  <span style={{ fontSize: "0.6875rem" }}>{new Date(l.created_at).toLocaleDateString()}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Letter Preview / Editor */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "1rem", overflow: "hidden" }}>
          {!activeLetter && !loading && (
            <div className="card flex-center" style={{ flex: 1, flexDirection: "column", gap: "1rem" }}>
              <div style={{ fontSize: "3rem" }}>✉️</div>
              <h3>No letter yet</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Choose a resume and job, then click Generate
              </p>
            </div>
          )}

          {loading && (
            <div className="card flex-center" style={{ flex: 1, flexDirection: "column", gap: "1rem" }}>
              <span className="animate-spin" style={{ fontSize: "2rem", display: "inline-block" }}>⟳</span>
              <p style={{ color: "var(--text-muted)" }}>AI is writing your cover letter…</p>
            </div>
          )}

          {activeLetter && (
            <>
              {/* Toolbar */}
              <div className="flex-between">
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <span className="badge badge-muted" style={{ textTransform: "capitalize" }}>{activeLetter.tone}</span>
                  <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                    {activeLetter.word_count} words
                  </span>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {editing ? (
                    <>
                      <button className="btn btn-secondary btn-sm" onClick={() => { setEditing(false); setEditContent(activeLetter.content); }}>
                        Cancel
                      </button>
                      <button className="btn btn-primary btn-sm" onClick={saveEdits}>Save</button>
                    </>
                  ) : (
                    <>
                      <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>✏️ Edit</button>
                      <button className="btn btn-primary btn-sm" onClick={exportPDF}>↓ PDF</button>
                    </>
                  )}
                </div>
              </div>

              {/* Content */}
              <div className="card animate-fade-in" style={{ flex: 1, overflow: "auto" }}>
                {editing ? (
                  <textarea
                    value={editContent}
                    onChange={e => setEditContent(e.target.value)}
                    style={{
                      width: "100%", height: "100%", minHeight: "400px",
                      background: "transparent", border: "none", outline: "none",
                      color: "var(--text-primary)", fontSize: "0.9375rem",
                      lineHeight: 1.8, resize: "none", fontFamily: "var(--font-sans)",
                    }}
                  />
                ) : (
                  <div style={{ fontSize: "0.9375rem", lineHeight: 1.8, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                    {activeLetter.content}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppShell>
  );
}
