"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useRef } from "react";

export default function Navbar() {
  const path = usePathname();

  // Always start with "light" — matches the default theme in layout.js.
  // Using a stable default prevents server/client hydration mismatch.
  const [themeColor, setThemeColor] = useState("emerald");
  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("app_theme_mode") || "light";
    }
    return "light";
  });
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const [mounted, setMounted] = useState(false);
  const themeMenuRef = useRef(null);

  // After mount, sync with localStorage for theme configuration
  useEffect(() => {
    setMounted(true);
    const savedColor = localStorage.getItem("app_theme_color");
    if (savedColor && ["emerald", "purple", "cyan", "blue"].includes(savedColor)) {
      setThemeColor(savedColor);
    }
    // Ensure theme mode is set in localStorage and DOM
    // Set default mode only if not already stored
    var color = localStorage.getItem('app_theme_color') || 'emerald';
    var mode = localStorage.getItem('app_theme_mode') || 'light';
    document.documentElement.setAttribute('data-theme', color);
    document.documentElement.setAttribute('data-mode', mode);
  }, []);

  // Sync theme color changes
  useEffect(() => {
    if (!mounted) return;
    localStorage.setItem("app_theme_color", themeColor);
    document.documentElement.setAttribute("data-theme", themeColor);
  }, [themeColor, mounted]);

  // Sync theme mode changes (user can still toggle, but default is light)
  useEffect(() => {
    if (!mounted) return;
    localStorage.setItem("app_theme_mode", themeMode);
    document.documentElement.setAttribute("data-mode", themeMode);
  }, [themeMode, mounted]);

  useEffect(() => {
    const handleOutsideThemeClick = (e) => {
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target)) {
        setShowThemeMenu(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideThemeClick);
    return () => document.removeEventListener("mousedown", handleOutsideThemeClick);
  }, []);

  const isDark = themeMode === "dark";

  // Stable nav background — use CSS variable driven by data-mode, avoid JS conditional
  // that causes hydration mismatch. After mount, update dynamically.
  const navBg = mounted
    ? (isDark ? "rgba(12, 11, 9, 0.82)" : "rgba(244, 241, 235, 0.85)")
    : "rgba(244, 241, 235, 0.85)"; // light default during SSR

  const activeLinkBg = mounted
    ? (isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.05)")
    : "rgba(0,0,0,0.05)";

  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      background: navBg,
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      borderBottom: "1px solid var(--c-border)",
    }}>
      <div style={{
        padding: "0 18px",
        height: 60,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>

        {/* Logo */}
        <Link href="/" style={{
          display: "flex", alignItems: "center", gap: 11,
          textDecoration: "none", color: "var(--c-text)",
          outline: "none",
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "var(--g-accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 15, fontWeight: 700, color: "var(--c-text)",
            boxShadow: "0 0 24px var(--c-accent-glow)",
            flexShrink: 0,
            fontFamily: "'Lora', Georgia, serif",
            letterSpacing: "-0.02em",
          }}>D</div>
          <span style={{
            fontFamily: "'Lora', Georgia, serif",
            fontWeight: 600,
            fontSize: 17.5,
            letterSpacing: "-0.025em",
            color: "var(--c-text)",
          }}>DocsChat</span>
        </Link>

        {/* Nav links */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link
            href="/login"
            style={{
              fontFamily: "'Outfit', sans-serif",
              fontSize: 13.5,
              fontWeight: 500,
              color: path === "/login" ? "var(--c-text)" : "var(--c-text-muted)",
              background: path === "/login" ? activeLinkBg : "transparent",
              padding: "7px 15px",
              borderRadius: 8,
              textDecoration: "none",
              transition: "all 0.15s",
              border: "1px solid transparent",
            }}
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="btn btn-primary btn-sm"
            style={{ fontSize: 13.5, letterSpacing: "-0.01em" }}
          >
            Get started
          </Link>

          {/* Theme switcher dropdown */}
          <div ref={themeMenuRef} style={{ position: "relative" }}>
            <button 
              onClick={() => setShowThemeMenu(v => !v)} 
              className="btn-ghost btn-sm" 
              style={{ 
                width: 38, 
                height: 38, 
                borderRadius: 12, 
                padding: 0, 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center",
                background: showThemeMenu
                  ? (mounted && !isDark ? "#F0EDE6" : "rgba(255,255,255,0.06)")
                  : "transparent",
                border: showThemeMenu ? "1px solid var(--c-border-mid)" : "1px solid transparent",
                position: "relative",
                cursor: "pointer",
                transition: "all 0.15s"
              }}
              title="Theme Settings"
            >
              <span style={{ 
                position: "absolute", 
                top: 4, 
                right: 4, 
                width: 8, 
                height: 8, 
                borderRadius: "50%", 
                background: "var(--c-accent)",
                boxShadow: "0 0 8px var(--c-accent-glow)"
              }} />

              {/* Render moon icon always — avoids hydration mismatch. After mount show correct icon. */}
              {(!mounted || isDark) ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--c-text-muted)" }}>
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--c-text-muted)" }}>
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
              )}
            </button>

            {showThemeMenu && (
              <div style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                width: 240,
                background: mounted && !isDark ? "rgba(255, 255, 255, 0.98)" : "rgba(22, 20, 16, 0.95)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                border: `1px solid ${mounted && !isDark ? "#CEC9BC" : "var(--c-border-mid)"}`,
                borderRadius: 16,
                padding: 16,
                boxShadow: "0 10px 32px rgba(0,0,0,0.35)",
                zIndex: 1000,
                display: "flex",
                flexDirection: "column",
                gap: 14,
                animation: "navPop 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) both"
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em", color: mounted && !isDark ? "#9A9080" : "rgba(240,237,230,0.4)" }}>
                  Theme Options
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--c-text-muted)" }}>Accent Color</div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    {[
                      { id: "blue", name: "Blue", hex: "#38BDF8" },
                      { id: "purple", name: "Purple", hex: "#A855F7" },
                      { id: "cyan", name: "Cyan", hex: "#06B6D4" },
                      { id: "emerald", name: "Emerald", hex: "#10B981" }
                    ].map(c => {
                      const isActive = themeColor === c.id;
                      return (
                        <button
                          key={c.id}
                          onClick={() => setThemeColor(c.id)}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: "50%",
                            background: c.hex,
                            border: isActive
                              ? `3px solid ${mounted && !isDark ? "#27251D" : "#fff"}`
                              : `1px solid ${mounted && !isDark ? "rgba(0,0,0,0.15)" : "rgba(255,255,255,0.2)"}`,
                            boxShadow: isActive ? `0 0 12px ${c.hex}` : "none",
                            cursor: "pointer",
                            transition: "all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
                            position: "relative",
                            padding: 0
                          }}
                          title={c.name}
                          onMouseEnter={e => {
                            if (!isActive) e.currentTarget.style.transform = "scale(1.15)";
                          }}
                          onMouseLeave={e => {
                            if (!isActive) e.currentTarget.style.transform = "scale(1)";
                          }}
                        >
                          {isActive && (
                            <span style={{
                              position: "absolute",
                              inset: -6,
                              borderRadius: "50%",
                              border: `1.5px solid ${c.hex}`,
                              animation: "navPulseAccent 1.6s infinite"
                            }} />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div style={{ height: "1px", background: "var(--c-border)" }} />

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--c-text-muted)" }}>Appearance</div>
                  <div style={{ 
                    display: "flex", 
                    background: mounted && !isDark ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.04)", 
                    borderRadius: 10, 
                    padding: 3, 
                    gap: 4 
                  }}>
                    {[
                      { id: "dark", name: "Dark", icon: "🌙" },
                      { id: "light", name: "Light", icon: "☀️" }
                    ].map(modeOpt => {
                      const isModeActive = themeMode === modeOpt.id;
                      return (
                        <button
                          key={modeOpt.id}
                          onClick={() => setThemeMode(modeOpt.id)}
                          style={{
                            flex: 1,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 6,
                            padding: "6px 0",
                            fontSize: 12,
                            fontWeight: 600,
                            border: "none",
                            borderRadius: 7,
                            background: isModeActive ? (mounted && !isDark ? "#FFFFFF" : "#2D2D2D") : "transparent",
                            color: isModeActive ? "var(--c-text)" : "var(--c-text-muted)",
                            cursor: "pointer",
                            boxShadow: isModeActive && mounted && !isDark ? "0 2px 6px rgba(0,0,0,0.06)" : "none",
                            transition: "all 0.15s"
                          }}
                        >
                          <span>{modeOpt.icon}</span>
                          <span>{modeOpt.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
