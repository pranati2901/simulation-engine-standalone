import { ReactNode, useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Logo } from "./Logo";

const NAV_SECTIONS: { label: string; items: { to: string; icon: string; label: string }[] }[] = [
  { label: "Main", items: [
    { to: "/", icon: "fa-table-cells-large", label: "Dashboard" },
    { to: "/live", icon: "fa-satellite-dish", label: "Live Scenarios" },
  ]},
  { label: "Library", items: [
    { to: "/library", icon: "fa-layer-group", label: "Scenario Library" },
    { to: "/catalog", icon: "fa-cubes", label: "Asset Catalog" },
    { to: "/builder", icon: "fa-wand-magic-sparkles", label: "Scenario Builder" },
  ]},
  { label: "Scenario Studio", items: [
    { to: "/studio", icon: "fa-flask-vial", label: "Studio" },
  ]},
  { label: "Insights", items: [
    { to: "/leaderboard", icon: "fa-trophy", label: "Leaderboard" },
    { to: "/reports", icon: "fa-file-lines", label: "Reports & AAR" },
  ]},
];
const ALL = NAV_SECTIONS.flatMap((s) => s.items);

function Clock() {
  const [t, setT] = useState("--:--:--");
  useEffect(() => {
    const tick = () => {
      const n = new Date();
      setT([n.getHours(), n.getMinutes(), n.getSeconds()].map((x) => String(x).padStart(2, "0")).join(":"));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <div className="topbar-clock"><i className="fa fa-clock" style={{ marginRight: 6 }} />{t}</div>;
}

function UserMenu() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const initials = (user?.name || "U").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="user-menu" onClick={() => setOpen((o) => !o)}>
        <div className="avatar-fallback">{initials}</div>
        <div style={{ lineHeight: 1.25 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.name}</div>
          <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{user?.role}</div>
        </div>
        <i className="fa fa-chevron-down" style={{ fontSize: 10, color: "var(--gc-muted)" }} />
      </div>
      {open && (
        <div className="user-pop">
          <div style={{ padding: "8px 12px 10px", borderBottom: "1px solid var(--gc-border)", marginBottom: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.name}</div>
            <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>{user?.email}</div>
          </div>
          <div className="row"><i className="fa fa-user" /> Profile</div>
          <div className="row"><i className="fa fa-gear" /> Settings</div>
          <div className="row" style={{ color: "var(--gc-red)" }} onClick={() => { logout(); nav("/login"); }}>
            <i className="fa fa-right-from-bracket" /> Sign out
          </div>
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const fullBleed = loc.pathname.startsWith("/play");   // immersive workspace manages its own layout
  const title =
    loc.pathname.startsWith("/play") ? "Live Scenario" :
    ALL.find((n) => n.to !== "/" && loc.pathname.startsWith(n.to))?.label ??
    (loc.pathname.startsWith("/sim-edu") ? "Educational Simulation" :
     loc.pathname.startsWith("/sim") ? "Active Simulation" :
     loc.pathname.startsWith("/launch") ? "Configure & Launch" : "Dashboard");

  return (
    <>
      <nav id="sidebar">
        <div className="sidebar-logo">
          <Logo size={32} />
          <div className="logo-text">Goalcert</div>
        </div>
        <div style={{ overflowY: "auto", flex: 1, paddingTop: 4 }}>
          {NAV_SECTIONS.map((sec) => (
            <div className="sidebar-section" key={sec.label}>
              <div className="sidebar-section-label">{sec.label}</div>
              {sec.items.map((n) => (
                <NavLink key={n.to} to={n.to} end={n.to === "/"}
                  className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}>
                  <i className={`fa ${n.icon}`} /> {n.label}
                </NavLink>
              ))}
            </div>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="sidebar-card">
            <div style={{ fontSize: 13, fontWeight: 600 }}><span className="status-dot" /> Engine Online</div>
            <div style={{ fontSize: 11, opacity: .85, marginTop: 4 }}>Cyber-range ready · v2.0</div>
          </div>
        </div>
      </nav>

      <div id="main">
        {/* the immersive workspace (/play) owns the whole canvas — its own slim bar replaces this one */}
        {!fullBleed && (
          <div id="topbar">
            <div className="topbar-title">{title}</div>
            <div className="topbar-right">
              <Clock />
              <NavLink to="/library" className="btn btn-primary"><i className="fa fa-plus" /> New Simulation</NavLink>
              <div className="icon-btn"><i className="fa fa-bell" /><span className="dot" /></div>
              <UserMenu />
            </div>
          </div>
        )}
        <div className={fullBleed ? "" : "page"}>{children}</div>
      </div>
    </>
  );
}
