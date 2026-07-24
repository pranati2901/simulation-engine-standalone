import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { LabStatus, LabToolRegistry, LabTool } from "../api/types";

const STATUS_META: Record<string, { color: string; label: string; icon: string }> = {
  integrated: { color: "var(--gc-green)", label: "Integrated", icon: "fa-circle-check" },
  planned: { color: "var(--gc-muted)", label: "Roadmap", icon: "fa-circle-dashed" },
  provided: { color: "#c084fc", label: "Provided", icon: "fa-lock" },
};

function ToolRow({ t }: { t: LabTool }) {
  const m = STATUS_META[t.status] ?? STATUS_META.planned;
  const dim = t.status !== "integrated";
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 12, marginBottom: 7, opacity: dim ? 0.6 : 1 }}>
      <i className={`fa ${m.icon}`} style={{ color: m.color, marginTop: 2, fontSize: 11 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600 }}>{t.name} <span style={{ color: "var(--gc-muted)", fontWeight: 400 }}>· {t.function}</span></div>
        {t.note && <div style={{ fontSize: 10.5, color: "var(--gc-muted)" }}>{t.note}</div>}
      </div>
      <span className="tag" style={{ fontSize: 9, color: m.color, borderColor: m.color }}>{m.label}</span>
    </div>
  );
}

export default function LabPanel({
  isHost, liveFire, onToggleLiveFire,
}: {
  isHost: boolean;
  liveFire: boolean;
  onToggleLiveFire: (v: boolean) => void;
}) {
  const [status, setStatus] = useState<LabStatus | null>(null);
  const [tools, setTools] = useState<LabToolRegistry | null>(null);
  const [busy, setBusy] = useState(false);
  const [showTools, setShowTools] = useState(false);

  const refresh = async () => {
    try {
      const [s, t] = await Promise.all([api.labStatus(), api.labTools()]);
      setStatus(s); setTools(t);
    } catch { /* backend not reachable yet */ }
  };
  useEffect(() => { refresh(); const id = setInterval(refresh, 8000); return () => clearInterval(id); }, []);

  const control = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); } finally { await refresh(); setBusy(false); }
  };

  const labUp = status?.up ?? false;
  const ready = status?.attacker_ready ?? false;
  const dotColor = !status?.available ? "var(--gc-red)" : labUp ? (ready ? "var(--gc-green)" : "var(--gc-yellow)") : "var(--gc-muted)";
  const dotText = !status?.available ? "Docker not found"
    : labUp ? (ready ? "Range up · attacker ready" : "Range up · attacker booting…") : "Range stopped";

  return (
    <div className="card" style={{ borderColor: liveFire ? "var(--gc-red)" : undefined }}>
      <div className="card-header">
        <div className="card-title"><i className="fa fa-flask-vial" /> Live-fire range</div>
        <button className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 11 }} onClick={refresh} title="refresh"><i className="fa fa-rotate" /></button>
      </div>

      {/* Lab status line */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 8 }}>
        <span className="status-dot" style={{ background: dotColor }} />
        <span>{dotText}</span>
        <span className="tag" style={{ marginLeft: "auto", fontSize: 9 }}>{status?.backend ?? "docker"}</span>
      </div>

      {/* Live-fire arm toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderTop: "1px solid var(--gc-border)" }}>
        <i className="fa fa-bolt" style={{ color: liveFire ? "var(--gc-red)" : "var(--gc-muted)" }} />
        <div style={{ flex: 1, fontSize: 12 }}>
          <div style={{ fontWeight: 600 }}>Real tools {liveFire ? "ARMED" : "off"}</div>
          <div style={{ color: "var(--gc-muted)", fontSize: 10.5 }}>
            {liveFire ? "Mapped Red actions execute real tools against the lab." : "Red actions are simulated only."}
          </div>
        </div>
        {isHost ? (
          <button className={"filter-chip" + (liveFire ? " active" : "")} style={{ fontSize: 11 }}
            disabled={!labUp} onClick={() => onToggleLiveFire(!liveFire)}
            title={labUp ? "" : "start the range first"}>
            <i className={`fa ${liveFire ? "fa-toggle-on" : "fa-toggle-off"}`} /> {liveFire ? "Armed" : "Arm"}
          </button>
        ) : (
          <span className="tag" style={{ fontSize: 9, color: liveFire ? "var(--gc-red)" : "var(--gc-muted)" }}>{liveFire ? "ARMED" : "OFF"}</span>
        )}
      </div>

      {/* Host lab controls */}
      {isHost && status?.available && (
        <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
          <button className="btn btn-ghost" style={{ flex: 1, fontSize: 11 }} disabled={busy || labUp}
            onClick={() => control(api.labUp)}><i className="fa fa-play" /> Start range</button>
          <button className="btn btn-ghost" style={{ flex: 1, fontSize: 11 }} disabled={busy || !labUp}
            onClick={() => control(api.labDown)}><i className="fa fa-stop" /> Stop</button>
        </div>
      )}

      {/* Real Kali shell in the browser — the "type your own commands" proof */}
      {ready && status?.terminal_url && (
        <a className="btn btn-primary" style={{ width: "100%", fontSize: 11, marginBottom: 8 }}
          href={status.terminal_url} target="_blank" rel="noreferrer">
          <i className="fa fa-terminal" /> Open Kali terminal (real shell)
        </a>
      )}

      {/* Targets */}
      {status?.targets?.length ? (
        <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 8 }}>
          <span style={{ textTransform: "uppercase", letterSpacing: 1, fontSize: 10 }}>Targets</span>
          {status.targets.map((t) => (
            <div key={t.id} style={{ display: "flex", gap: 6, marginTop: 3 }}>
              <i className="fa fa-server" style={{ marginTop: 2 }} />
              <span style={{ color: "var(--gc-text)" }}>{t.name}</span>
              <span>· {t.host}</span>
              <span style={{ marginLeft: "auto" }}>{t.services.join(", ")}</span>
            </div>
          ))}
        </div>
      ) : null}

      {/* Tool registry */}
      <button className="btn btn-ghost" style={{ width: "100%", fontSize: 11 }} onClick={() => setShowTools((v) => !v)}>
        <i className={`fa ${showTools ? "fa-chevron-up" : "fa-toolbox"}`} /> {showTools ? "Hide" : "Show"} tool catalog
        {tools && <span className="tag" style={{ marginLeft: 6, fontSize: 9 }}>{tools.counts.integrated} live</span>}
      </button>
      {showTools && tools && (
        <div style={{ marginTop: 10, maxHeight: 280, overflowY: "auto", paddingRight: 4 }}>
          {(["integrated", "planned", "provided"] as const).map((st) => (
            (tools.by_status[st] ?? []).length > 0 && (
              <div key={st} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 1, color: STATUS_META[st].color, marginBottom: 6 }}>
                  {STATUS_META[st].label} ({(tools.by_status[st] ?? []).length})
                </div>
                {(tools.by_status[st] ?? []).map((t) => <ToolRow key={t.id} t={t} />)}
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}
