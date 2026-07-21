"use client";
/**
 * SmartHire AI — Dashboard Page
 * Shows summary stats, ATS score trend, component averages, top jobs, and activity feed.
 */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import ScoreRing from "@/components/ScoreRing";
import ProgressBar from "@/components/ProgressBar";
import { api } from "@/lib/api";
import Link from "next/link";

interface Stats {
  total_resumes: number;
  total_analyses: number;
  total_jobs: number;
  total_cover_letters: number;
  average_ats_score: number;
  best_ats_score: number;
  last_upload: string | null;
}

interface ComponentAverages {
  keyword_match: number;
  formatting: number;
  section_completeness: number;
  skills_match: number;
  experience_relevance: number;
}

interface Analytics {
  component_averages: ComponentAverages;
  score_trend: { date: string; score: number; count: number }[];
  top_matched_jobs: { job_title: string; company: string; score: number; analysis_id: string }[];
}

interface Activity {
  activities: { type: string; description: string; timestamp: string }[];
}

const STAT_CARDS = [
  { key: "total_resumes",      label: "Resumes",         icon: "📄", href: "/resume" },
  { key: "total_analyses",     label: "ATS Analyses",    icon: "📊", href: "/resume" },
  { key: "total_jobs",         label: "Jobs Saved",      icon: "🎯", href: "/jobs" },
  { key: "total_cover_letters",label: "Cover Letters",   icon: "✉️",  href: "/cover-letter" },
] as const;

const COMPONENT_LABELS: Record<string, [string, string]> = {
  keyword_match:         ["Keyword Match",         "30%"],
  formatting:            ["Formatting",            "15%"],
  section_completeness:  ["Section Completeness",  "15%"],
  skills_match:          ["Skills Match",          "20%"],
  experience_relevance:  ["Experience Relevance",  "20%"],
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Stats>("/dashboard/stats"),
      api.get<Analytics>("/dashboard/analytics?days=30"),
      api.get<Activity>("/dashboard/activity?limit=8"),
    ]).then(([s, a, act]) => {
      setStats(s);
      setAnalytics(a);
      setActivity(act);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: "80px", borderRadius: "var(--radius-lg)" }} />
        ))}
      </div>
    </AppShell>
  );

  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>

        {/* Header */}
        <div>
          <h1>Dashboard</h1>
          <p style={{ color: "var(--text-muted)", marginTop: "0.25rem", fontSize: "0.875rem" }}>
            Your resume performance at a glance
          </p>
        </div>

        {/* Stat Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          {STAT_CARDS.map(({ key, label, icon, href }) => (
            <Link key={key} href={href} style={{ textDecoration: "none" }}>
              <div className="card card-hover" style={{ cursor: "pointer" }}>
                <div style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>{icon}</div>
                <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--text-primary)" }}>
                  {stats ? (stats as any)[key] : "—"}
                </div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>{label}</div>
              </div>
            </Link>
          ))}
        </div>

        {/* Score Overview + Component Averages */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1rem" }}>

          {/* Overall Score Ring */}
          <div className="card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem" }}>
            <h3 style={{ alignSelf: "flex-start" }}>Average Score</h3>
            <ScoreRing score={stats?.average_ats_score ?? 0} size={100} strokeWidth={8} />
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                Best: <span style={{ color: "var(--success)", fontWeight: 600 }}>{Math.round(stats?.best_ats_score ?? 0)}</span>
              </div>
            </div>
            <Link href="/resume" className="btn btn-primary btn-sm" style={{ width: "100%", justifyContent: "center" }}>
              + Upload Resume
            </Link>
          </div>

          {/* Component Averages */}
          <div className="card">
            <h3 style={{ marginBottom: "1.25rem" }}>Component Averages</h3>
            {analytics?.component_averages ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
                {Object.entries(COMPONENT_LABELS).map(([key, [label, weight]]) => (
                  <ProgressBar
                    key={key}
                    label={label}
                    weight={weight}
                    score={(analytics.component_averages as any)[key] ?? 0}
                  />
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                No analyses yet. <Link href="/resume">Upload a resume</Link> to get started.
              </p>
            )}
          </div>
        </div>

        {/* Top Jobs + Activity */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>

          {/* Top Matched Jobs */}
          <div className="card">
            <h3 style={{ marginBottom: "1rem" }}>Top Matched Jobs</h3>
            {analytics?.top_matched_jobs?.length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {analytics.top_matched_jobs.map((job, i) => (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "0.625rem 0.875rem",
                    background: "var(--bg-secondary)",
                    borderRadius: "var(--radius)",
                    border: "1px solid var(--border)",
                  }}>
                    <div>
                      <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--text-primary)" }}>
                        {job.job_title}
                      </div>
                      {job.company && (
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{job.company}</div>
                      )}
                    </div>
                    <ScoreRing score={job.score} size={44} strokeWidth={4} />
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                <Link href="/jobs">Add a job description</Link> to see match scores here.
              </p>
            )}
          </div>

          {/* Recent Activity */}
          <div className="card">
            <h3 style={{ marginBottom: "1rem" }}>Recent Activity</h3>
            {activity?.activities?.length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {activity.activities.map((a, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
                    <div style={{
                      width: "8px", height: "8px", borderRadius: "50%",
                      background: a.type.includes("ats") ? "var(--accent)"
                        : a.type.includes("cover") ? "var(--success)"
                        : "var(--text-muted)",
                      marginTop: "0.375rem", flexShrink: 0,
                    }} />
                    <div>
                      <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{a.description}</div>
                      <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                        {new Date(a.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>No recent activity.</p>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
