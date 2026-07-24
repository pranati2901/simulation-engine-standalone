import { useCallback, useEffect, useRef, useState } from "react";
import type { LiveSnapshot } from "../api/types";

export interface LiveState {
  connected: boolean;
  snapshot: LiveSnapshot | null;
  error: string | null;
}

function wsUrl(sessionId: string, playerId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/live/${sessionId}?player_id=${encodeURIComponent(playerId)}`;
}

export function useLiveSocket(sessionId: string | null, playerId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<LiveState>({ connected: false, snapshot: null, error: null });

  useEffect(() => {
    if (!sessionId || !playerId) return;
    const ws = new WebSocket(wsUrl(sessionId, playerId));
    wsRef.current = ws;
    ws.onopen = () => setState((s) => ({ ...s, connected: true }));
    ws.onclose = () => setState((s) => ({ ...s, connected: false }));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot") setState((s) => ({ ...s, snapshot: msg as LiveSnapshot, error: null }));
      else if (msg.type === "error") setState((s) => ({ ...s, error: msg.message }));
    };
    return () => ws.close();
  }, [sessionId, playerId]);

  const send = useCallback((m: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(m));
  }, []);

  return {
    state,
    clearError: () => setState((s) => ({ ...s, error: null })),
    claimRole: (role: string) => send({ action: "claim_role", role }),
    setProfile: (profile: string) => send({ action: "set_profile", profile }),
    setMission: (mission: string) => send({ action: "set_mission", mission }),
    start: (profile: string, mission: string) => send({ action: "start", profile, mission }),
    redAction: (action_id: string, target_id?: string | null) =>
      send({ action: "red_action", action_id, target_id: target_id ?? null }),
    blueAction: (action_id: string, target_id?: string | null) =>
      send({ action: "blue_action", action_id, target_id: target_id ?? null }),
    socAction: (action_id: string, target_id?: string | null) =>
      send({ action: "soc_action", action_id, target_id: target_id ?? null }),
    setAuto: (role: string, value: boolean | null) => send({ action: "set_auto", role, value }),
    setLiveFire: (value: boolean) => send({ action: "set_live_fire", value }),
    guidedTask: (task_id: string) => send({ action: "guided_task", task_id }),
    runTool: (tool_id: string, params?: Record<string, string>) =>
      send({ action: "run_tool", tool_id, params: params ?? {} }),
    setSimAuto: (value: boolean) => send({ action: "set_sim_auto", value }),
    conclude: () => send({ action: "conclude" }),
    chat: (text: string) => send({ action: "chat", text }),
  };
}
