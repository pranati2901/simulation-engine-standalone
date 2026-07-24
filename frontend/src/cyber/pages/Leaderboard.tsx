import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function Leaderboard() {
  const { data } = useQuery<any[]>({ queryKey: ["leaderboard"], queryFn: api.leaderboard });
  const rows = data ?? [];
  return (
    <>
      <div className="section-header"><h1>Leaderboard</h1><p>Top runs by Blue-team score</p></div>
      <div className="card">
        {rows.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No runs yet — launch a simulation to populate the board.</div>}
        {rows.length > 0 && (
          <table className="score-table">
            <thead><tr><th>#</th><th>Operator</th><th>Scenario</th><th>Detection</th><th>Red</th><th>Blue</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.rank}>
                  <td><span className={`rank-${r.rank}`} style={{ fontFamily: "var(--mono)", fontWeight: 700 }}>{r.rank <= 3 ? ["🥇", "🥈", "🥉"][r.rank - 1] : r.rank}</span></td>
                  <td style={{ fontWeight: 600 }}>{r.operator}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{r.scenario}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{Math.round((r.detection_rate || 0) * 100)}%</td>
                  <td style={{ fontFamily: "var(--mono)", color: "var(--gc-red)" }}>{r.red}</td>
                  <td style={{ fontFamily: "var(--mono)", color: "var(--gc-green)", fontWeight: 700 }}>{r.blue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
