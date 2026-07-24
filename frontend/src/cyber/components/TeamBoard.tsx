import type { Workflow } from "../hooks/useSimSocket";

export const ROLE_ACCENT: Record<string, string> = {
  red: "var(--gc-red)", soc: "var(--gc-green)", blue: "#5B8CFF",
  mgmt: "var(--gc-accent2)", ot: "var(--gc-orange)",
};
export const ROLE_ICON: Record<string, string> = {
  red: "fa-crosshairs", soc: "fa-eye", blue: "fa-shield-alt", mgmt: "fa-briefcase", ot: "fa-industry",
};

const STATUS_ICON: Record<string, [string, string]> = {
  done: ["fa-check-circle", "var(--gc-green)"],
  active: ["fa-circle-notch fa-spin", "var(--gc-accent)"],
  blocked: ["fa-ban", "var(--gc-red)"],
  skipped: ["fa-minus-circle", "var(--gc-muted)"],
  pending: ["fa-circle", "var(--gc-muted)"],
};

interface Props {
  workflow: Workflow;
  statuses: Record<string, string>;
  score: number;
  focused?: boolean;
  onClick?: () => void;
}

export default function TeamBoard({ workflow, statuses, score, focused, onClick }: Props) {
  const accent = ROLE_ACCENT[workflow.actor] ?? "var(--gc-accent)";
  const done = workflow.steps.filter((s) => statuses[s.id] === "done").length;
  return (
    <div className="card" onClick={onClick}
      style={{ padding: 14, cursor: onClick ? "pointer" : "default",
               borderColor: focused ? accent : "var(--gc-border)",
               boxShadow: focused ? `0 0 0 1px ${accent}` : "none" }}>
      <div className="card-header" style={{ marginBottom: 10 }}>
        <div className="card-title" style={{ fontSize: 12 }}>
          <i className={`fa ${ROLE_ICON[workflow.actor] || "fa-user"}`} style={{ color: accent }} />
          <span style={{ textTransform: "capitalize" }}>{workflow.actor}</span>
        </div>
        <span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: accent }}>{score}</span>
      </div>
      <div style={{ fontSize: 10, color: "var(--gc-muted)", marginBottom: 8 }}>
        {done}/{workflow.steps.length} tasks · {workflow.name}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {workflow.steps.map((st) => {
          const status = statuses[st.id] ?? "pending";
          const [icon, color] = STATUS_ICON[status] ?? STATUS_ICON.pending;
          return (
            <div key={st.id} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 11.5 }} title={st.description}>
              <i className={`fa ${icon}`} style={{ color, marginTop: 2, fontSize: 11, width: 12 }} />
              <span style={{ color: status === "done" ? "var(--gc-text)" : status === "blocked" ? "var(--gc-red)" : "var(--gc-muted)",
                             textDecoration: status === "blocked" ? "line-through" : "none" }}>{st.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
