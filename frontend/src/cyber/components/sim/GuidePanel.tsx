/**
 * GuidePanel — persistent side rail that teaches the student through each phase.
 * Shows: phase context, role-specific perspective, next step hint, teaching notes.
 */
import { useState } from "react";
import { getPhase, getStory } from "./StoryData";
import { TEAM_META } from "./shared";

interface Props {
  sim: any;
  myRole: string;
  scenarioId: string;
  onHighlightNode?: (hostId: string | null) => void;
}

export default function GuidePanel({ sim, myRole, scenarioId, onHighlightNode }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const guide = sim?.guide;
  const story = getStory(scenarioId);
  const phase = guide ? getPhase(scenarioId, guide.phase) : null;
  const nextTool = guide?.next_tools?.[myRole];
  const meta = TEAM_META[myRole] || TEAM_META.red;

  if (collapsed) {
    return (
      <div style={{ width: 36, background: "#fff", borderRight: "1px solid var(--gc-border)",
        display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 12, cursor: "pointer" }}
        onClick={() => setCollapsed(false)}>
        <i className="fa fa-book" style={{ color: "var(--gc-primary)", fontSize: 14 }} />
        <div style={{ writingMode: "vertical-rl", fontSize: 10, color: "var(--gc-muted)", marginTop: 8, letterSpacing: 1 }}>GUIDE</div>
      </div>
    );
  }

  return (
    <div style={{ width: 280, background: "#fff", borderRight: "1px solid var(--gc-border)",
      overflowY: "auto", display: "flex", flexDirection: "column", gap: 0, flexShrink: 0 }}>

      {/* Header */}
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gc-border)",
        display: "flex", alignItems: "center", gap: 8 }}>
        <i className="fa fa-book" style={{ color: "var(--gc-accent)", fontSize: 13 }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--gc-accent)", letterSpacing: 1 }}>SCENARIO GUIDE</span>
        <button onClick={() => setCollapsed(true)} style={{ marginLeft: "auto", background: "none", border: "none",
          color: "var(--gc-muted)", cursor: "pointer", fontSize: 12 }}>
          <i className="fa fa-chevron-left" />
        </button>
      </div>

      {/* Phase progress dots */}
      {guide && (
        <div style={{ padding: "8px 12px", display: "flex", gap: 3, borderBottom: "1px solid var(--gc-border)" }}>
          {(guide.phases as string[]).map((p: string, i: number) => (
            <div key={p} title={p} style={{ flex: 1, height: 4, borderRadius: 2,
              background: i < guide.phase_index ? "var(--gc-green)" : i === guide.phase_index ? "var(--gc-accent)" : "#e8e3f4",
              transition: "background 0.5s" }} />
          ))}
        </div>
      )}

      {/* Current phase */}
      {phase && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gc-border)" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--gc-accent)", letterSpacing: 1, marginBottom: 4 }}>{phase.name}</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--gc-text)", marginBottom: 6 }}>{phase.subtitle}</div>
          <div style={{ fontSize: 11.5, color: "var(--gc-body)", lineHeight: 1.6 }}>{phase.briefing}</div>
        </div>
      )}

      {/* Role-specific perspective */}
      {phase && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gc-border)",
          borderLeft: `3px solid ${meta.color}` }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: meta.color, letterSpacing: 1, marginBottom: 4 }}>
            <i className={`fa ${meta.icon}`} style={{ marginRight: 4 }} />
            {myRole.toUpperCase()} PERSPECTIVE
          </div>
          <div style={{ fontSize: 11.5, color: "var(--gc-body)", lineHeight: 1.6 }}>
            {myRole === "red" ? phase.red : myRole === "soc" ? phase.soc : phase.blue}
          </div>
        </div>
      )}

      {/* Next step */}
      {nextTool && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gc-border)",
          background: "rgba(73,2,162,0.05)" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#22d3ee", letterSpacing: 1, marginBottom: 4 }}>
            <i className="fa fa-arrow-right" style={{ marginRight: 4 }} /> NEXT STEP
          </div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--gc-text)", marginBottom: 4 }}>{nextTool.name}</div>
          <div style={{ fontSize: 11, color: "var(--gc-body)", lineHeight: 1.5 }}>
            {nextTool.guide_text || nextTool.summary}
          </div>
        </div>
      )}

      {/* Progress */}
      {guide?.progress && (
        <div style={{ padding: "10px 12px", marginTop: "auto" }}>
          <div style={{ fontSize: 10, color: "var(--gc-muted)", marginBottom: 4 }}>
            Progress: {guide.progress.done}/{guide.progress.total} tools used
          </div>
          <div style={{ height: 4, borderRadius: 2, background: "var(--gc-border)" }}>
            <div style={{ height: "100%", borderRadius: 2, width: `${guide.progress.total > 0 ? (guide.progress.done / guide.progress.total) * 100 : 0}%`,
              background: "var(--gc-accent)", transition: "width 0.5s" }} />
          </div>
        </div>
      )}

      {/* Scenario intro (if tick 0) */}
      {story && sim?.tick === 0 && (
        <div style={{ padding: "10px 12px", borderTop: "1px solid var(--gc-border)" }}>
          <div style={{ fontSize: 11, fontStyle: "italic", color: "var(--gc-body)", lineHeight: 1.6 }}>
            "{story.intro}"
          </div>
        </div>
      )}
    </div>
  );
}
