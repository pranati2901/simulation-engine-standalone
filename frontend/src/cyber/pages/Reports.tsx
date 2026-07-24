import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ReportContent, RunSummary } from "../api/types";
import { ROLE_ACCENT, ROLE_ICON } from "../components/TeamBoard";
import AarReport from "../components/AarReport";

const STATUS_ICON: Record<string, [string, string]> = {
  done: ["fa-check-circle", "var(--gc-green)"], active: ["fa-circle-notch", "var(--gc-accent)"],
  blocked: ["fa-ban", "var(--gc-red)"], skipped: ["fa-minus-circle", "var(--gc-muted)"],
  pending: ["fa-circle", "var(--gc-muted)"],
};

function riskColor(score: number) { return score >= 70 ? "var(--gc-red)" : score >= 40 ? "var(--gc-yellow)" : "var(--gc-green)"; }
function stateColor(s: string) { return s === "compromised" ? "var(--gc-red)" : s === "contained" ? "var(--gc-teal)" : s === "suspicious" ? "var(--gc-yellow)" : "var(--gc-green)"; }
function healthBadge(h: string) { return h === "down" ? { bg: "rgba(255,71,87,.2)", color: "var(--gc-red)", label: "DOWN" } : h === "degraded" ? { bg: "rgba(255,214,0,.2)", color: "var(--gc-yellow)", label: "DEGRADED" } : { bg: "rgba(0,230,118,.12)", color: "var(--gc-green)", label: "OK" }; }
function tagColor(t: string) { return t === "attack" ? "rgba(255,112,67,.18)" : t === "detection" ? "rgba(0,230,118,.18)" : t === "block" ? "rgba(0,212,255,.15)" : t === "response" ? "rgba(77,208,225,.18)" : t === "inject" ? "rgba(123,97,255,.18)" : t === "fail" ? "rgba(107,122,149,.18)" : "rgba(255,255,255,.06)"; }
function zoneColor(s: string) { return s === "breached" ? "var(--gc-red)" : s === "contained" ? "var(--gc-teal)" : "var(--gc-green)"; }
const credColor: Record<string, string> = { none: "var(--gc-muted)", user: "var(--gc-yellow)", privileged: "var(--gc-orange)", domain_admin: "var(--gc-red)" };

