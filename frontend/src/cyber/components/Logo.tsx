/** GoalCert brand mark — Phi symbol with purple-blue gradient. */
export function Logo({ size = 34 }: { size?: number; color?: string }) {
  return (
    <img src="/logo-goalcert.png" alt="Goalcert" width={size} height={size}
      style={{ objectFit: "contain" }} />
  );
}

/** Mark + wordmark, used in the sidebar / login form. */
export function Wordmark({ size = 30 }: { size?: number; color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
      <Logo size={Math.round(size * 1.15)} />
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
        <span style={{ fontSize: size * 0.62, fontWeight: 700, letterSpacing: "-.3px", color: "#15101f" }}>Goalcert</span>
        <span style={{ fontSize: size * 0.26, fontWeight: 600, letterSpacing: "1.5px", color: "#8b5cf6", textTransform: "uppercase" }}>Simulation Engine</span>
      </div>
    </div>
  );
}
