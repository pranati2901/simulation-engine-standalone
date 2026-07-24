import { useState } from "react";
import { SimHost } from "./shared";

/* VICTIM — a stylized Windows desktop for any host, rendering its victim-journey stage from the
   host's sim state (normal → subtle slowdown → files .locked → ransom note + lock screen). */
const FILES = ["budget.xlsx", "payroll_Q3.xlsx", "contracts.docx", "patients.csv", "notes.txt"];

export default function VictimDesktop({ sim, initialHost }: { sim: any; initialHost?: string }) {
  const hosts: SimHost[] = sim.topology.hosts;
  const [hid, setHid] = useState(initialHost || hosts.find((h) => h.patient_zero)?.id || hosts[0]?.id);
  const host = hosts.find((h) => h.id === hid) || hosts[0];
  const st = host?.state || "healthy";
  const compromised = ["exploited", "infected", "propagating", "persistent"].includes(st) || host?.flags.includes("persistent");
  const encrypting = st === "encrypting";
  const impacted = st === "impacted";

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      {/* host picker */}
      <div style={{ width: 200, borderRight: "1px solid #1f2937", overflowY: "auto", padding: 10, flexShrink: 0 }}>
        <div style={{ fontSize: 11, textTransform: "uppercase", color: "#93a4bd", marginBottom: 8 }}>Pick a host</div>
        {hosts.map((h) => (
          <div key={h.id} onClick={() => setHid(h.id)} style={{
            fontSize: 12, padding: "5px 7px", borderRadius: 6, cursor: "pointer", marginBottom: 2,
            background: h.id === hid ? "#111a2e" : "transparent",
            color: h.state === "impacted" ? "#ef4444" : ["infected", "propagating"].includes(h.state) ? "#f59e0b" : "#cbd5e1" }}>
            <i className="fa fa-desktop" style={{ marginRight: 6, opacity: .7 }} />{h.name}
          </div>
        ))}
      </div>

      {/* the "desktop" */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden",
        background: impacted ? "#3b0a0a" : "linear-gradient(135deg,#0f3460,#16213e)" }}>
        {/* desktop icons */}
        <div style={{ padding: 24, display: "grid", gridTemplateColumns: "repeat(auto-fill,76px)", gap: 18 }}>
          {["Outlook fa-envelope", "Excel fa-file-excel", "Teams fa-users", "Chrome fa-chrome"].map((s) => {
            const [name, icon] = s.split(" ");
            return (
              <div key={name} style={{ textAlign: "center", color: "#e2e8f0", opacity: impacted ? .3 : 1 }}>
                <i className={`fa ${icon}`} style={{ fontSize: 30 }} /><div style={{ fontSize: 11, marginTop: 4 }}>{name}</div>
              </div>
            );
          })}
          {FILES.map((f) => (
            <div key={f} style={{ textAlign: "center", color: impacted ? "#fca5a5" : "#e2e8f0", opacity: impacted ? .85 : 1 }}>
              <i className={`fa ${impacted ? "fa-file-circle-xmark" : "fa-file-lines"}`} style={{ fontSize: 28 }} />
              <div style={{ fontSize: 10, marginTop: 4 }}>{impacted ? f.replace(/\.\w+$/, ".locked") : f}</div>
            </div>
          ))}
        </div>

        {/* subtle state hint */}
        {(compromised && !impacted && !encrypting) && (
          <div style={{ position: "absolute", bottom: 50, left: 16, fontSize: 11, color: "#cbd5e1", opacity: .7 }}>
            <i className="fa fa-circle-notch fa-spin" /> the machine feels a little slow… (you notice nothing wrong)
          </div>
        )}
        {encrypting && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            background: "#0008", color: "#fca5a5", fontSize: 16 }}>
            <div><i className="fa fa-lock fa-beat" /> Files are being encrypted…</div>
          </div>
        )}

        {/* ransom lock screen */}
        {impacted && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ background: "#111", border: "2px solid #ef4444", borderRadius: 10, padding: 28, maxWidth: 460, textAlign: "center" }}>
              <div style={{ color: "#ef4444", fontSize: 22, fontWeight: 800, marginBottom: 8 }}><i className="fa fa-skull" /> Ooops, your files have been encrypted!</div>
              <div style={{ color: "#fca5a5", fontSize: 13, lineHeight: 1.6 }}>
                All your important files — documents, spreadsheets, patient records — are encrypted with
                <b> W1-Worm</b>. Send 0.17 BTC to recover them. README_RESTORE.txt has been placed in every folder.
              </div>
              <div style={{ marginTop: 12, fontFamily: "ui-monospace, monospace", color: "#94a3b8", fontSize: 12 }}>
                {host.name} · time remaining: 71:59:42
              </div>
            </div>
          </div>
        )}

        {/* taskbar */}
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 34, background: "#0b1220cc",
          display: "flex", alignItems: "center", gap: 10, padding: "0 12px", fontSize: 12, color: "#cbd5e1" }}>
          <i className="fa fa-window-maximize" /> {host?.name} — Jessica Harper (Finance)
          <span style={{ marginLeft: "auto", color: impacted ? "#ef4444" : ["infected", "propagating"].includes(st) ? "#f59e0b" : "#22c55e" }}>
            ● {impacted ? "LOCKED" : compromised ? "compromised" : "normal"}
          </span>
        </div>
      </div>
    </div>
  );
}
