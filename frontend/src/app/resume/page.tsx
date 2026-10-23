"use client";
/**
 * SmartHire AI — Resume Upload & Management Page
 * Upload PDF → poll Celery task → view parsed data + ATS trigger
 */
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import ScoreRing from "@/components/ScoreRing";
import Toast from "@/components/Toast";
import { api, ApiError } from "@/lib/api";
import Link from "next/link";

interface ResumeSummary {
  id: string; filename: string; file_size: number; status: string; created_at: string;
}
interface PaginatedResumes { items: ResumeSummary[]; total: number; page: number; }
interface UploadResponse { resume_id: string; task_id: string; status: string; }
interface TaskStatus { task_id: string; state: string; progress: number; message: string; result?: any; }

function StatusBadge({ status }: { status: string }) {
  const cls = status === "completed" ? "badge-success"
    : status === "processing" ? "badge-info"
    : status === "failed" ? "badge-danger"
    : "badge-muted";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export default function ResumePage() {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [taskProgress, setTaskProgress] = useState<{ [key: string]: TaskStatus }>({});
  const [toast, setToast] = useState<{ msg: string; type: "success"|"error"|"info" } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRefs = useRef<{ [taskId: string]: ReturnType<typeof setInterval> }>({});

  async function loadResumes() {
    try {
      const data = await api.get<PaginatedResumes>("/resume/list");
      setResumes(data.items);
    } catch { /* ignore */ }
  }

  useEffect(() => { loadResumes(); }, []);

  async function uploadFile(file: File) {
    if (file.type !== "application/pdf") {
      setToast({ msg: "Only PDF files are accepted", type: "error" }); return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setToast({ msg: "File must be under 10 MB", type: "error" }); return;
    }
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await api.upload<UploadResponse>("/resume/upload", fd);
      setToast({ msg: "Resume uploaded! Processing started.", type: "success" });
      await loadResumes();
      startPolling(res.task_id, res.resume_id);
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Upload failed";
      setToast({ msg, type: "error" });
    } finally {
      setUploading(false);
    }
  }

  function startPolling(taskId: string, resumeId: string) {
    const interval = setInterval(async () => {
      const status = await api.get<TaskStatus>(`/resume/task/${taskId}/status`);
      setTaskProgress(prev => ({ ...prev, [resumeId]: status }));
      if (status.state === "SUCCESS" || status.state === "FAILURE") {
        clearInterval(interval);
        delete pollRefs.current[taskId];
        await loadResumes();
        if (status.state === "SUCCESS") setToast({ msg: "Resume processed successfully!", type: "success" });
        else setToast({ msg: "Resume processing failed", type: "error" });
      }
    }, 2000);
    pollRefs.current[taskId] = interval;
  }

  async function deleteResume(id: string) {
    if (!confirm("Delete this resume? This cannot be undone.")) return;
    await api.delete(`/resume/${id}`);
    setResumes(prev => prev.filter(r => r.id !== id));
    setToast({ msg: "Resume deleted", type: "info" });
  }

  async function downloadResume(id: string) {
    const res = await api.get<{ download_url: string }>(`/resume/${id}/download`);
    await api.download(res.download_url);
  }

  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
        <div>
          <h1>Resumes</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.25rem" }}>
            Upload your PDF resume to get ATS scores and AI-powered insights
          </p>
        </div>

        {/* Drop Zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }}
          onClick={() => fileRef.current?.click()}
          className="card"
          style={{
            border: `2px dashed ${dragOver ? "var(--accent)" : "var(--border)"}`,
            background: dragOver ? "var(--accent-subtle)" : "var(--bg-card)",
            cursor: "pointer",
            textAlign: "center",
            padding: "3rem",
            transition: "all var(--transition)",
          }}
        >
          <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }}
            onChange={e => { const f = e.target.files?.[0]; if (f) uploadFile(f); e.target.value = ""; }} />
          <div style={{ fontSize: "2.5rem", marginBottom: "1rem" }}>
            {uploading ? <span className="animate-spin" style={{ display: "inline-block" }}>⟳</span> : "📂"}
          </div>
          <p style={{ color: "var(--text-primary)", fontWeight: 500 }}>
            {uploading ? "Uploading..." : "Drop your PDF here or click to browse"}
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginTop: "0.375rem" }}>
            PDF only · Max 10 MB
          </p>
        </div>

        {/* Resumes List */}
        {resumes.length > 0 && (
          <div>
            <h3 style={{ marginBottom: "0.875rem" }}>Your Resumes ({resumes.length})</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {resumes.map(r => {
                const task = taskProgress[r.id];
                return (
                  <div key={r.id} className="card" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div style={{ fontSize: "1.75rem" }}>📄</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                        <span className="truncate" style={{ fontWeight: 500, fontSize: "0.9375rem" }}>{r.filename}</span>
                        <StatusBadge status={task?.state === "PROGRESS" ? "processing" : r.status} />
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {(r.file_size / 1024).toFixed(0)} KB · {new Date(r.created_at).toLocaleDateString()}
                      </div>
                      {task?.state === "PROGRESS" && (
                        <div style={{ marginTop: "0.5rem" }}>
                          <div className="progress-bar">
                            <div className="progress-fill"
                              style={{ width: `${task.progress}%`, background: "var(--accent)" }} />
                          </div>
                          <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                            {task.message}
                          </div>
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
                      {r.status === "completed" && (
                        <Link href={`/jobs?resume=${r.id}`} className="btn btn-primary btn-sm">
                          Analyze
                        </Link>
                      )}
                      <button className="btn btn-secondary btn-sm" onClick={() => downloadResume(r.id)}>↓</button>
                      <button className="btn btn-danger btn-sm" onClick={() => deleteResume(r.id)}>✕</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {resumes.length === 0 && !uploading && (
          <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>
            No resumes uploaded yet. Drop a PDF above to get started.
          </p>
        )}
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </AppShell>
  );
}
