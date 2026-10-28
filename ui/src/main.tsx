import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { SessionProvider, useSession } from "./SessionContext";
import IntroSlides from "./IntroSlides";
import Landing from "./Landing";
import Demo from "./demo/Demo";
import "./index.css";
import "./phone/phone.css";
import "./demo/demo.css";

/**
 * Single-page app with STATE-BASED view switching (no router) — matching the
 * agentic-studio pattern. This keeps URLs clean (no "#/..." hash routes) and
 * works reliably behind the Cloud9/VFS single-port preview proxy.
 *
 * Flow: Intro (branded slides) → Landing ("Start the live demo") → Demo
 * (split phone + operator console). Demo "Exit console" → back to Landing.
 */
type View = "intro" | "landing" | "demo";

function AppRoot() {
  const [view, setView] = useState<View>("intro");
  const { setSessionId } = useSession();

  const startDemo = () => {
    // Fresh slate: clear any prior session so the operator never shows stale
    // data before the new accident's session is created by the phone.
    setSessionId(null);
    setView("demo");
  };

  const exitDemo = () => {
    setSessionId(null);
    setView("landing");
  };

  if (view === "intro") {
    return <IntroSlides onDone={startDemo} />;
  }
  if (view === "demo") {
    return <Demo onExit={exitDemo} />;
  }
  return <Landing onStart={startDemo} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SessionProvider>
      <AppRoot />
    </SessionProvider>
  </React.StrictMode>
);