export default function Reports() {
  const { runId } = useParams();
  const nav = useNavigate();
  const { data: runs } = useQuery<RunSummary[]>({ queryKey: ["runs"], queryFn: () => api.runs(30), enabled: !runId });
  const { data: report } = useQuery<ReportContent>({ queryKey: ["report", runId], queryFn: () => api.report(runId!), enabled: !!runId });

  if (!runId) {
    return (
      <>
        <div className="section-header"><h1>After-Action Reports</h1><p>Select a completed run to view its debrief</p></div>
        {(runs ?? []).length === 0 && <div className="center-empty">No runs yet.</div>}
        {(runs ?? []).map((r) => (
          <div key={r.id} className="card" style={{ marginBottom: 12, cursor: "pointer" }} onClick={() => nav(`/reports/${r.id}`)}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div><div style={{ fontWeight: 600 }}>{r.scenario_name}</div><div className="muted" style={{ fontSize: 12.5 }}>{new Date(r.created_at).toLocaleString()} · {r.operator || "Operator"}</div></div>
              <div style={{ fontFamily: "var(--mono)" }}><span style={{ color: "var(--gc-red)" }}>R {r.scores.red}</span> · <span style={{ color: "var(--gc-green)" }}>B {r.scores.blue}</span></div>
            </div>
          </div>
        ))}
      </>
    );
  }

  if (!report) return <div className="center-empty"><span className="spinner" /> Loading report...</div>;

  // Live / guided / immersive-sim reports use a different shape (no precompute `scorecard`) → render
  // the readable AAR (per-team scorecards, MITRE chain, recommendations) with Print/PDF.
  if (!(report as any).scorecard) {
    return (
      <>
        <div className="section-header no-print" style={{ display: "flex", justifyContent: "space-between" }}>
          <div><h1>After-Action Report</h1><p>Cyber-range debrief</p></div>
          <button className="btn btn-ghost" onClick={() => nav("/reports")}><i className="fa fa-arrow-left" /> All reports</button>
        </div>
        <AarReport report={report as any} />
      </>
    );
  }

  const sc = report.scorecard, fin = report.financial_impact, kf = report.key_findings;
  const ap = report.attack_path ?? [], pa = report.per_asset ?? [], ce = report.control_effectiveness ?? [];
  const dw = report.dwell_analysis, za = report.zone_analysis ?? [], ct = report.credential_timeline ?? [];
  const mb = report.maturity_score.breakdown;

  return (
    <>
      <div className="section-header" style={{ display: "flex", justifyContent: "space-between" }}>
        <div><h1>{report.scenario_name} — After-Action Report</h1><p>{report.duration_min}-minute exercise · executive debrief</p></div>
        <button className="btn btn-ghost" onClick={() => nav("/reports")}><i className="fa fa-arrow-left" /> All reports</button>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-file-lines" /> Executive Summary</div>
        <p style={{ fontSize: 14, lineHeight: 1.8 }}>{report.exec_summary}</p>
      </div>

      {(report.role_scorecards ?? []).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>
            <i className="fa fa-users" /> Per-Team Scorecards
            {report.focus_role && <span className="tag" style={{ marginLeft: 8 }}>focus: {report.focus_role}</span>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(report.role_scorecards!.length, 5)},1fr)`, gap: 12 }}>
            {report.role_scorecards!.map((rc) => {
              const accent = ROLE_ACCENT[rc.role] ?? "var(--gc-accent)";
              const focused = report.focus_role === rc.role;
              return (
                <div key={rc.role} className="card" style={{ padding: 14, borderColor: focused ? accent : "var(--gc-border)", boxShadow: focused ? `0 0 0 1px ${accent}` : "none" }}>
                  <div className="card-header" style={{ marginBottom: 8 }}>
                    <div className="card-title" style={{ fontSize: 12.5 }}><i className={`fa ${ROLE_ICON[rc.role] || "fa-user"}`} style={{ color: accent }} /> {rc.title}</div>
                    <span style={{ fontFamily: "var(--mono)", fontWeight: 700, color: accent }}>{rc.score}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--gc-muted)", marginBottom: 8 }}>{rc.headline} · {rc.tasks_done}/{rc.tasks_total} tasks</div>
                  {Object.entries(rc.kpis).map(([k, v]) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "2px 0" }}>
                      <span className="muted">{k}</span><span style={{ fontFamily: "var(--mono)" }}>{v}</span>
                    </div>
                  ))}
                  <div style={{ borderTop: "1px solid var(--gc-border)", marginTop: 8, paddingTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                    {rc.tasks.map((t) => {
                      const [icon, color] = STATUS_ICON[t.status] ?? STATUS_ICON.pending;
                      return (
                        <div key={t.id} style={{ display: "flex", gap: 6, alignItems: "flex-start", fontSize: 12 }} title={t.description}>
                          <i className={`fa ${icon}`} style={{ color, marginTop: 2, fontSize: 11, width: 11 }} />
                          <span style={{ color: t.status === "done" ? "var(--gc-text)" : "var(--gc-muted)", textDecoration: t.status === "blocked" ? "line-through" : "none" }}>{t.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="stats-row">
        <Stat cls={sc.winner === "Blue" ? "green" : "red"} label="Outcome" value={`${sc.winner} advantage`} sub={`Red ${sc.red_score} / Blue ${sc.blue_score}`} />
        <Stat cls="accent" label="Detection rate" value={`${Math.round(sc.detection_rate * 100)}%`} sub={`MTTD ${sc.mttd_min}m · MTTR ${sc.mttr_min}m`} />
        <Stat cls="purple" label="Security maturity" value={`${report.maturity_score.score}`} sub={report.maturity_score.band} />
        <Stat cls="red" label="Est. financial impact" value={fin.estimate_low_usd + fin.estimate_high_usd > 0 ? `$${(fin.estimate_low_usd / 1e6).toFixed(1)}-${(fin.estimate_high_usd / 1e6).toFixed(1)}M` : "$0"} sub={`${sc.contained} contained · ${sc.blocked} blocked`} />
      </div>

      {kf && <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-magnifying-glass-chart" /> Key Findings</div>
        <div style={{ background: "rgba(123,97,255,.08)", border: "1px solid rgba(123,97,255,.25)", borderRadius: 10, padding: "12px 16px", marginBottom: 16, fontSize: 13 }}>
          <strong style={{ color: "var(--gc-accent2)" }}>Critical Moment:</strong> {kf.critical_moment}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.5, color: "var(--gc-green)", marginBottom: 10 }}>Strengths</div>
            {kf.strengths.map((s, i) => <div key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, marginBottom: 8, lineHeight: 1.5 }}><i className="fa fa-check-circle" style={{ color: "var(--gc-green)", marginTop: 3, flexShrink: 0 }} /><span>{s}</span></div>)}
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.5, color: "var(--gc-red)", marginBottom: 10 }}>Weaknesses</div>
            {kf.weaknesses.map((w, i) => <div key={i} style={{ display: "flex", gap: 8, fontSize: 12.5, marginBottom: 8, lineHeight: 1.5 }}><i className="fa fa-exclamation-triangle" style={{ color: "var(--gc-red)", marginTop: 3, flexShrink: 0 }} /><span>{w}</span></div>)}
          </div>
        </div>
      </div>}

      {ap.length > 0 && <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-route" /> Attack Path</div>
        <div style={{ display: "flex", gap: 0, overflowX: "auto", paddingBottom: 8 }}>
          {ap.map((step, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
              <div style={{ background: step.result === "blocked" ? "rgba(0,212,255,.08)" : "rgba(255,112,67,.08)", border: `1px solid ${step.result === "blocked" ? "rgba(0,212,255,.3)" : step.severity === "critical" ? "rgba(255,71,87,.4)" : "rgba(255,112,67,.3)"}`, borderRadius: 10, padding: "10px 14px", minWidth: 140, textAlign: "center", opacity: step.result === "blocked" ? 0.7 : 1 }}>
                <div style={{ fontSize: 11, color: "var(--gc-muted)", fontFamily: "var(--mono)" }}>{step.clock}</div>
                <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 2, color: step.result === "blocked" ? "var(--gc-teal)" : "var(--gc-text)" }}>{step.name}</div>
                {step.target_name && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 2 }}>{step.target_name}</div>}
                {step.result === "blocked" && <div style={{ fontSize: 11, color: "var(--gc-teal)", marginTop: 4, fontWeight: 600 }}>BLOCKED by {step.blocked_by}</div>}
                <div style={{ marginTop: 4 }}><span className={`diff-badge diff-${step.severity === "critical" || step.severity === "high" ? "expert" : step.severity === "medium" ? "hard" : "easy"}`}>{step.severity}</span></div>
              </div>
              {i < ap.length - 1 && <div style={{ width: 24, height: 2, background: step.result === "blocked" ? "var(--gc-muted)" : "var(--gc-accent)", flexShrink: 0 }} />}
            </div>
          ))}
        </div>
      </div>}

      {pa.length > 0 && <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><div className="card-title"><i className="fa fa-server" /> Per-Asset Risk Assessment</div><span className="muted" style={{ fontSize: 12 }}>{pa.length} assets · sorted by risk</span></div>
        <div style={{ overflowX: "auto" }}>
          <table className="score-table"><thead><tr><th>Asset</th><th>Zone</th><th>Crit</th><th>Initial</th><th>Final</th><th>Health</th><th>Targeted</th><th>Detected</th><th>Dwell</th><th>Contained</th><th>Risk</th></tr></thead>
            <tbody>{pa.map((a) => { const hb = healthBadge(a.final_health); return (
              <tr key={a.id}>
                <td style={{ fontWeight: 600, fontSize: 12.5 }}>{a.name}<div className="muted" style={{ fontSize: 11 }}>{a.type}</div></td>
                <td><span className="tag">{a.zone}</span></td>
                <td style={{ fontFamily: "var(--mono)", textAlign: "center" }}>{a.criticality}</td>
                <td><span style={{ color: stateColor(a.initial_state), fontSize: 12, fontWeight: 600 }}>{a.initial_state}</span></td>
                <td><span style={{ color: stateColor(a.final_state), fontSize: 12, fontWeight: 600 }}>{a.final_state}</span></td>
                <td><span style={{ background: hb.bg, color: hb.color, fontSize: 11, padding: "1px 6px", borderRadius: 4, fontWeight: 600 }}>{hb.label}</span></td>
                <td style={{ fontFamily: "var(--mono)", textAlign: "center" }}>{a.times_targeted || "-"}</td>
                <td style={{ fontFamily: "var(--mono)", textAlign: "center" }}>{a.times_detected || "-"}{a.detected_by.length > 0 && <div className="muted" style={{ fontSize: 10.5 }}>{a.detected_by.join(", ")}</div>}</td>
                <td style={{ fontFamily: "var(--mono)", textAlign: "center" }}>{a.avg_dwell_s > 0 ? `${Math.round(a.avg_dwell_s / 60)}m` : "-"}</td>
                <td style={{ textAlign: "center" }}>{a.contained ? <i className="fa fa-check" style={{ color: "var(--gc-teal)" }} /> : a.times_targeted > 0 ? <i className="fa fa-times" style={{ color: "var(--gc-red)" }} /> : <span className="muted">-</span>}</td>
                <td><div style={{ display: "flex", alignItems: "center", gap: 6 }}><div style={{ width: 40, height: 6, background: "var(--gc-surface)", borderRadius: 3, overflow: "hidden" }}><div style={{ width: `${a.risk_score}%`, height: "100%", background: riskColor(a.risk_score), borderRadius: 3 }} /></div><span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: riskColor(a.risk_score) }}>{a.risk_score}</span></div></td>
              </tr>); })}</tbody>
          </table>
        </div>
      </div>}

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-stream" /> Attack Timeline</div>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            {report.timeline.map((e, i) => (
              <div key={i} style={{ display: "flex", gap: 10, fontSize: 12.5, padding: "6px 0", borderBottom: "1px solid var(--gc-border)" }}>
                <span style={{ fontFamily: "var(--mono)", color: "var(--gc-muted)", minWidth: 62 }}>{e.clock}</span>
                <span className="tag" style={{ background: tagColor(e.type), minWidth: 70, textAlign: "center" }}>{e.type}</span>
                <span style={{ flex: 1 }}>{e.title}{e.asset ? <span className="muted"> ({e.asset})</span> : null}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-sitemap" /> MITRE ATTACK Mapping</div>
          <table className="score-table"><thead><tr><th>Technique</th><th>Tactic</th><th>Detected</th><th>Blocked</th></tr></thead>
            <tbody>{report.mitre_map.map((m, i) => (
              <tr key={i}>
                <td><span style={{ fontFamily: "var(--mono)", color: "var(--gc-accent)", fontSize: 12 }}>{m.technique}</span> {m.name}</td>
                <td className="muted" style={{ fontSize: 12.5 }}>{m.tactic}</td>
                <td style={{ textAlign: "center" }}>{m.detected ? <i className="fa fa-check" style={{ color: "var(--gc-green)" }} /> : <i className="fa fa-times" style={{ color: "var(--gc-red)" }} />}</td>
                <td style={{ textAlign: "center" }}>{m.blocked ? <i className="fa fa-ban" style={{ color: "var(--gc-teal)" }} /> : <span className="muted">-</span>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-shield-halved" /> Control Effectiveness</div>
          {ce.length === 0 && <div className="muted" style={{ fontSize: 12.5 }}>No controls triggered during this run.</div>}
          {ce.map((c) => (
            <div key={c.type} style={{ padding: "10px 0", borderBottom: "1px solid var(--gc-border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}><span style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</span><span style={{ fontFamily: "var(--mono)", fontSize: 12.5, color: "var(--gc-accent)" }}>{c.total_actions} actions</span></div>
              <div style={{ display: "flex", gap: 12, fontSize: 12 }}>
                {c.detections > 0 && <span><span style={{ color: "var(--gc-green)" }}>{c.detections}</span> detections</span>}
                {c.blocks > 0 && <span><span style={{ color: "var(--gc-teal)" }}>{c.blocks}</span> blocks</span>}
                {c.avg_dwell_s > 0 && <span className="muted">avg dwell {Math.round(c.avg_dwell_s / 60)}m</span>}
              </div>
              {c.techniques_detected.length > 0 && <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>Detected: {c.techniques_detected.join(", ")}</div>}
              {c.techniques_blocked.length > 0 && <div style={{ fontSize: 11, color: "var(--gc-teal)", marginTop: 2 }}>Blocked: {c.techniques_blocked.join(", ")}</div>}
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-clock" /> Dwell Time Analysis</div>
          {dw && dw.overall.count > 0 ? <>
            <div className="stats-row" style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
              <Mini label="Mean" value={`${Math.round(dw.overall.mean_s / 60)}m`} /><Mini label="Median" value={`${Math.round(dw.overall.median_s / 60)}m`} /><Mini label="Min" value={`${Math.round(dw.overall.min_s / 60)}m`} /><Mini label="Max" value={`${Math.round(dw.overall.max_s / 60)}m`} />
            </div>
            {dw.worst.asset && <div style={{ fontSize: 12.5, marginBottom: 12, padding: "8px 12px", background: "rgba(255,71,87,.06)", borderRadius: 8, border: "1px solid rgba(255,71,87,.15)" }}><span style={{ color: "var(--gc-red)", fontWeight: 600 }}>Longest dwell:</span> {dw.worst.asset} ({Math.round(dw.worst.max_dwell_s / 60)}m)</div>}
            <div className="builder-label">By Asset</div>
            {dw.by_asset.map((a) => <div key={a.asset} style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, padding: "4px 0" }}><span>{a.asset}</span><span style={{ fontFamily: "var(--mono)", color: a.mean_s > 300 ? "var(--gc-red)" : "var(--gc-green)" }}>{Math.round(a.mean_s / 60)}m ({a.count}x)</span></div>)}
          </> : <div className="muted" style={{ fontSize: 12.5 }}>No detections recorded, no dwell time data available.</div>}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-network-wired" /> Zone Breach Analysis</div>
          {za.map((z) => (
            <div key={z.zone} style={{ padding: "10px 0", borderBottom: "1px solid var(--gc-border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: zoneColor(z.status), flexShrink: 0 }} /><span style={{ fontWeight: 600, fontSize: 13, textTransform: "uppercase", letterSpacing: 0.5 }}>{z.zone}</span></div>
                <span className={`diff-badge diff-${z.status === "breached" ? "expert" : z.status === "contained" ? "hard" : "easy"}`}>{z.status}</span>
              </div>
              <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--gc-muted)" }}>
                <span>{z.assets_total} assets</span>
                {z.assets_compromised > 0 && <span style={{ color: "var(--gc-red)" }}>{z.assets_compromised} compromised</span>}
                {z.assets_contained > 0 && <span style={{ color: "var(--gc-teal)" }}>{z.assets_contained} contained</span>}
                {z.assets_down > 0 && <span style={{ color: "var(--gc-red)" }}>{z.assets_down} down</span>}
                {z.assets_safe > 0 && <span style={{ color: "var(--gc-green)" }}>{z.assets_safe} safe</span>}
              </div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>{z.asset_names.join(", ")}</div>
              {z.breach_pct > 0 && <div className="progress-bar" style={{ marginTop: 6, height: 4 }}><div style={{ width: `${z.breach_pct}%`, height: "100%", background: "var(--gc-red)", borderRadius: 2 }} /></div>}
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}><i className="fa fa-key" /> Credential Escalation</div>
          {ct.length === 0 ? <div className="muted" style={{ fontSize: 12.5 }}>No credential escalation occurred during this run.</div> : (
            <div style={{ position: "relative", paddingLeft: 24 }}>
              <div style={{ position: "absolute", left: 9, top: 0, bottom: 0, width: 2, background: "var(--gc-border)" }} />
              {ct.map((c, i) => (
                <div key={i} style={{ position: "relative", marginBottom: 20, paddingLeft: 16 }}>
                  <div style={{ position: "absolute", left: -16, top: 4, width: 14, height: 14, borderRadius: "50%", background: credColor[c.scope] || "var(--gc-muted)", border: "2px solid var(--gc-card)" }} />
                  <div style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--gc-muted)" }}>{c.clock}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: credColor[c.scope] || "var(--gc-text)", marginTop: 2, textTransform: "uppercase", letterSpacing: 0.5 }}>{c.scope.replace("_", " ")}</div>
                  <div style={{ fontSize: 12.5, marginTop: 2 }}>{c.description}</div>
                  <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 2 }}>{c.technique} · {c.target}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ============ PERSISTENCE vs ERADICATION ============ */}
      {(report as any).persistence_report && (report as any).persistence_report.total_planted > 0 && (() => {
        const pr = (report as any).persistence_report;
        return (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <div className="card-title"><i className="fa fa-bug" /> Persistence vs Eradication (IRP ch.04)</div>
              <span style={{ fontFamily: "var(--mono)", fontSize: 12.5, fontWeight: 700, color: pr.eradication_complete ? "var(--gc-green)" : "var(--gc-red)" }}>
                {pr.total_eradicated}/{pr.total_planted} eradicated {pr.eradication_complete ? "(complete)" : "(INCOMPLETE)"}
              </span>
            </div>
            <table className="score-table">
              <thead><tr><th>Type</th><th>Asset</th><th>Time</th><th>Status</th></tr></thead>
              <tbody>
                {pr.items.map((item: any, i: number) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, fontSize: 12.5 }}>{item.label}</td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{item.asset || "-"}</td>
                    <td style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{item.clock}</td>
                    <td style={{ textAlign: "center" }}>
                      {item.eradicated
                        ? <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "rgba(0,230,118,.12)", color: "var(--gc-green)", fontWeight: 600 }}>ERADICATED</span>
                        : <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "rgba(255,71,87,.12)", color: "var(--gc-red)", fontWeight: 600 }}>SURVIVING</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      {/* ============ LIVE-FIRE VALIDATION ============ */}
      {(report as any).live_fire_validation && (() => {
        const lf = (report as any).live_fire_validation;
        return (
          <div className="card" style={{ marginBottom: 20, border: "1px solid rgba(0,212,255,.2)" }}>
            <div className="card-header">
              <div className="card-title"><i className="fa fa-crosshairs" /> Live-Fire Validation — Model vs Actual</div>
              <span style={{ fontFamily: "var(--mono)", fontSize: 12.5, fontWeight: 700, color: "var(--gc-accent)" }}>
                {lf.total_real_executed} attacks executed on real infrastructure
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Model Detection", value: `${lf.model_detection_rate}%`, color: "var(--gc-blue)" },
                { label: "Real Detection", value: `${lf.real_detection_rate}%`, color: lf.real_detection_rate >= lf.model_detection_rate ? "var(--gc-green)" : "var(--gc-red)" },
                { label: "Delta", value: `${lf.detection_delta_pct > 0 ? "+" : ""}${lf.detection_delta_pct}%`, color: Math.abs(lf.detection_delta_pct) < 10 ? "var(--gc-green)" : "var(--gc-yellow)" },
                { label: "Lab", value: lf.lab_backend, color: "var(--gc-muted)" },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 800, fontFamily: "var(--mono)", color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: "var(--gc-muted)", marginTop: 4 }}>{s.label}</div>
                </div>
              ))}
            </div>
            <table className="score-table">
              <thead><tr><th>Technique</th><th>Target</th><th>Model</th><th>Real</th><th>Tool</th><th>Detection</th></tr></thead>
              <tbody>
                {(lf.results || []).filter((r: any) => r.real_executed).map((r: any, i: number) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, fontSize: 12.5 }}>{r.technique}<br/><span style={{ fontSize: 11, color: "var(--gc-muted)" }}>{r.mitre_id}</span></td>
                    <td className="muted" style={{ fontSize: 12.5 }}>{r.target}</td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: r.model_detected ? "rgba(0,230,118,.12)" : "rgba(255,71,87,.12)", color: r.model_detected ? "var(--gc-green)" : "var(--gc-red)", fontWeight: 600 }}>
                        {r.model_detected ? `DETECTED ${r.model_detect_time_s}s` : "MISSED"}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      {r.real_success
                        ? <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(0,230,118,.12)", color: "var(--gc-green)", fontWeight: 600 }}>SUCCESS</span>
                        : <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(255,71,87,.12)", color: "var(--gc-red)", fontWeight: 600 }}>FAILED</span>
                      }
                    </td>
                    <td style={{ fontFamily: "var(--mono)", fontSize: 12 }}>{r.tool}</td>
                    <td style={{ textAlign: "center" }}>
                      {r.real_detected
                        ? <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(0,230,118,.12)", color: "var(--gc-green)", fontWeight: 600 }}>DETECTED</span>
                        : <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: "rgba(255,71,87,.12)", color: "var(--gc-red)", fontWeight: 600 }}>MISSED</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-gavel" /> Regulatory Impact</div>
          {report.regulatory_impact.map((r, i) => (
            <div key={i} className="alert-item warning" style={{ fontSize: 12.5, display: "flex", gap: 8, alignItems: "flex-start" }}>
              <i className="fa fa-balance-scale" style={{ color: r.on_time ? "var(--gc-green)" : "var(--gc-yellow)", marginRight: 4, marginTop: 2 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{r.framework_name}{r.deadline_hours > 0 ? ` (${r.deadline_hours >= 24 ? `${Math.round(r.deadline_hours / 24)}d` : `${r.deadline_hours}h`})` : ""}</div>
                <div style={{ fontSize: 12, color: "var(--gc-muted)", marginTop: 2 }}>{r.message}</div>
                {r.penalty && <div style={{ fontSize: 11, color: "var(--gc-red)", marginTop: 2 }}>{r.penalty}</div>}
              </div>
              {r.on_time !== undefined && <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: r.on_time ? "rgba(0,230,118,.12)" : "rgba(255,71,87,.12)", color: r.on_time ? "var(--gc-green)" : "var(--gc-red)", whiteSpace: "nowrap" }}>{r.on_time ? "ON TIME" : "LATE"}</span>}
            </div>
          ))}
          <div className="card-title" style={{ margin: "16px 0 8px" }}><i className="fa fa-coins" /> Financial Impact Drivers</div>
          {fin.drivers.map((d, i) => <div key={i} className="muted" style={{ fontSize: 12.5, padding: "3px 0" }}>- {d}</div>)}
          {(fin.estimate_low_usd + fin.estimate_high_usd > 0) && <div style={{ marginTop: 12, padding: "10px 14px", background: "rgba(255,71,87,.06)", borderRadius: 8, border: "1px solid rgba(255,71,87,.15)", fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700, color: "var(--gc-red)" }}>${(fin.estimate_low_usd / 1e6).toFixed(1)}M - ${(fin.estimate_high_usd / 1e6).toFixed(1)}M estimated</div>}
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-gauge-high" /> Security Maturity</div>
          <div style={{ textAlign: "center", padding: "14px 0" }}>
            <div style={{ fontSize: 48, fontWeight: 700, fontFamily: "var(--mono)", color: report.maturity_score.score >= 70 ? "var(--gc-green)" : report.maturity_score.score >= 40 ? "var(--gc-yellow)" : "var(--gc-red)" }}>{report.maturity_score.score}</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--gc-accent2)", marginTop: 4 }}>{report.maturity_score.band}</div>
          </div>
          {mb && <div style={{ marginTop: 12 }}>{Object.entries(mb).map(([label, value]) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12.5, padding: "5px 0" }}>
              <span>{label}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 60, height: 5, background: "var(--gc-surface)", borderRadius: 3, overflow: "hidden" }}><div style={{ width: `${Math.min(100, Math.max(0, (value / 30) * 100))}%`, height: "100%", borderRadius: 3, background: value < 0 ? "var(--gc-red)" : value > 15 ? "var(--gc-green)" : "var(--gc-yellow)" }} /></div>
                <span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600, color: value < 0 ? "var(--gc-red)" : "var(--gc-green)", minWidth: 30, textAlign: "right" }}>{value > 0 ? "+" : ""}{value}</span>
              </div>
            </div>
          ))}</div>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-list-check" /> Corrective Action Plan</div>
        {report.corrective_actions.map((a, i) => (
          <div key={i} className="alert-item info" style={{ fontSize: 12.5 }}>
            <span className="tag" style={{ background: a.priority === "P1" ? "rgba(255,71,87,.2)" : a.priority === "P2" ? "rgba(255,214,0,.2)" : "rgba(77,208,225,.2)", color: a.priority === "P1" ? "var(--gc-red)" : a.priority === "P2" ? "var(--gc-yellow)" : "var(--gc-teal)", marginRight: 8, fontWeight: 700, flexShrink: 0 }}>{a.priority}</span>
            {a.action}
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-chart-bar" /> Detailed Scorecard</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          <Mini label="Attacker Actions" value={sc.attacker_actions} /><Mini label="Succeeded" value={sc.succeeded} /><Mini label="Blocked" value={sc.blocked} /><Mini label="Failed" value={sc.failed} />
          <Mini label="Detected" value={sc.detected} /><Mini label="Contained" value={sc.contained} /><Mini label="Prevention Rate" value={`${Math.round(sc.prevention_rate * 100)}%`} /><Mini label="Containment Rate" value={`${Math.round(sc.containment_rate * 100)}%`} />
          <Mini label="Red Objectives" value={`${sc.red_objectives_met}/${sc.red_objectives_total}`} /><Mini label="Blue Objectives" value={`${sc.blue_objectives_met}/${sc.blue_objectives_total}`} /><Mini label="First Detection" value={`${sc.time_to_first_detection_min}m`} /><Mini label="FP Rate" value={`${Math.round(sc.fp_rate * 100)}%`} />
        </div>
      </div>
    </>
  );
}

function Stat({ cls, label, value, sub }: { cls: string; label: string; value: string | number; sub: string }) {
  return <div className={`stat-card ${cls}`}><div className="stat-label">{label}</div><div className="stat-value" style={{ fontSize: 20 }}>{value}</div><div className="stat-sub">{sub}</div></div>;
}
function Mini({ label, value }: { label: string; value: string | number }) {
  return <div style={{ background: "var(--gc-surface)", borderRadius: 8, padding: "10px 12px", textAlign: "center" }}><div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 1.5, color: "var(--gc-muted)", marginBottom: 4 }}>{label}</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: "var(--mono)" }}>{value}</div></div>;
}
