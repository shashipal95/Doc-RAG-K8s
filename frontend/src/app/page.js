"use client";
import Navbar from "@/components/Navbar";
import Link from "next/link";

const FEATURES = [
  { icon: "🎙️", title: "Multimodal Intelligence", desc: "Native vision and audio transcription. Analyze images, charts, and voice recordings effortlessly." },
  { icon: "🔍", title: "Multiple Model Support", desc: "Leverage advanced semantic analysis across different AI models for the ultimate accuracy." },
  { icon: "🔐", title: "Secure Multi-Format", desc: "Full support for PDF, DOCX, and media files, all protected by enterprise-grade encryption." },
];

export default function Home() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--c-bg)", overflowX: "hidden", position: "relative" }}>
      <Navbar />

      {/* Ambient background */}
      <div aria-hidden style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}>
        <div className="orb" style={{
          width: 800, height: 800,
          background: "radial-gradient(circle, var(--c-accent-soft) 0%, transparent 70%)",
          top: "-10%", left: "-10%",
        }} />
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: "linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }} />
      </div>


      <main style={{ position: "relative", zIndex: 1, paddingTop: 110 }}>
        
        {/* HERO SECTION */}
        <section className="hero-grid">
          <div className="hero-content">
            <h1 className="text-display" style={{ fontSize: "clamp(2.5rem, 5vw, 4.8rem)", lineHeight: 1.02, color: "var(--c-text)", marginBottom: 24 }}>
              Your documents, <br/>
              <span style={{ fontStyle: "italic", color: "var(--c-accent)" }}>finally</span> speak.
            </h1>
            
            <p style={{ fontSize: 18, color: "var(--c-text-muted)", lineHeight: 1.7, maxWidth: 520, marginBottom: 40 }}>
              Stop reading. Start talking. DocsChat uses advanced semantic search to context-aware answers from your private data in seconds.
            </p>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center", alignItems: "center" }}>
              <Link href="/signup" className="btn btn-primary" style={{ height: 52, padding: "0 32px", fontSize: 16 }}>Get Started for Free</Link>
              <Link href="/login" className="btn btn-ghost" style={{ height: 52, padding: "0 32px", fontSize: 16, border: "1px solid var(--c-border-soft)" }}>Sign in</Link>
              
              {/* Demo Button */}
              <button 
                onClick={async () => {
                  const btn = document.getElementById('demo-btn');
                  btn.innerText = "Logging in...";
                  try {
                    const formData = new FormData();
                    formData.append('email', 'demo@shashipal.in');
                    formData.append('password', 'demouser123');
                    
                    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/auth/login`, {
                      method: "POST",
                      body: formData,
                    });
                    
                    if (res.ok) {
                      const data = await res.json();
                      
                      // Use the correct keys from src/lib/auth.js
                      localStorage.setItem("docchat_access_token", data.access_token);
                      localStorage.setItem("docchat_user", JSON.stringify({ 
                        email: data.email, 
                        full_name: "Demo User" 
                      }));
                      localStorage.setItem("docchat_token_expiry", String(Date.now() + 3600 * 1000));

                      window.location.href = "/chat";
                    } else {
                      alert("Demo login failed. Please try again later.");
                      btn.innerText = "Try Demo";
                    }
                  } catch (err) {
                    console.error(err);
                    btn.innerText = "Try Demo";
                  }
                }}
                id="demo-btn"
                className="btn" 
                style={{ 
                  height: 52, 
                  padding: "0 32px", 
                  fontSize: 16, 
                  border: "1px solid var(--c-accent)",
                  color: "var(--c-accent)",
                  background: "var(--c-accent-soft)"
                }}
              >
                Try Demo
              </button>
            </div>
          </div>

          {/* Chat Preview Card Mockup */}
          <div style={{ position: "relative", maxWidth: 440, margin: "0 auto", width: "100%" }}>
             <div style={{ 
               background: "var(--c-surface)", 
               border: "1px solid var(--c-border-mid)", 
               borderRadius: 24, 
               boxShadow: "0 60px 120px rgba(0,0,0,0.6)",
               overflow: "hidden"
             }}>

                <div style={{ padding: "14px 20px", background: "var(--c-surface-2)", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--c-border-soft)" }}>
                   <div style={{ display: "flex", gap: 6 }}>
                      {[1,2,3].map(n => <div key={n} style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--c-text-ghost)" }} />)}
                   </div>
                   <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", opacity: 0.4 }}>SEC_Filing_2024.pdf</div>
                </div>
                <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
                   <div style={{ alignSelf: "flex-end", background: "var(--g-accent)", color: "var(--c-text)", padding: "10px 16px", borderRadius: "14px 14px 2px 14px", fontSize: 13, fontWeight: 500 }}>What was the net profit?</div>
                   <div style={{ display: "flex", gap: 12 }}>
                      <div style={{ width: 26, height: 26, borderRadius: "50%", background: "var(--g-accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: "#000" }}>D</div>
                      <div style={{ background: "var(--c-surface-2)", padding: "12px 16px", borderRadius: "2px 14px 14px 14px", fontSize: 13, color: "var(--c-text-muted)", lineHeight: 1.6, border: "1px solid var(--c-border-soft)" }}>
                        Based on page 4, the net profit was <span style={{ color: "var(--c-accent)", fontWeight: 600 }}>$4.2B</span> — an 11% increase from the previous quarter.
                      </div>
                   </div>
                </div>
             </div>
             {/* Abstract shape behind */}
             <div style={{ position: "absolute", inset: -20, background: "radial-gradient(circle, var(--c-accent-soft) 0%, transparent 70%)", zIndex: -1 }} />
          </div>
        </section>

        {/* FEATURES GRID */}
        <section style={{ borderTop: "1px solid var(--c-border-soft)", background: "var(--c-bg-warm)", padding: "100px 24px" }}>
           <div style={{ maxWidth: 1100, margin: "0 auto" }}>
              <div style={{ textAlign: "center", marginBottom: 60 }}>
                 <h2 className="text-display" style={{ fontSize: 36, marginBottom: 16, color: "var(--c-text)" }}>Everything you need</h2>
                 <p style={{ color: "var(--c-text-muted)", maxWidth: 500, margin: "0 auto" }}>Powerful AI tools designed for modern efficiency and absolute data privacy.</p>
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 24 }}>
                 {FEATURES.map((f, i) => (
                   <div key={f.title} style={{ background: "var(--c-surface)", padding: 32, borderRadius: 20, border: "1px solid var(--c-border-mid)", transition: "all 0.3s" }}>
                      <div style={{ fontSize: 24, marginBottom: 20 }}>{f.icon}</div>
                      <h3 style={{ fontSize: 17, fontWeight: 600, marginBottom: 12, color: "var(--c-text)" }}>{f.title}</h3>
                      <p style={{ fontSize: 14, color: "var(--c-text-muted)", lineHeight: 1.5 }}>{f.desc}</p>
                   </div>
                 ))}
              </div>
           </div>
        </section>

        {/* FOOTER */}
        <footer style={{ padding: "80px 24px 40px", borderTop: "1px solid var(--c-border-soft)" }}>
           <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 40 }}>
              <div>
                 <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "var(--font-display)", color: "var(--c-text)", marginBottom: 16 }}>DocsChat<span style={{ color: "var(--c-accent)" }}>.</span></div>
                 <p style={{ fontSize: 13, color: "var(--c-text-muted)", maxWidth: 300 }}>Built for professional document intelligence and secure semantic retrieval.</p>
              </div>
              
              <div style={{ display: "flex", gap: 32 }}>
                 <Link href="/login" style={{ fontSize: 13, color: "var(--c-text-muted)", textDecoration: "none" }}>Log in</Link>
                 <Link href="/signup" style={{ fontSize: 13, color: "var(--c-text-muted)", textDecoration: "none" }}>Sign up</Link>
                 <Link href="#" style={{ fontSize: 13, color: "var(--c-text-muted)", textDecoration: "none" }}>Documentation</Link>
              </div>
           </div>
           
           <div style={{ maxWidth: 1100, margin: "40px auto 0", paddingTop: 40, borderTop: "1px solid var(--c-border-soft)", display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--c-text-muted)" }}>
              <span>© 2026 DocsChat AI.</span>
              <div style={{ display: "flex", gap: 20 }}>
                 <span>Privacy</span>
                 <span>Terms</span>
              </div>
           </div>
        </footer>
      </main>
    </div>
  );
}
