import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Wordmark } from "../components/Logo";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      await login(email.trim(), password);
      nav("/", { replace: true });
    } catch {
      setErr("Invalid email or password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <img src="/logo-goalcert.png" alt="" className="login-bg-logo" />
      <div className="login-form-side">
        <form className="login-card" onSubmit={submit}>
          <div className="brand"><Wordmark size={28} /></div>
          <h1>Welcome back</h1>
          <div className="sub">Sign in to access your simulation environment.</div>

          <label>Email</label>
          <input className="form-input" type="email" autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" required />

          <label>Password</label>
          <input className="form-input" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" required />

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, fontSize: 12.5 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 7, margin: 0, color: "var(--gc-text2)", cursor: "pointer", textTransform: "none", fontWeight: 500, letterSpacing: 0 }}>
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember me
            </label>
            <span style={{ color: "var(--gc-primary)", cursor: "pointer", fontWeight: 500 }}>Forgot password?</span>
          </div>

          {err && <div className="login-err"><i className="fa fa-circle-exclamation" /> {err}</div>}

          <button className="btn btn-primary" type="submit" disabled={busy}
            style={{ width: "100%", marginTop: 22, justifyContent: "center", padding: "13px", fontSize: 14, fontWeight: 600 }}>
            {busy ? <><span className="spinner" style={{ borderTopColor: "#fff" }} /> Signing in…</> : <>Sign In</>}
          </button>
        </form>
      </div>

    </div>
  );
}
