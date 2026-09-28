import React, { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Console from "./pages/Console.jsx";
import Report from "./pages/Report.jsx";
import Track from "./pages/Track.jsx";

function Shell() {
  const { officer, booting } = useAuth();
  const [screen, setScreen] = useState("landing"); // "landing" | "login" | "report"
  const [authTab, setAuthTab] = useState("signin");

  if (booting) {
    // Silent session-restore in progress - a brief centered spinner beats
    // an unexplained blank white screen while we avoid a landing-page flash.
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        minHeight: "100dvh", color: "var(--copper)", fontFamily: "var(--font-sans)", background: "var(--paper)",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 28, height: 28, margin: "0 auto 10px", borderRadius: "50%",
            border: "2px solid var(--line-strong)", borderTopColor: "var(--copper)",
            animation: "vajra-spin 0.8s linear infinite",
          }} />
          <div style={{ fontSize: "calc(13px * var(--fs-scale, 1))", opacity: 0.7 }}>Loading VAJRA…</div>
        </div>
        <style>{"@keyframes vajra-spin{to{transform:rotate(360deg)}}"}</style>
      </div>
    );
  }

  if (officer) return <Console />;

  if (screen === "login") {
    return (
      <Login
        initialTab={authTab}
        onBack={() => setScreen("landing")}
      />
    );
  }

  if (screen === "report") {
    return <Report onBack={() => setScreen("landing")} />;
  }

  if (screen === "track") {
    return <Track onBack={() => setScreen("landing")} />;
  }

  return (
    <Landing
      onAuth={(tab) => { setAuthTab(tab); setScreen("login"); }}
      onReport={() => setScreen("report")}
      onTrack={() => setScreen("track")}
    />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
