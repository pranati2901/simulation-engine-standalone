import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { StudioDomain, StudioFault, StudioPreset, StudioScenario, StudioSpec, StudioRunSummary } from "../api/types";

export const BAND_COLOR: Record<string, string> = {
  Contained: "#22c55e", Degraded: "#f59e0b", Severe: "#f97316", Critical: "#ef4444",
};
const KINDS = [
  { key: "scenario", label: "Scenario", icon: "fa-cloud-bolt", hint: "An external situation (heat, surge, outage…)" },
  { key: "fault", label: "Fault", icon: "fa-triangle-exclamation", hint: "A degraded component / system fault" },
] as const;

export default function Studio() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [domain, setDomain] = useState("rail");
  const [kind, setKind] = useState<"scenario" | "fault">("scenario");
  const [description, setDescription] = useState("");
  const [horizon, setHorizon] = useState(120);
  const [save, setSave] = useState(true);
  const [spec, setSpec] = useState<StudioSpec | null>(null);
  const [busy, setBusy] = useState<"" | "author" | "run">("");

  const { data: domainsData } = useQuery({ queryKey: ["studio-domains"], queryFn: api.studioDomains });
  const { data: settings } = useQuery({ queryKey: ["studio-settings"], queryFn: api.studioSettings });
  const { data: presetsData } = useQuery({ queryKey: ["studio-presets", domain], queryFn: () => api.studioPresets(domain) });
  const { data: faultsData } = useQuery({ queryKey: ["studio-faults", domain], queryFn: () => api.studioFaults(domain) });
  const { data: scnData } = useQuery({ queryKey: ["studio-scenarios"], queryFn: () => api.studioScenarios() });
  const { data: runsData } = useQuery({ queryKey: ["studio-runs"], queryFn: () => api.studioRuns(12) });

  const domains: StudioDomain[] = domainsData?.domains ?? [];
  const presets: StudioPreset[] = presetsData?.presets ?? [];
  const faults: StudioFault[] = faultsData?.faults ?? [];
  const scenarios: StudioScenario[] = scnData?.scenarios ?? [];
  const runs: StudioRunSummary[] = runsData?.runs ?? [];
  const domainMeta = useMemo(() => domains.find((d) => d.id === domain), [domains, domain]);

  useEffect(() => { setSpec(null); }, [domain, kind]);

  const author = async () => {
    if (!description.trim()) return;
    setBusy("author");
    try {
      const r = await api.studioAuthor({ description, domain, kind, horizon_min: horizon, save });
      setSpec(r.spec);
      if (save) qc.invalidateQueries({ queryKey: ["studio-scenarios"] });
    } catch (e) { alert("Author failed: " + e); }
    finally { setBusy(""); }
  };

  const runSpec = async (body: { scenario_id?: string; spec?: StudioSpec }) => {
    setBusy("run");
    try {
      const r = await api.studioRun({ ...body, analyze: true });
      qc.invalidateQueries({ queryKey: ["studio-runs"] });
      nav(`/studio/run/${r.id}`);
    } catch (e) { alert("Run failed: " + e); setBusy(""); }
  };

  const del = async (s: StudioScenario) => {
    if (!confirm(`Delete "${s.name}"?`)) return;
    await api.studioDeleteScenario(s.id).catch((e) => alert(e));
    qc.invalidateQueries({ queryKey: ["studio-scenarios"] });
  };

  const train = (s: StudioSpec) => {
    const q = new URLSearchParams({ domain: s.domain, system: s.system, fault: s.fault, title: s.name });
    nav(`/studio/train?${q}`);
  };

  return (
    <>
      <div className="section-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>Scenario Studio</h1>
          <p>Describe a what-if for <b>any sector</b> — the agent authors a runnable scenario, simulates the outcome, and scores it against objective KPIs. No physics engine required.</p>
        </div>
        <AiBadge mode={settings?.ai_mode} />
      </div>

      <div className="grid-2" style={{ alignItems: "start", gap: 18 }}>
        {/* ---- Authoring panel ---- */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-wand-magic-sparkles" /> Create a scenario</div>

          <div className="builder-label">Sector / domain</div>
          <select className="form-select" value={domain} onChange={(e) => setDomain(e.target.value)} style={{ marginBottom: 12 }}>
            {domains.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>

          <div className="builder-label">Type</div>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            {KINDS.map((k) => (
              <button key={k.key} className={"filter-chip" + (kind === k.key ? " active" : "")}
                onClick={() => setKind(k.key)} title={k.hint} style={{ flex: 1 }}>
                <i className={`fa ${k.icon}`} /> {k.label}
              </button>
            ))}
          </div>

          {kind === "fault" && faults.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div className="builder-label">Fault catalogue <span className="muted" style={{ fontWeight: 400 }}>(click to seed the description)</span></div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {faults.map((f) => (
                  <button key={f.id} className="filter-chip" style={{ fontSize: 11 }}
                    onClick={() => setDescription((d) => d || `${f.label} on the ${domainMeta?.system || "system"}`)}>
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {kind === "scenario" && presets.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div className="builder-label">Preset situations</div>
              <div style={{ display: "grid", gap: 6 }}>
                {presets.map((p) => (
                  <button key={p.title} className="btn btn-ghost" style={{ justifyContent: "flex-start", textAlign: "left", fontSize: 12, padding: "7px 10px" }}
                    onClick={() => setDescription(p.description)}>
                    <b style={{ marginRight: 6 }}>{p.title}</b> <span className="muted">{p.description.slice(0, 60)}…</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="builder-label">Describe the situation</div>
          <textarea className="form-textarea" value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder={`e.g. "${presets[0]?.description ?? "A heatwave stresses the system during peak load"}"`}
            style={{ minHeight: 84, marginBottom: 12 }} />

          <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <div className="builder-label">Horizon (min)</div>
              <select className="form-select" value={horizon} onChange={(e) => setHorizon(+e.target.value)}>
                {[30, 60, 120, 240, 480, 720].map((h) => <option key={h} value={h}>{h} minutes</option>)}
              </select>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, marginTop: 18 }}>
              <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} /> Save to library
            </label>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" disabled={!description.trim() || !!busy} onClick={author} style={{ flex: 1 }}>
              {busy === "author" ? <><span className="spinner" /> Authoring…</> : <><i className="fa fa-feather" /> Author scenario</>}
            </button>
          </div>

          {spec && (
            <div className="card" style={{ marginTop: 14, borderLeft: "3px solid var(--gc-accent)", background: "rgba(73,2,162,.03)" }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{spec.name}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {domainMeta?.label} · {spec.system} · {spec.kind}{spec.fault !== "none" && <> · fault <code>{spec.fault}</code></>}
              </div>
              <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 12 }}>
                <Meter label="Severity" v={spec.severity} />
                <Meter label="Intensity" v={spec.intensity} />
                <div><span className="muted">Horizon</span><br /><b>{spec.horizon_min}m</b></div>
              </div>
              {spec.rationale && <div style={{ fontSize: 12, marginTop: 8, color: "var(--gc-body)" }}><b>Why:</b> {spec.rationale}</div>}
              {spec.expected_outcome && <div style={{ fontSize: 12, marginTop: 4, color: "var(--gc-body)" }}><b>Expected:</b> {spec.expected_outcome}</div>}
              {spec.objectives?.length > 0 && (
                <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--gc-body)" }}>
                  {spec.objectives.map((o, i) => <li key={i}>{o}</li>)}
                </ul>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="btn btn-primary" disabled={busy === "run"} onClick={() => runSpec({ spec })}>
                  {busy === "run" ? <><span className="spinner" /> Simulating…</> : <><i className="fa fa-play" /> Run simulation</>}
                </button>
                <button className="btn" onClick={() => train(spec)}><i className="fa fa-graduation-cap" /> Train</button>
              </div>
            </div>
          )}
        </div>

        {/* ---- Library + history ---- */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-layer-group" /> Scenario library <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>({scenarios.length})</span></div>
            <div style={{ display: "grid", gap: 8, maxHeight: 320, overflowY: "auto" }}>
              {scenarios.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No scenarios yet — author one on the left.</div>}
              {scenarios.map((s) => {
                const dm = domains.find((d) => d.id === s.domain);
                return (
                  <div key={s.id} style={{ border: "1px solid var(--gc-border)", borderRadius: 10, padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <i className={`fa ${dm?.icon || "fa-diagram-project"}`} style={{ color: "var(--gc-accent)" }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{s.name}</div>
                        <div className="muted" style={{ fontSize: 11 }}>{dm?.label} · {s.kind}{s.is_seed && " · sample"}</div>
                      </div>
                      <button className="btn btn-primary" style={{ fontSize: 11, padding: "4px 9px" }} onClick={() => runSpec({ scenario_id: s.id })}><i className="fa fa-play" /> Run</button>
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 8px" }} onClick={() => train(s.spec)}><i className="fa fa-graduation-cap" /></button>
                      {!s.is_seed && <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 8px", color: "var(--gc-red)" }} onClick={() => del(s)}><i className="fa fa-trash" /></button>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-clock-rotate-left" /> Recent runs</div>
            {runs.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No runs yet.</div>}
            <div style={{ display: "grid", gap: 6 }}>
              {runs.map((r) => (
                <div key={r.id} onClick={() => nav(`/studio/run/${r.id}`)}
                  style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: "1px solid var(--gc-border)", borderRadius: 8, cursor: "pointer" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: BAND_COLOR[r.outcome_band] || "#94a3b8" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.name}</div>
                    <div className="muted" style={{ fontSize: 11 }}>{r.outcome_band} · readiness {r.readiness_score} ({r.grade})</div>
                  </div>
                  <i className="fa fa-chevron-right muted" style={{ fontSize: 11 }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function Meter({ label, v }: { label: string; v: number }) {
  const c = v < 0.4 ? "#22c55e" : v < 0.7 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ flex: 1 }}>
      <span className="muted" style={{ fontSize: 11 }}>{label} {Math.round(v * 100)}%</span>
      <div style={{ height: 5, borderRadius: 3, background: "var(--gc-border)", marginTop: 3 }}>
        <div style={{ height: "100%", width: `${v * 100}%`, borderRadius: 3, background: c }} />
      </div>
    </div>
  );
}

export function AiBadge({ mode }: { mode?: string }) {
  const agent = mode === "agent";
  return (
    <span style={{ fontSize: 11.5, padding: "5px 11px", borderRadius: 999, border: "1px solid var(--gc-border)", color: "var(--gc-text2)", whiteSpace: "nowrap" }}
      title={agent ? "Claude connected via the ANTHROPIC_API_KEY environment variable on the server"
                   : "Running on deterministic local stubs — set ANTHROPIC_API_KEY on the server for full Claude reasoning"}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: agent ? "#22c55e" : "#94a3b8", display: "inline-block", marginRight: 6 }} />
      {agent ? "AI: Claude" : "AI: local stub"}
    </span>
  );
}
