"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { signUp } from "@/lib/auth";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { Eye, EyeOff } from "lucide-react";

export default function Signup() {
  const router = useRouter();
  const [name, setName]         = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [success, setSuccess]   = useState("");

  const handleSignup = async (e) => {
    e.preventDefault();
    setLoading(true); setError(""); setSuccess("");
    try {
      const { message } = await signUp({ email, password, fullName: name });
      setSuccess(message || "Account created! Check your email to verify.");
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      setError(err.message || "Signup failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { label: "Full Name",  type: "text",     placeholder: "Ada Lovelace",     val: name,     set: setName },
    { label: "Email",      type: "email",    placeholder: "you@company.com",  val: email,    set: setEmail },
    { label: "Password",   type: "password", placeholder: "Min. 8 characters",val: password, set: setPassword },
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--c-bg)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      position: "relative",
      overflow: "hidden",
    }}>
      <Navbar />

      {/* Ambient background enhancements */}
      <div aria-hidden style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}>
        <div className="orb" style={{
          width: 800, height: 800,
          background: "radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%)",
          top: "-20%", left: "-10%",
        }} />
        <div className="orb" style={{
          width: 600, height: 600,
          background: "radial-gradient(circle, rgba(180,100,10,0.04) 0%, transparent 70%)",
          bottom: "-10%", right: "-5%",
          animationDelay: "5s",
        }} />
        <div className="grain" style={{ position: "absolute", inset: 0, opacity: 0.2 }} />
      </div>

      <div style={{ width: "100%", maxWidth: 460, position: "relative", zIndex: 1, marginTop: 40 }}>
        
        {/* Brand Header */}
        <div className="fade-up" style={{ textAlign: "center", marginBottom: 32 }}>
          <h1 className="text-display" style={{ fontSize: 32, fontWeight: 700, color: "var(--c-text)", marginBottom: 8, letterSpacing: "-0.02em" }}>
            Create an account
          </h1>
          <p style={{ color: "var(--c-text-muted)", fontSize: 13.5, fontWeight: 400 }}>
            Join 2,000+ professionals using DocsChat
          </p>
        </div>

        {/* Signup Card */}
        <div className="fade-up fade-up-1 auth-card">
          {/* Subtle top light */}

          {/* Subtle top light */}
          <div style={{ position: "absolute", top: 0, left: "10%", right: "10%", height: 1, background: "linear-gradient(90deg, transparent, rgba(59,130,246,0.3), transparent)" }} />

          {error && (
            <div className="fade-up" style={{
              background: "rgba(255, 80, 60, 0.08)",
              border: "1px solid rgba(255, 80, 60, 0.2)",
              borderRadius: 12,
              padding: "12px 16px",
              marginBottom: 24,
              fontSize: 13.5,
              color: "var(--c-error)",
              display: "flex", alignItems: "center", gap: 10,
              fontFamily: "var(--font-body)"
            }}>
              <span>⚠</span> {error}
            </div>
          )}

          {success && (
            <div className="fade-up" style={{
              background: "rgba(94, 201, 149, 0.08)",
              border: "1px solid rgba(94, 201, 149, 0.2)",
              borderRadius: 12,
              padding: "12px 16px",
              marginBottom: 24,
              fontSize: 13.5,
              color: "#5EC995",
              display: "flex", alignItems: "center", gap: 10,
              fontFamily: "var(--font-body)"
            }}>
              <span>✓</span> {success}
            </div>
          )}

          <form onSubmit={handleSignup} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {fields.map(({ label, type, placeholder, val, set }, i) => (
              <div key={label} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={{ fontSize: 11, color: "var(--c-text-faint)", letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {label}
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    className="input"
                    type={label === "Password" ? (showPassword ? "text" : "password") : type}
                    placeholder={placeholder}
                    required
                    value={val}
                    onChange={e => set(e.target.value)}
                    style={{ height: 48, fontSize: 14.5, paddingRight: label === "Password" ? 48 : 16 }}
                  />
                  {label === "Password" && (
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{
                        position: "absolute",
                        right: 12,
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        color: "var(--c-text-faint)",
                        cursor: "pointer",
                        padding: 4,
                        display: "flex", alignItems: "center", justifyContent: "center"
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = "var(--c-text-muted)"}
                      onMouseLeave={e => e.currentTarget.style.color = "var(--c-text-faint)"}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  )}
                </div>
              </div>
            ))}

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
              style={{
                marginTop: 8, height: 48, fontSize: 15, fontWeight: 600,
                opacity: loading ? 0.6 : 1, transition: "all 0.2s"
              }}
            >
              {loading ? "Creating account..." : "Start for free →"}
            </button>
          </form>

          {/* Social Logins */}
          <div style={{ margin: "32px 0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
              <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
              <span style={{ fontSize: 11, color: "var(--c-text-faint)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Sign up with</span>
              <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
            </div>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <button className="btn btn-ghost" style={{ fontSize: 13, height: 44, padding: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                Google
              </button>
              <button className="btn btn-ghost" style={{ fontSize: 13, height: 44, padding: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>
                GitHub
              </button>
            </div>
          </div>

          <p style={{ textAlign: "center", fontSize: 13.5, color: "var(--c-text-faint)" }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "var(--c-accent)", textDecoration: "none", fontWeight: 600 }}>Log in</Link>
          </p>
        </div>

        {/* Support links */}
        <div className="fade-up fade-up-2" style={{ display: "flex", justifyContent: "center", gap: 32, marginTop: 40, opacity: 0.5 }}>
          {["Privacy Policy", "Terms of Service", "Help Center"].map(l => (
            <Link key={l} href="#" style={{ fontSize: 11, color: "var(--c-text)", textDecoration: "none", textTransform: "uppercase", letterSpacing: "0.05em", fontFamily: "var(--font-mono)" }}>{l}</Link>
          ))}
        </div>
      </div>
    </div>
  );
}
