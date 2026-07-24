import { useCallback, useEffect, useRef, useState } from "react";
import type { AssetNode, SimEvent } from "../api/types";

export interface WorkflowStep { id: string; kind: string; label: string; description: string; phase_hint: string; scored: boolean; }
export interface Workflow { actor: string; id: string; name: string; description: string; steps: WorkflowStep[]; }
export interface RoleTask { id: string; label: string; description?: string; status: string; }

export interface SimInit {
  run_id: string;
  focus_role: string;
  scenario: { name: string; phases: string[]; objectives: { red: string[]; blue: string[] }; type: string; label: string };
  duration_s: number;
  environment: AssetNode[];
  workflows: Workflow[];
  role_tasks: Record<string, RoleTask[]>;
  scores: Record<string, number>;
  speed: number;
  total_events: number;
}
export interface SimComplete {
  scores: Record<string, number>;
  kpis: Record<string, number>;
  summary: Record<string, any>;
  objectives: { red: { text: string; met: boolean }[]; blue: { text: string; met: boolean }[] };
  final_assets: AssetNode[];
  role_tasks: Record<string, RoleTask[]>;
}

export interface SimState {
  connected: boolean;
  init?: SimInit;
  events: SimEvent[];
  simT: number;
  paused: boolean;
  speed: number;
  scores: Record<string, number>;
  assets: Record<string, AssetNode>;
  // live per-role task status: actor -> stepId -> status
  taskStatus: Record<string, Record<string, string>>;
  complete?: SimComplete;
}

const ZERO_SCORES = { red: 0, blue: 0, soc: 0, mgmt: 0, ot: 0 };

function wsUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/runs/${runId}`;
}

export function useSimSocket(runId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<SimState>({
    connected: false, events: [], simT: 0, paused: false, speed: 30,
    scores: { ...ZERO_SCORES }, assets: {}, taskStatus: {},
  });

  useEffect(() => {
    if (!runId) return;
    const ws = new WebSocket(wsUrl(runId));
    wsRef.current = ws;
    ws.onopen = () => setState((s) => ({ ...s, connected: true }));
    ws.onclose = () => setState((s) => ({ ...s, connected: false }));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "init") {
        const assets: Record<string, AssetNode> = {};
        for (const a of (msg.environment ?? []) as AssetNode[]) assets[a.id] = { ...a };
        const taskStatus: Record<string, Record<string, string>> = {};
        for (const [actor, tasks] of Object.entries((msg.role_tasks ?? {}) as Record<string, RoleTask[]>)) {
          taskStatus[actor] = {};
          for (const t of tasks) taskStatus[actor][t.id] = t.status;
        }
        setState((s) => ({
          ...s, init: msg, speed: msg.speed, assets, taskStatus,
          scores: { ...ZERO_SCORES, ...(msg.scores ?? {}) }, events: [], complete: undefined, simT: 0,
        }));
      } else if (msg.type === "event") {
        const e = msg.event as SimEvent;
        setState((s) => {
          const next: SimState = { ...s, events: [...s.events, e] };
          if (e.type === "score" && e.data) next.scores = { ...s.scores, ...e.data };
          if (e.type === "state" && e.asset_id && e.data) {
            const a = s.assets[e.asset_id];
            if (a) next.assets = { ...s.assets, [e.asset_id]: { ...a, security_state: e.data.security_state ?? a.security_state, health: e.data.health ?? a.health } };
          }
          if (e.type === "task" && e.data?.step_id) {
            const actor = e.side;
            next.taskStatus = { ...s.taskStatus, [actor]: { ...(s.taskStatus[actor] ?? {}), [e.data.step_id]: e.data.status } };
          }
          return next;
        });
      } else if (msg.type === "tick") {
        setState((s) => ({ ...s, simT: msg.sim_t, paused: msg.paused, speed: msg.speed }));
      } else if (msg.type === "complete") {
        setState((s) => {
          const taskStatus = { ...s.taskStatus };
          for (const [actor, tasks] of Object.entries((msg.role_tasks ?? {}) as Record<string, RoleTask[]>)) {
            taskStatus[actor] = { ...(taskStatus[actor] ?? {}) };
            for (const t of tasks) taskStatus[actor][t.id] = t.status;
          }
          return { ...s, complete: msg as SimComplete, scores: { ...s.scores, ...msg.scores }, taskStatus };
        });
      }
    };
    return () => ws.close();
  }, [runId]);

  const send = useCallback((m: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(m));
  }, []);

  return {
    state,
    pause: () => send({ action: "pause" }),
    resume: () => send({ action: "resume" }),
    setSpeed: (value: number) => send({ action: "speed", value }),
    seek: (t: number) => send({ action: "seek", t }),
    stop: () => send({ action: "stop" }),
    inject: (technique: string, target_by?: string, target_value?: string, label?: string) =>
      send({ action: "inject", technique, target_by, target_value, label }),
  };
}
