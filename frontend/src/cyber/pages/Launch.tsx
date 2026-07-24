import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AssetSpec, AssetType, ControlSpec, ControlType, RoleInfo, Topology, WorkflowDef } from "../api/types";

const DIFFS = ["Easy", "Medium", "Hard", "Expert"] as const;
const ROLE_ICON: Record<string, string> = {
  red: "fa-crosshairs", soc: "fa-eye", blue: "fa-shield-alt", mgmt: "fa-briefcase", ot: "fa-industry",
};
const ROLE_ACCENT: Record<string, string> = {
  red: "var(--gc-red)", soc: "var(--gc-green)", blue: "#5B8CFF", mgmt: "var(--gc-accent2)", ot: "var(--gc-orange)",
};
const WF_TEAMS = ["red", "soc", "blue", "mgmt", "ot"] as const;

export default function Launch() {
  const { scenarioId } = useParams();
  const nav = useNavigate();

  const { data: scenario } = useQuery({ queryKey: ["scenario", scenarioId], queryFn: () => api.scenario(scenarioId!) });
  const { data: topology } = useQuery<Topology>({ queryKey: ["topology", scenarioId], queryFn: () => api.topology(scenarioId!) });
  const { data: assetCatalog } = useQuery<AssetType[]>({ queryKey: ["assets"], queryFn: api.assets });
  const { data: controlCatalog } = useQuery<ControlType[]>({ queryKey: ["controls"], queryFn: api.controls });
  const { data: roles } = useQuery<RoleInfo[]>({ queryKey: ["roles"], queryFn: api.roles });
  const { data: workflowDefs } = useQuery<WorkflowDef[]>({ queryKey: ["workflows"], queryFn: api.workflows });

  const [assets, setAssets] = useState<AssetSpec[]>([]);
  const [enabledAssets, setEnabledAssets] = useState<Set<string>>(new Set());
  const [enabledControls, setEnabledControls] = useState<Set<string>>(new Set());
  const [difficulty, setDifficulty] = useState<(typeof DIFFS)[number]>("Hard");
  const [readiness, setReadiness] = useState(60);
  const [duration, setDuration] = useState(120);
  const [operator, setOperator] = useState("");
  const [addType, setAddType] = useState("");
  const [focusRole, setFocusRole] = useState("blue");
  const [phaseSel, setPhaseSel] = useState("full");
  const [enabledTasks, setEnabledTasks] = useState<Record<string, Set<string>>>({});
  const [wfTeam, setWfTeam] = useState<string>("red");
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    if (topology) {
      setAssets(topology.assets);
      setEnabledAssets(new Set(topology.assets.map((a) => a.id)));
      setEnabledControls(new Set(topology.controls.filter((c) => c.enabled).map((c) => c.type)));
    }
    if (scenario?.nominal_duration_min) setDuration(scenario.nominal_duration_min);
    if (scenario?.type && ["red", "soc", "blue", "mgmt", "ot"].includes(scenario.type)) {
      setFocusRole(scenario.type);
    }
  }, [topology, scenario]);

  useEffect(() => {
    if (workflowDefs) {
      const init: Record<string, Set<string>> = {};
      for (const wf of workflowDefs) {
        init[wf.actor] = new Set(wf.steps.filter((s) => s.default_enabled).map((s) => s.id));
      }
      setEnabledTasks(init);
    }
  }, [workflowDefs]);

  const iconFor = useMemo(() => {
    const m: Record<string, string> = {};
    for (const a of assetCatalog ?? []) m[a.key] = a.icon;
    return m;
  }, [assetCatalog]);

  if (!scenario || !topology) return <div className="center-empty"><span className="spinner" /> Loading scenario…</div>;

  const toggleAsset = (id: string) => setEnabledAssets((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleControl = (type: string) => setEnabledControls((s) => { const n = new Set(s); n.has(type) ? n.delete(type) : n.add(type); return n; });
  const toggleTask = (team: string, id: string) => setEnabledTasks((s) => {
    const next = new Set(s[team] ?? []);
    next.has(id) ? next.delete(id) : next.add(id);
    return { ...s, [team]: next };
  });

  const addAsset = () => {
    if (!addType) return;
    const at = (assetCatalog ?? []).find((a) => a.key === addType)!;
    const count = assets.filter((a) => a.type === addType).length + 1;
    const id = `${addType}-${count}`;
    const spec: AssetSpec = { id, type: addType, name: `${at.name} ${count}`, zone: at.default_zone, criticality: at.default_criticality };
    setAssets((a) => [...a, spec]);
    setEnabledAssets((s) => new Set(s).add(id));
    setAddType("");
  };

  const launch = async () => {
    setLaunching(true);
    const env: Topology = {
      assets: assets.filter((a) => enabledAssets.has(a.id)),
      controls: (controlCatalog ?? []).map((c): ControlSpec => {
        const existing = topology.controls.find((tc) => tc.type === c.key);
        return existing
          ? { ...existing, enabled: enabledControls.has(c.key) }
          : { id: `c-${c.key}`, type: c.key, enabled: enabledControls.has(c.key) };
      }),
    };
    const phases: string[] = scenario.phases ?? [];
    const phaseIdx = phases.indexOf(phaseSel);
    const phase_range: [number, number] | null =
      phaseSel === "full" || phaseIdx < 0 ? null : [phaseIdx + 1, phaseIdx + 1];
    const wfEnabled: Record<string, string[]> = {};
    for (const team of WF_TEAMS) if (enabledTasks[team]) wfEnabled[team] = [...enabledTasks[team]];
    try {
      const run = await api.launch({
        scenario_id: scenarioId!, environment_spec: env,
        config: { difficulty, readiness, duration_min: duration, focus_role: focusRole,
                  phase_range, workflow_config: { enabled: wfEnabled } },
        operator: operator || undefined,
      });
      nav(`/sim/${run.id}`);
    } catch (e) {
      alert("Launch failed: " + e);
      setLaunching(false);
    }
  };

  const zones = [...new Set(assets.filter((a) => enabledAssets.has(a.id)).map((a) => a.zone || "corp"))];

  return (
    <>
      <div className="section-header">
        <h1>Configure & Launch — {scenario.name}</h1>
        <p>{scenario.description}</p>
      </div>

      {/* FOCUS ROLE (lens) + PHASE SCOPE */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="fa fa-users" /> Focus role (lens) — every team acts; you observe one</div>
          <span className="muted" style={{ fontSize: 11 }}>switchable live & in the report</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 8 }}>
          {(roles ?? []).map((r) => {
            const on = focusRole === r.role;
            return (
              <div key={r.role} className={"asset-tile" + (on ? " on" : "")} style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}
                onClick={() => setFocusRole(r.role)} title={r.description}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="icon"><i className={`fa ${ROLE_ICON[r.role] || "fa-user"}`} /></div>
                  <span style={{ fontSize: 12, fontWeight: 700, textTransform: "capitalize" }}>{r.role}</span>
                </div>
                <div style={{ fontSize: 10, color: "var(--gc-muted)", lineHeight: 1.35 }}>{r.mission}</div>
              </div>
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 14, alignItems: "center", flexWrap: "wrap" }}>
          <div className="builder-label" style={{ margin: 0 }}>Scope</div>
          <select className="form-select" value={phaseSel} onChange={(e) => setPhaseSel(e.target.value)} style={{ maxWidth: 320 }}>
            <option value="full">Full mission ({(scenario.phases ?? []).length} phases)</option>
            {(scenario.phases ?? []).map((p: string, i: number) => (
              <option key={p} value={p}>Drill — Phase {i + 1}: {p}</option>
            ))}
          </select>
          <span className="muted" style={{ fontSize: 11 }}>Run the whole kill-chain or a single-phase focused drill.</span>
        </div>
      </div>

      <div className="grid-2">
        {/* ENVIRONMENT / ASSET SELECTION */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><i className="fa fa-network-wired" /> Environment — select assets</div>
            <span className="muted" style={{ fontSize: 11 }}>{enabledAssets.size}/{assets.length} included · {zones.length} zones</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, maxHeight: 340, overflowY: "auto" }}>
            {assets.map((a) => {
              const on = enabledAssets.has(a.id);
              return (
                <div key={a.id} className={"asset-tile" + (on ? " on" : "")} onClick={() => toggleAsset(a.id)}>
                  <div className="icon"><i className={`fa ${iconFor[a.type] || "fa-server"}`} /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.name || a.type}</div>
                    <div style={{ fontSize: 10, color: "var(--gc-muted)" }}>{a.zone} · crit {a.criticality}</div>
                  </div>
                  <i className={`fa ${on ? "fa-check-circle" : "fa-circle"}`} style={{ color: on ? "var(--gc-accent)" : "var(--gc-muted)", fontSize: 13 }} />
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <select className="form-select" value={addType} onChange={(e) => setAddType(e.target.value)} style={{ flex: 1 }}>
              <option value="">+ add asset type…</option>
              {(assetCatalog ?? []).map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
            </select>
            <button className="btn btn-ghost" onClick={addAsset} disabled={!addType}>Add</button>
          </div>
        </div>

        {/* CONTROLS + CONFIG */}
        <div>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header"><div className="card-title"><i className="fa fa-shield-alt" /> Security controls</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {(controlCatalog ?? []).map((c) => {
                const on = enabledControls.has(c.key);
                return (
                  <div key={c.key} className="toggle" onClick={() => toggleControl(c.key)}
                    title={c.description} style={{ justifyContent: "space-between", padding: "6px 4px" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}><i className={`fa ${c.icon}`} style={{ color: on ? "var(--gc-green)" : "var(--gc-muted)" }} /> {c.name}</span>
                    <span className={"toggle" + (on ? " on" : "")}><span className="track"><span className="knob" /></span></span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><div className="card-title"><i className="fa fa-sliders-h" /> Run configuration</div></div>
            <div className="builder-label">Difficulty (adversary sophistication)</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              {DIFFS.map((d) => (
                <button key={d} className={"filter-chip" + (difficulty === d ? " active" : "")} onClick={() => setDifficulty(d)}>{d}</button>
              ))}
            </div>
            <div className="builder-label">Team readiness — {readiness}</div>
            <input type="range" min={0} max={100} value={readiness} onChange={(e) => setReadiness(+e.target.value)} style={{ width: "100%", marginBottom: 14 }} />
            <div className="builder-label">Duration (minutes)</div>
            <select className="form-select" value={duration} onChange={(e) => setDuration(+e.target.value)} style={{ marginBottom: 14 }}>
              {[30, 60, 90, 120, 240].map((d) => <option key={d} value={d}>{d} minutes</option>)}
            </select>
            <div className="builder-label">Operator (optional)</div>
            <input className="form-input" value={operator} placeholder="Your name" onChange={(e) => setOperator(e.target.value)} />
          </div>
        </div>
      </div>

      {/* TEAM WORKFLOW CUSTOMISATION (IRP-based) */}
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="fa fa-list-check" /> Team workflows — customise each team's tasks</div>
          <span className="muted" style={{ fontSize: 11 }}>IRP-CYBER-001 · toggle to add/remove · effects change the outcome</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
          {WF_TEAMS.map((t) => {
            const wf = (workflowDefs ?? []).find((w) => w.actor === t);
            const on = enabledTasks[t]?.size ?? 0;
            const tot = wf?.steps.length ?? 0;
            return (
              <button key={t} className={"filter-chip" + (wfTeam === t ? " active" : "")}
                style={wfTeam === t ? { borderColor: ROLE_ACCENT[t], color: ROLE_ACCENT[t] } : {}}
                onClick={() => setWfTeam(t)}>
                <i className={`fa ${ROLE_ICON[t]}`} /> {t.toUpperCase()} <span className="muted">{on}/{tot}</span>
              </button>
            );
          })}
        </div>
        {(() => {
          const wf = (workflowDefs ?? []).find((w) => w.actor === wfTeam);
          if (!wf) return <div className="muted" style={{ fontSize: 12 }}>Loading…</div>;
          const phases: string[] = [];
          for (const s of wf.steps) if (s.phase_hint && !phases.includes(s.phase_hint)) phases.push(s.phase_hint);
          if (!phases.includes("")) phases.push("");
          return (
            <div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 10 }}>{wf.description}</div>
              {phases.map((ph) => {
                const steps = wf.steps.filter((s) => (s.phase_hint || "") === ph);
                if (steps.length === 0) return null;
                return (
                  <div key={ph || "_"} style={{ marginBottom: 12 }}>
                    {ph && <div className="builder-label" style={{ marginBottom: 6 }}>{ph}</div>}
                    {steps.map((s) => {
                      const on = enabledTasks[wfTeam]?.has(s.id) ?? false;
                      return (
                        <div key={s.id}
                          onClick={() => s.removable && toggleTask(wfTeam, s.id)}
                          title={s.description}
                          style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px",
                                   borderRadius: 8, marginBottom: 6, cursor: s.removable ? "pointer" : "default",
                                   border: "1px solid var(--gc-border)",
                                   background: on ? "rgba(0,212,255,.05)" : "var(--gc-surface)", opacity: on ? 1 : 0.55 }}>
                          <i className={`fa ${on ? "fa-check-square" : "fa-square"}`}
                            style={{ color: on ? ROLE_ACCENT[wfTeam] : "var(--gc-muted)", fontSize: 14 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12.5, fontWeight: 600 }}>
                              {s.label}
                              {!s.removable && <span className="tag" style={{ marginLeft: 8, fontSize: 9 }}>core</span>}
                            </div>
                            <div style={{ fontSize: 10.5, color: "var(--gc-muted)" }}>{s.description}</div>
                          </div>
                          <div style={{ display: "flex", gap: 4, flexShrink: 0, alignItems: "center" }}>
                            {s.effects.map((e, i) => (
                              <span key={i} className="tag" style={{ fontSize: 9, background: "rgba(123,97,255,.12)", color: "var(--gc-purple)" }}>
                                {e.kind}{e.scope && e.scope !== "all" ? `:${e.scope}` : ""}
                              </span>
                            ))}
                            {s.irp_ref && <span style={{ fontSize: 9, color: "var(--gc-muted)", fontFamily: "var(--mono)" }}>{s.irp_ref}</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 16 }}>
        <button className="btn btn-ghost" onClick={() => nav("/library")}>Cancel</button>
        <button className="btn btn-primary" onClick={launch} disabled={launching || enabledAssets.size === 0}>
          {launching ? <><span className="spinner" /> Launching…</> : <><i className="fa fa-play" /> Launch Simulation</>}
        </button>
      </div>
    </>
  );
}
