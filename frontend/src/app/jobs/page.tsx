"use client";
/**
 * SmartHire AI — Job Match Page
 * Add job descriptions → trigger ATS analysis → view score + skill gap
 */
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import ScoreRing from "@/components/ScoreRing";
import ProgressBar from "@/components/ProgressBar";
import Toast from "@/components/Toast";
import { api, ApiError } from "@/lib/api";

interface Job { id: string; title: string; company?: string; description: string; created_at: string; }
interface Resume { id: string; filename: string; status: string; }
interface ATSResult {
  id: string; overall_score: number;
  components: {
    keyword_match: { score: number; weight: number };
    formatting: { score: number; weight: number };
    section_completeness: { score: number; weight: number };
    skills_match: { score: number; weight: number };
    experience_relevance: { score: number; weight: number };
  };
  detailed_report: {
    matched_keywords: string[]; missing_keywords: string[];
    skill_match_details: { matched: string[]; missing: string[]; };
    recommendations: string[]; strengths: string[];
  };
}

const COMPONENT_META: [string, string, string][] = [
  ["keyword_match",        "Keyword Match",        "30%"],
  ["formatting",           "Formatting",           "15%"],
  ["section_completeness", "Section Completeness", "15%"],
  ["skills_match",         "Skills Match",         "20%"],
  ["experience_relevance", "Experience Relevance", "20%"],
];

export default function JobsPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "var(--bg-primary)" }} />}>
      <JobsContent />
    </Suspense>
  );
}

