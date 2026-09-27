import React from "react";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext.jsx";
import { toast } from "../console-core/components/toast.js";
import { useTheme, toggleTheme } from "../lib/prefs.js";
import { ICONS } from "../console-core/icons.js";

// Shared motion variants - one place to tune the whole page's feel instead
// of re-writing the same fade+rise on every section.
const fadeUp = {
  hidden: { opacity: 0, y: 22 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] } },
};
const staggerParent = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
const staggerChild = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } },
};
// viewport settings shared by every scroll-triggered section: fire once,
// slightly before the section fully enters so it doesn't feel late.
const revealViewport = { once: true, margin: "0px 0px -80px 0px" };

export default function Landing({ onAuth, onReport, onTrack }) {
  const { login } = useAuth();
  const [demoLoading, setDemoLoading] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const theme = useTheme();
  const navRef = React.useRef(null);

  React.useEffect(() => {
    const onScroll = () => navRef.current && navRef.current.classList.toggle("scrolled", window.scrollY > 40);
    document.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => document.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setMenuOpen(false);
  };

  const demoLogin = async () => {
    setDemoLoading(true);
    try {
      await login("MHA-CY-08231", "vajra123");
    } catch (err) {
      toast(err.message || "Couldn't start the demo - try Sign in instead.", "error");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div id="landingScreen">
      <div className="gov-strip" aria-hidden="true"></div>
      <motion.nav
        id="landingNav"
        ref={navRef}
        aria-label="Primary"
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="brandmark">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" strokeWidth="1.4"><path d="M12 2l7 3v6c0 5-3.2 8.4-7 11-3.8-2.6-7-6-7-11V5l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
          <span className="brandmark-name">VAJRA</span>
          <span className="gov-badge"><span dangerouslySetInnerHTML={{ __html: ICONS.chakra }} />Govt. of India</span>
        </div>
        <div id="landingNavLinks" className={menuOpen ? "open" : ""}>
          <a href="#landingHero" onClick={scrollTo("landingHero")}>Home</a>
          <a href="#landingCapabilities" onClick={scrollTo("landingCapabilities")}>Capabilities</a>
          <a href="#landingFeatures" onClick={scrollTo("landingFeatures")}>How it works</a>
          <a href="#landingAbout" onClick={scrollTo("landingAbout")}>About</a>
          <a href="#landingDemo" onClick={scrollTo("landingDemo")}>Demo</a>
        </div>
        <div className="l-nav-spacer"></div>
        <div className="l-nav-actions">
          <button className="l-icon-btn" id="landingThemeBtn" title="Toggle theme" aria-label="Toggle theme" onClick={toggleTheme}>
            {theme === "dark"
              ? <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="10" cy="10" r="3.4"/><path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1L4.7 4.7"/></svg>
              : <svg viewBox="0 0 20 20" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"><path d="M17 11.2A7 7 0 1 1 8.8 3 5.6 5.6 0 0 0 17 11.2z"/></svg>}
          </button>
          <button className="l-btn l-btn-ghost" onClick={onReport}>Report a suspect wallet</button>
          <button className="l-btn l-btn-ghost" onClick={onTrack}>Track your report</button>
          <button className="l-btn l-btn-ghost" onClick={() => onAuth("signin")}>Sign in</button>
          <button className="l-btn l-btn-solid" onClick={() => onAuth("signup")}>Create account</button>
          <button className="l-icon-btn" id="landingNavToggle" aria-label="Menu" aria-expanded={menuOpen} aria-controls="landingNavLinks"
                  onClick={() => setMenuOpen((o) => !o)}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M3 5h14M3 10h14M3 15h14"/></svg>
          </button>
        </div>
      </motion.nav>

      <main id="mainContent" tabIndex={-1}>

      <section id="landingHero">
        <div className="hero-cyber-bg" aria-hidden="true">
          <svg viewBox="0 0 800 420" preserveAspectRatio="xMidYMid slice">
            <defs>
              <radialGradient id="heroRadarFade" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="var(--copper)" stopOpacity="0.16"/>
                <stop offset="70%" stopColor="var(--copper)" stopOpacity="0.03"/>
                <stop offset="100%" stopColor="var(--copper)" stopOpacity="0"/>
              </radialGradient>
              <linearGradient id="heroRadarSweep" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="var(--copper)" stopOpacity="0"/>
                <stop offset="100%" stopColor="var(--copper)" stopOpacity="0.4"/>
              </linearGradient>
            </defs>
            {/* soft radar glow + slow rotating sweep wedge, centered on the rightmost node cluster */}
            <circle cx="560" cy="180" r="190" fill="url(#heroRadarFade)"/>
            <g className="hero-cyber-radar" style={{ transformOrigin: "560px 180px" }}>
              <path d="M560,180 L560,10 A170,170 0 0 1 700,90 Z" fill="url(#heroRadarSweep)"/>
            </g>
            {/* trace network: a handful of nodes + connecting lines, echoing the fund-flow graph the product actually draws */}
            <g stroke="var(--copper)" strokeOpacity="0.35" strokeWidth="1">
              <line className="hero-cyber-line" x1="90" y1="330" x2="260" y2="230"/>
              <line className="hero-cyber-line" x1="260" y1="230" x2="430" y2="260"/>
              <line className="hero-cyber-line" x1="430" y1="260" x2="560" y2="180"/>
              <line className="hero-cyber-line" x1="560" y1="180" x2="680" y2="110"/>
              <line className="hero-cyber-line" x1="430" y1="260" x2="520" y2="340"/>
            </g>
            <g fill="var(--copper)">
              <circle className="hero-cyber-node n1" cx="90" cy="330" r="2.6"/>
              <circle className="hero-cyber-node n2" cx="260" cy="230" r="2.6"/>
              <circle className="hero-cyber-node n3" cx="430" cy="260" r="2.6"/>
              <circle className="hero-cyber-node n4" cx="560" cy="180" r="3.2"/>
              <circle className="hero-cyber-node n5" cx="680" cy="110" r="2.6"/>
              <circle className="hero-cyber-node n3" cx="520" cy="340" r="2.4"/>
            </g>
            {/* three packets travelling the trace at different speeds, like live fund-flow hops */}
            <circle r="2.6" fill="var(--sage)">
              <animateMotion dur="3.2s" repeatCount="indefinite">
                <mpath href="#heroBgPath1"/>
              </animateMotion>
            </circle>
            <circle r="2.2" fill="var(--slate)">
              <animateMotion dur="4.1s" begin="0.6s" repeatCount="indefinite">
                <mpath href="#heroBgPath2"/>
              </animateMotion>
            </circle>
            <path id="heroBgPath1" d="M90,330 L260,230 L430,260 L560,180 L680,110" fill="none" opacity="0"/>
            <path id="heroBgPath2" d="M430,260 L520,340" fill="none" opacity="0"/>
          </svg>
        </div>
        <div className="l-wrap hero-grid">
          <motion.div
            initial="hidden" animate="visible" variants={staggerParent}
          >
            <motion.div variants={staggerChild} className="hero-eyebrow">National Cyber-Crime Threat Analytics Unit</motion.div>
            <motion.h1 variants={staggerChild}>Trace the money. Name the exchange.</motion.h1>
            <motion.p variants={staggerChild} className="hero-story">
              Every crypto fraud complaint starts the same way: a victim's wallet
              address and a deadline. VAJRA takes it from there - clustering the
              suspect's on-chain footprint, scoring how confident the attribution
              really is, and drafting the legal notice the moment the evidence
              supports one.
            </motion.p>
            <motion.div variants={staggerChild} className="hero-ctas">
              <motion.button whileHover={{ y: -2, boxShadow: "var(--shadow-md)" }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-solid" onClick={demoLogin} disabled={demoLoading}>
                {demoLoading ? "Signing in…" : "Launch live demo"}
              </motion.button>
              <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-ghost" onClick={() => onAuth("signup")}>Create free account</motion.button>
              <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-ghost" onClick={onReport}>Lost funds? Report a wallet &rarr;</motion.button>
              <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-ghost" onClick={onTrack}>Already reported? Track it &rarr;</motion.button>
            </motion.div>
            <motion.div variants={staggerChild} className="hero-stats">
              <div className="hero-stat"><div className="n">6-stage</div><div className="l">Real tracing pipeline - collection to notice, no canned steps</div></div>
              <div className="hero-stat"><div className="n">3 chains</div><div className="l">Bitcoin, Ethereum and Tron adapters with live failover</div></div>
              <div className="hero-stat"><div className="n">FastAPI + React</div><div className="l">Standard, maintainable stack end to end</div></div>
            </motion.div>
          </motion.div>

          <motion.div
            className="hero-art"
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
            whileHover={{ y: -4 }}
          >
            <div className="card">
              <div className="card-label">CASE NCRP-2026-88213 &middot; ETHEREUM</div>
              <svg className="hero-hopflow" viewBox="0 0 360 130" aria-hidden="true">
                <path id="heroHopPath" d="M20 100 C 90 20, 160 110, 210 45 S 310 15, 340 60" fill="none" stroke="var(--line-strong)" strokeWidth="1.4" strokeDasharray="3 5"/>
                <circle cx="20" cy="100" r="5" fill="var(--copper-deep)"/>
                <circle cx="210" cy="45" r="5" fill="var(--slate)"/>
                <circle cx="340" cy="60" r="6" fill="var(--brass)"/>
                <circle r="3.4" fill="var(--copper)" className="hero-hop-pulse">
                  <animateMotion dur="4.5s" repeatCount="indefinite" rotate="auto">
                    <mpath href="#heroHopPath"/>
                  </animateMotion>
                </circle>
              </svg>
              <div className="card-foot">
                <span>Deposit-fingerprint match &middot; WazirX hot wallet</span>
                <span className="conf">87% confidence</span>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section id="landingCapabilities">
        <div className="l-wrap">
          <motion.div className="l-section-head" initial="hidden" whileInView="visible" viewport={revealViewport} variants={fadeUp}>
            <div className="l-kicker">What makes VAJRA different</div>
            <h2>Six capabilities, all running on real evidence</h2>
            <p>Not a single generic "AI dashboard" feature - each of these is a distinct, working layer of the console, one tap away for anyone reviewing a live demo.</p>
          </motion.div>
          <motion.div className="cap-grid" initial="hidden" whileInView="visible" viewport={revealViewport} variants={staggerParent}>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card violet">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 3l1.8 4.2L16 9l-4.2 1.8L10 15l-1.8-4.2L4 9l4.2-1.8z"/></svg></div>
              <div className="cap-title">AI Investigation Copilot</div>
              <div className="cap-desc">Narrates why a wallet is flagged - ranked by real evidence - and recommends the next concrete step, not free-text guessing.</div>
            </motion.div>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="5" cy="4" r="1.6"/><circle cx="15" cy="4" r="1.6"/><circle cx="10" cy="10" r="1.6"/><circle cx="5" cy="16" r="1.6"/><circle cx="15" cy="16" r="1.6"/><path d="M6.2 5L8.6 8.6M13.8 5L11.4 8.6M8.6 11.4L6.2 15M11.4 11.4L13.8 15"/></svg></div>
              <div className="cap-title">Syndicate Score&trade;</div>
              <div className="cap-desc">Turns "40 isolated ₹15,000 complaints" into one ranked WATCH / ESCALATE / CRITICAL signal the moment they share a wallet cluster.</div>
            </motion.div>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card amber">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/></svg></div>
              <div className="cap-title">Freeze Window&trade;</div>
              <div className="cap-desc">An explicit, honestly-labeled heuristic estimate of how long before pooled funds likely move again - shrinks as a syndicate grows.</div>
            </motion.div>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 15l4-8 4 5 3-4 3 6"/></svg></div>
              <div className="cap-title">Explainable AI</div>
              <div className="cap-desc">Every risk score ships with the SHAP-style factor breakdown behind it - no black-box percentage a judge can't interrogate.</div>
            </motion.div>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card violet">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="4" cy="5" r="1.8"/><circle cx="16" cy="5" r="1.8"/><circle cx="10" cy="15" r="1.8"/><path d="M6 5h8M5.5 6.7L9 13.3M14.5 6.7L11 13.3"/></svg></div>
              <div className="cap-title">Cross-case Intelligence</div>
              <div className="cap-desc">A real graph query links complaints that share an address across different officers and jurisdictions - automatically, not manually.</div>
            </motion.div>
            <motion.div variants={staggerChild} whileHover={{ y: -5 }} className="metric-card">
              <div className="icon"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="4" width="14" height="12" rx="1.5"/><path d="M3 8h14M7 12h6"/></svg></div>
              <div className="cap-title">Evidence Timeline</div>
              <div className="cap-desc">Scrubs through the actual chronological transaction list, hop by hop, revealing the fund-flow graph exactly as it happened.</div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      <section id="landingFeatures">
        <div className="l-wrap">
          <motion.div className="l-section-head" initial="hidden" whileInView="visible" viewport={revealViewport} variants={fadeUp}>
            <div className="l-kicker">How it works</div>
            <h2>One pipeline, from a wallet address to a signed notice</h2>
            <p>Every trace runs the same six stages - each one real code, not a progress bar timed against nothing.</p>
          </motion.div>
          <motion.div className="pipeline" initial="hidden" whileInView="visible" viewport={revealViewport} variants={staggerParent}>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">01</span><h3>Collection</h3><p>Pulls the suspect wallet's forward transaction history from a live chain adapter.</p></motion.div>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">02</span><h3>Tracing</h3><p>Follows funds forward up to six hops, building the full transaction graph.</p></motion.div>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">03</span><h3>Clustering</h3><p>Co-spend, change-address and deposit-fingerprint heuristics group related addresses.</p></motion.div>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">04</span><h3>Obfuscation check</h3><p>Flags known mixer contracts on the path and honestly stops rather than guessing past them.</p></motion.div>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">05</span><h3>Scoring</h3><p>A weighted confidence formula plus a trained illicit-probability classifier.</p></motion.div>
            <motion.div variants={staggerChild} className="pipeline-step"><span className="num">06</span><h3>Notice &amp; approval</h3><p>An outcome-aware CrPC/BNSS notice drafted automatically, routed through maker-checker approval.</p></motion.div>
          </motion.div>
        </div>
      </section>

      <section id="landingAbout">
        <div className="l-wrap about-grid">
          <motion.div initial="hidden" whileInView="visible" viewport={revealViewport} variants={fadeUp}>
            <div className="l-kicker">About VAJRA</div>
            <h2 style={{ fontFamily: "var(--font-serif)", fontSize: "clamp(24px,3vw,32px)", fontWeight: 600, color: "var(--text)", lineHeight: 1.24, marginBottom: 18 }}>Virtual Asset Judicial Response &amp; Attribution</h2>
            <p>VAJRA is a fund-flow tracing and exchange-attribution console for cyber-crime investigators.</p>
            <p>It's deliberately honest about what's finished and what's a documented next step: the clustering heuristics, the scoring formula, the classifier and the notice drafting all run for real inside the console.</p>
            <p>The interface is modelled on Indian government web conventions - an identity header, adjustable text size, light and dark themes, keyboard navigation - with semantic colour that carries meaning: red for critical risk, amber for pending, green for verified.</p>
          </motion.div>
          <motion.div className="trust-list" initial="hidden" whileInView="visible" viewport={revealViewport} variants={staggerParent}>
            <motion.div variants={staggerChild} className="trust-item"><span className="dot"></span><div><div className="t">Maker-checker approvals</div><div className="s">An officer drafts a notice; a supervisor has to approve it before it goes out.</div></div></motion.div>
            <motion.div variants={staggerChild} className="trust-item"><span className="dot"></span><div><div className="t">Full audit trail</div><div className="s">Every sign-in, trace and notice is logged and searchable by an admin.</div></div></motion.div>
            <motion.div variants={staggerChild} className="trust-item"><span className="dot"></span><div><div className="t">Standard, maintainable stack</div><div className="s">FastAPI backend, React console - easy for any teammate to pick up.</div></div></motion.div>
            <motion.div variants={staggerChild} className="trust-item"><span className="dot"></span><div><div className="t">Role-based access</div><div className="s">Officer, Supervisor and Admin each see exactly what their role permits, enforced server-side.</div></div></motion.div>
          </motion.div>
        </div>
      </section>

      <section>
        <motion.div id="landingDemo" initial="hidden" whileInView="visible" viewport={revealViewport} variants={fadeUp}>
          <div className="demo-inner">
            <div>
              <h2>See three honest outcomes from the same real pipeline</h2>
              <p>The live demo signs you in as Officer R. Kulkarni with a real seeded case queue - run an actual trace and watch the pipeline decide.</p>
              <div className="demo-cta">
                <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-solid" onClick={demoLogin} disabled={demoLoading}>
                  {demoLoading ? "Signing in…" : "Launch live demo as Officer"}
                </motion.button>
                <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} className="l-btn l-btn-ghost demo-signin-ghost" onClick={() => onAuth("signin")}>Sign in instead</motion.button>
              </div>
            </div>
            <div className="demo-scenarios">
              <div className="demo-scenario"><span className="chip-dot" style={{ background: "#22D3EE" }}></span>Ethereum case → deposit-fingerprint match → 87% confidence, suggest freeze notice</div>
              <div className="demo-scenario"><span className="chip-dot" style={{ background: "#F59E0B" }}></span>Tron case → trail hits a known mixer → confidence collapses, flagged for manual review</div>
              <div className="demo-scenario"><span className="chip-dot" style={{ background: "#60A5FA" }}></span>Bitcoin case → no exchange pattern anywhere on the path → insufficient evidence, recommend closing</div>
            </div>
          </div>
        </motion.div>
      </section>

      </main>

      <footer id="landingFoot">
        <div className="l-wrap foot-row">
          <span>VAJRA &middot; National Cyber-Crime Threat Analytics Unit</span>
          <span>See About this build inside the console for the full built-vs-roadmap breakdown.</span>
        </div>
      </footer>
    </div>
  );
}
