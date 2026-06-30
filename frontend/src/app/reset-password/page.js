"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import Navbar from "@/components/Navbar";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ message: "", error: "" });

  useEffect(() => {
    setToken(searchParams.get("token") || "");
    setEmail(searchParams.get("email") || "");
  }, [searchParams]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setStatus({ message: "", error: "Passwords do not match" });
      return;
    }

    setLoading(true);
    setStatus({ message: "", error: "" });
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, token, password }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus({ message: "Password reset successful! Redirecting to login...", error: "" });
        setTimeout(() => router.push("/login"), 3000);
      } else {
        setStatus({ message: "", error: data.detail || "Reset failed" });
      }
    } catch (err) {
      setStatus({ message: "", error: "Connection error" });
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "var(--c-text)" }}>
        <h2 style={{ color: "#ff6060" }}>Invalid Reset Link</h2>
        <p>Please request a new password reset link from the login page.</p>
      </div>
    );
  }

  return (
    <div style={{ width: "100%", maxWidth: 400 }}>
      <div className="auth-card" style={{ padding: 32 }}>
        <h2 style={{ fontSize: 24, fontWeight: 700, color: "var(--c-text)", marginBottom: 8 }}>Set New Password</h2>
        <p style={{ fontSize: 14, color: "var(--c-text-muted)", marginBottom: 24 }}>
          Enter a new secure password for <b>{email}</b>
        </p>

        {status.message && (
          <div style={{ background: "rgba(0,200,100,0.1)", border: "1px solid rgba(0,200,100,0.2)", borderRadius: 12, padding: 12, color: "#4ade80", fontSize: 13, marginBottom: 20 }}>
            {status.message}
          </div>
        )}
        {status.error && (
          <div style={{ background: "rgba(255,80,60,0.1)", border: "1px solid rgba(255,80,60,0.2)", borderRadius: 12, padding: 12, color: "#ff6060", fontSize: 13, marginBottom: 20 }}>
            {status.error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ fontSize: 11, color: "var(--c-text-faint)", letterSpacing: "0.05em", textTransform: "uppercase", fontWeight: 700 }}>
              New Password
            </label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              required
              minLength={6}
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{ height: 48 }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label style={{ fontSize: 11, color: "var(--c-text-faint)", letterSpacing: "0.05em", textTransform: "uppercase", fontWeight: 700 }}>
              Confirm Password
            </label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              required
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              style={{ height: 48 }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ marginTop: 8, height: 48, fontSize: 15, fontWeight: 600 }}
          >
            {loading ? "Updating..." : "Reset Password"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function ResetPassword() {
  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--c-bg)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
    }}>
      <Navbar />
      <Suspense fallback={<div style={{ color: "var(--c-text)" }}>Loading...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