function JobsContent() {
  const params = useSearchParams();
  const preselectedResume = params.get("resume");

  const [jobs, setJobs] = useState<Job[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResume, setSelectedResume] = useState(preselectedResume ?? "");
  const [selectedJob, setSelectedJob] = useState("");
  const [atsResult, setAtsResult] = useState<ATSResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newJob, setNewJob] = useState({ title: "", company: "", description: "" });
  const [toast, setToast] = useState<{ msg: string; type: "success"|"error"|"info" } | null>(null);

  useEffect(() => {
    api.get<any>("/job/list").then(d => setJobs(d.items ?? []));
    api.get<any>("/resume/list").then(d => setResumes((d.items ?? []).filter((r: Resume) => r.status === "completed")));
  }, []);

  async function saveJob() {
    if (!newJob.title || newJob.description.length < 50) {
      setToast({ msg: "Title and description (min 50 chars) required", type: "error" }); return;
    }
    const j = await api.post<Job>("/job/create", newJob);
    setJobs(prev => [j, ...prev]);
    setSelectedJob(j.id);
    setShowAdd(false);
    setNewJob({ title: "", company: "", description: "" });
    setToast({ msg: "Job saved! Background parsing started.", type: "success" });
  }

  async function runAnalysis() {
    if (!selectedResume || !selectedJob) {
      setToast({ msg: "Select a resume and job first", type: "error" }); return;
    }
    setLoading(true); setAtsResult(null);
    try {
      const trigger = await api.post<{ task_id: string }>("/ats/analyze", { resume_id: selectedResume, job_id: selectedJob });
      // Poll task
      let done = false;
      while (!done) {
        await new Promise(r => setTimeout(r, 2500));
        const status = await api.get<any>(`/ats/status/${trigger.task_id}`);
        if (status.state === "SUCCESS") {
          const result = await api.get<ATSResult>(`/ats/score/${selectedResume}?job_id=${selectedJob}`);
          setAtsResult(result); done = true;
        } else if (status.state === "FAILURE") {
          setToast({ msg: "Analysis failed", type: "error" }); done = true;
        }
      }
    } catch (err) {
      setToast({ msg: err instanceof ApiError ? err.detail : "Error", type: "error" });
    } finally { setLoading(false); }
  }

  async function exportPDF() {
    if (!atsResult) return;
    const res = await api.get<{ download_url: string }>(`/ats/export/${atsResult.id}`);
    if (res.download_url.startsWith("/")) {
      setToast({ msg: "PDF export queued. Refresh in a moment.", type: "info" });
    } else {
      window.open(res.download_url, "_blank");
    }
  }

  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
        <div className="flex-between">
          <div>
            <h1>Job Match</h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.25rem" }}>
              Paste a job description and get your ATS score instantly
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAdd(v => !v)}>
            {showAdd ? "✕ Cancel" : "+ Add Job"}
          </button>
        </div>

        {/* Add Job Form */}
        {showAdd && (
          <div className="card animate-fade-in">
            <h3 style={{ marginBottom: "1rem" }}>New Job Description</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.875rem" }}>
                <div className="form-group">
                  <label className="form-label">Job Title *</label>
                  <input className="form-input" placeholder="Senior Software Engineer"
                    value={newJob.title} onChange={e => setNewJob(p => ({ ...p, title: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Company</label>
                  <input className="form-input" placeholder="Acme Corp"
                    value={newJob.company} onChange={e => setNewJob(p => ({ ...p, company: e.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Job Description * (paste full JD)</label>
                <textarea className="form-input form-textarea" rows={8}
                  placeholder="Paste the full job description here..."
                  value={newJob.description} onChange={e => setNewJob(p => ({ ...p, description: e.target.value }))} />
              </div>
              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
                <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={saveJob}>Save Job</button>
              </div>
            </div>
          </div>
        )}

        {/* Analyze Controls */}
        <div className="card">
          <h3 style={{ marginBottom: "1rem" }}>Run ATS Analysis</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "1rem", alignItems: "flex-end" }}>
            <div className="form-group">
              <label className="form-label">Resume</label>
              <select className="form-input" value={selectedResume} onChange={e => setSelectedResume(e.target.value)}>
                <option value="">Select resume...</option>
                {resumes.map(r => <option key={r.id} value={r.id}>{r.filename}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Job Description</label>
              <select className="form-input" value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
                <option value="">Select job...</option>
                {jobs.map(j => <option key={j.id} value={j.id}>{j.title}{j.company ? ` — ${j.company}` : ""}</option>)}
              </select>
            </div>
            <button className="btn btn-primary" onClick={runAnalysis} disabled={loading || !selectedResume || !selectedJob}
              style={{ whiteSpace: "nowrap" }}>
              {loading ? <span className="animate-spin" style={{ display: "inline-block" }}>⟳</span> : "Analyze →"}
            </button>
          </div>
        </div>

        {/* ATS Result */}
        {atsResult && (
          <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Overall */}
            <div className="card" style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
              <ScoreRing score={atsResult.overall_score} size={90} strokeWidth={7} />
              <div style={{ flex: 1 }}>
                <h2>ATS Score: {Math.round(atsResult.overall_score)} / 100</h2>
                <p style={{ marginTop: "0.25rem", fontSize: "0.875rem" }}>
                  {atsResult.overall_score >= 75 ? "Strong match — good chance of passing ATS filters"
                    : atsResult.overall_score >= 50 ? "Moderate match — consider improvements below"
                    : "Low match — significant improvements recommended"}
                </p>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={exportPDF}>↓ Export PDF</button>
            </div>

            {/* Components + Keywords */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="card">
                <h3 style={{ marginBottom: "1rem" }}>Score Breakdown</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
                  {COMPONENT_META.map(([key, label, weight]) => (
                    <ProgressBar key={key} label={label} weight={weight}
                      score={(atsResult.components as any)[key]?.score ?? 0} />
                  ))}
                </div>
              </div>
              <div className="card">
                <h3 style={{ marginBottom: "1rem" }}>Keywords</h3>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>Matched</p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem", marginBottom: "1rem" }}>
                  {atsResult.detailed_report?.matched_keywords?.slice(0,12).map(kw => (
                    <span key={kw} className="badge badge-success">{kw}</span>
                  ))}
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>Missing</p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem" }}>
                  {atsResult.detailed_report?.missing_keywords?.slice(0,12).map(kw => (
                    <span key={kw} className="badge badge-danger">{kw}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Recommendations */}
            {atsResult.detailed_report?.recommendations?.length > 0 && (
              <div className="card">
                <h3 style={{ marginBottom: "0.875rem" }}>💡 Recommendations</h3>
                <ul style={{ paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {atsResult.detailed_report.recommendations.map((r, i) => (
                    <li key={i} style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppShell>
  );
}
