import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Truck, LogOut } from "lucide-react";
import {
  CLAIM_STATES,
  fetchDashboard,
  subscribeDashboard,
  type ChannelKind,
  type ClaimState,
  type DashboardView,
} from "./data";
import { Timeline } from "./components/Timeline";
import { PartyRoster } from "./components/PartyRoster";
import { StatePipeline } from "./components/StatePipeline";
import { ChannelTag } from "./components/ChannelTag";

const POLL_MS = 2000;

export default function App({ embedded = false, sessionId: sessionIdProp, onExit }: { embedded?: boolean; sessionId?: string | null; onExit?: () => void } = {}) {
  // In embedded (split-demo) mode, skip the boot screen + entrance animation so
  // the operator pane renders instantly with no transient fade/ghost overlap.
  const [booting, setBooting] = useState(!embedded);
  const [view, setView] = useState<DashboardView | null>(null);
  const [connected, setConnected] = useState(false);

  // The session to pin to comes from context/props (SPA) — no URL parsing.
  const sessionId = sessionIdProp ?? undefined;

  // Brief boot so the app enters like a real product (connect + hydrate).
  // Skipped entirely when embedded in the split demo.
  useEffect(() => {
    if (embedded) return;
    const t = window.setTimeout(() => setBooting(false), 700);
    return () => clearTimeout(t);
  }, [embedded]);

  // Realtime: subscribe to the SSE stream (true push). If the stream can't
  // stay connected, transparently fall back to interval polling so the operator
  // view always stays live.
  const [transport, setTransport] = useState<"live" | "polling">("live");
  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | null = null;

    // In the split demo, don't fall back to the server's "latest" session when
    // no session is pinned yet — that would surface a PREVIOUS claim's data.
    // Show the clean idle state and wait for the phone to start a fresh one.
    if (embedded && !sessionId) {
      setView({ exists: false });
      setConnected(true);
      return;
    }

    const startPolling = () => {
      setTransport("polling");
      const tick = async () => {
        const v = await fetchDashboard(sessionId);
        if (cancelled) return;
        setConnected(true);
        setView(v);
        pollTimer = window.setTimeout(tick, POLL_MS);
      };
      tick();
    };

    // Prime immediately so the UI isn't empty before the first SSE frame.
    fetchDashboard(sessionId).then((v) => {
      if (!cancelled) {
        setView(v);
        setConnected(true);
      }
    });

    let failed = 0;
    const unsub = subscribeDashboard(
      sessionId,
      (v) => {
        if (cancelled) return;
        failed = 0;
        setTransport("live");
        setView(v);
      },
      (ok) => {
        if (cancelled) return;
        setConnected(ok);
        if (!ok && ++failed >= 3 && pollTimer === null) startPolling();
      }
    );

    return () => {
      cancelled = true;
      unsub();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [sessionId, embedded]);

  if (booting) {
    return (
      <div className="boot">
        <div className="boot-card">
          <div className="boot-mark">
            <img src="./hcltech-logo.jpg" alt="HCLTech" width={52} height={52} />
          </div>
          <div style={{ textAlign: "center" }}>
            <div className="boot-title">One Touch Resolve</div>
            <div className="boot-sub">Connecting to Bedrock AgentCore…</div>
          </div>
          <div className="spinner" />
        </div>
      </div>
    );
  }

  const exists = Boolean(view?.exists);
  const state: ClaimState = view?.state ?? "REPORTED";
  const parties = view?.parties ?? [];
  const timeline = view?.timeline ?? [];
  const channels: ChannelKind[] = view?.channels ?? [];
  const tow = view?.tow;
  // Settled if the server flag says so OR the pipeline has reached SETTLED —
  // avoids the "SETTLED but still Coordinating live" contradiction.
  const settled = Boolean(view?.settled) || (view?.state === "SETTLED");
  const triage = view?.triage;
  const committed = parties.filter((p) =>
    ["committed", "booked", "reserved", "safe", "confirmed", "dispatched"].includes(
      p.status.toLowerCase()
    )
  ).length;
  const total = parties.length;
  const stateIdx = CLAIM_STATES.indexOf(state);
  const progress = exists ? Math.round(((stateIdx + 1) / CLAIM_STATES.length) * 100) : 0;

  const running = exists && !settled;

  // Live usage figures mapped from the real claim.
  const consents = view?.consents ?? 0;
  const pct = exists ? progress : 0;

  return (
    <div className={embedded ? "nexus nexus-embedded" : "nexus"}>
      {/* ── Sidebar ── */}
      <aside className="nx-side">
        <div className="nx-brand">
          <h1>HCLTech</h1>
          <div className="nx-prod">One Touch Resolve</div>
          <div className="nx-prod-sub">Agentic Claims Coordination Engine</div>
        </div>

        <div className="nx-view"><span className="sw" /> OPERATOR VIEW</div>

        <button
          className="nx-cta"
          onClick={() => onExit?.()}
          title="Return to the landing page"
        >
          <LogOut size={16} strokeWidth={2.2} /> Exit console
        </button>

        <ul className="nx-nav">
          <li className="active">Live Claim {exists && <span className="ct">1</span>}</li>
          <li>Parties <span className="ct">{total}</span></li>
          <li>Timeline</li>
          <li>Channels <span className="ct">{channels.length}</span></li>
        </ul>

        <div className="nx-livebox">
          <div className="lbl">SESSION</div>
          <div className="lrow">
            <span
              className="ldot"
              style={{ background: !connected ? "#6f83a0" : running ? "#2f9bff" : settled ? "#1fae6c" : "#c9a227" }}
            />
            <span className="lk">Status</span>
            <span className="lv">{!connected ? "Connecting" : running ? "Live" : settled ? "Settled" : "Idle"}</span>
          </div>
          <div className="lrow">
            <span className="lk" style={{ marginLeft: 17 }}>Transport</span>
            <span className="lv">{transport === "live" ? "SSE push" : "Polling"}</span>
          </div>
          <div className="lrow">
            <span className="lk" style={{ marginLeft: 17 }}>Committed</span>
            <span className="lv">{committed}/{total}</span>
          </div>
        </div>

        <div className="nx-tenant">
          <div className="lbl">CLAIM</div>
          <div className="name">{view?.claim_id ?? "No active claim"}</div>
          <div className="meta">
            {view?.customer ? `${view.customer} · ${view?.vehicle ?? "vehicle"}` : "awaiting FNOL"}
          </div>
          <div className="ref">{view?.location ?? "—"}</div>
        </div>
      </aside>

      {/* ── Content ── */}
      <main className="nx-main">
        {/* ONE compact header: title + status + claim identity + exit */}
        <div className="nx-topbar">
          <div className="nx-topbar-l">
            <h2>Mission Control</h2>
            <span
              className="nx-statuspill"
              data-state={!connected ? "wait" : running ? "run" : settled ? "ok" : "idle"}
            >
              <span className="dot" />
              {!connected ? "Connecting" : settled ? "Settled" : running ? "Coordinating live" : "Standing by"}
            </span>
            {exists && (
              <span className="nx-claimline">
                {view?.claim_id} · {state} · {committed}/{total} committed · {channels.length} CDS
              </span>
            )}
          </div>
          <div className="nx-user">
            <div style={{ textAlign: "right" }}>
              <div className="u-name">{exists ? (view?.customer ?? "Active claim") : "Operator console"}</div>
              <div className="u-sub">
                {exists
                  ? (view?.vehicle ?? "One Touch Resolve")
                  : "One Touch Resolve · awaiting a claim"}
              </div>
            </div>
            <div className="av">{exists ? "LC" : "OTR"}</div>
            {embedded && onExit && (
              <button className="nx-topexit" onClick={() => onExit?.()} title="Exit the console">
                <LogOut size={15} strokeWidth={2.2} /> Exit
              </button>
            )}
          </div>
        </div>

        {/* Thin pipeline bar directly under the header (the only "status band") */}
        <div className="nx-pipebar-top">
          <StatePipeline current={state} />
          {channels.length > 0 && (
            <div className="nx-chgroup">
              <span className="nx-chgroup-lbl">Channels</span>
              {channels.map((c) => (
                <ChannelTag key={c} channel={c} compact />
              ))}
            </div>
          )}
          <div className="nx-pipebar-track">
            <div className="nx-pipebar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="nx-scroll">
          {/* Grid: main cards + right rail */}
          <div className="nx-grid">
            <div className="nx-col">
              {/* Agent activity */}
              <div className="nx-card nx-anim" style={{ animationDelay: "120ms" }}>
                <div className="accent" />
                <div className="nx-card-in">
                  <div className="nx-card-head">
                    <h4>Agent activity</h4>
                    <span className="meta">
                      {view?.customer ? `${view.customer} · ${view?.vehicle ?? ""}` : "no active session"}
                    </span>
                  </div>
                  <div className="scroll-area">
                    <Timeline items={timeline} live={running} />
                  </div>
                </div>
              </div>

              {/* Impact / triage */}
              <div className="nx-card nx-anim" style={{ animationDelay: "180ms" }}>
                <div className="accent teal" />
                <div className="nx-card-in">
                  <div className="nx-card-head">
                    <h4>Impact</h4>
                    {triage?.source?.includes("vision") && <span className="meta">Nova Pro vision</span>}
                  </div>
                  {(view?.photo || triage?.reasoning) && (
                    <div className="triage-vision">
                      {view?.photo && <img className="triage-photo" src={view.photo} alt="damage" />}
                      <div className="triage-vision-body">
                        {triage?.damage && <div className="triage-damage">{triage.damage}</div>}
                        {triage?.reasoning && <div className="triage-reason">{triage.reasoning}</div>}
                      </div>
                    </div>
                  )}
                  <div className="metrics">
                    <Metric
                      label="Triage"
                      value={triage?.severity ? triage.severity : "—"}
                      unit={
                        triage?.source
                          ? `${triage.source.includes("vision") ? "Vision AI" : "AI"}: ${triage.source} · ~${triage.est_repair_days ?? "?"}d repair`
                          : "awaiting damage photo"
                      }
                      green={Boolean(triage?.drivable)}
                    />
                    <Metric
                      label="Parties coordinated"
                      value={String(total)}
                      unit={`across ${channels.length || 0} CDS channel(s)`}
                    />
                    <Metric
                      label="Consents captured"
                      value={String(consents)}
                      unit="taps = auth + authorization"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Right rail */}
            <div className="nx-rail">
              <div className="nx-card nx-anim" style={{ animationDelay: "150ms" }}>
                <div className="accent violet" />
                <div className="nx-card-in">
                  <div className="nx-card-head"><h4>Parties</h4><span className="meta">{committed} / {total} engaged</span></div>
                  <PartyRoster parties={parties} />
                </div>
              </div>

              {tow?.active && (
                <div className="nx-card">
                  <div className="accent" />
                  <div className="nx-card-in">
                    <div className="nx-card-head">
                      <h4>Roadside</h4>
                      <span className="meta">{tow.arrived ? "arrived" : `ETA ${tow.eta_remaining_min ?? "—"} min`}</span>
                    </div>
                    <div className="tow-live">
                      <span className="role-ic" style={{ color: "var(--wait)", background: "var(--wait-soft)" }}>
                        <Truck size={15} strokeWidth={2.1} />
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div className="name">{tow.provider ?? "Roadside"}</div>
                        <div className="note">{tow.text}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Usage & Notices */}
              <h3 style={{ marginTop: 4 }}>Usage &amp; Notices</h3>
              <div className="nx-usage">
                <div className="row"><span className="k">Claim progress</span><span className="v">{pct}%</span></div>
                <div className="nx-bar"><div className="fill" style={{ width: `${pct}%` }} /></div>
                <div className="row"><span className="k">Parties committed</span><span className="v">{committed} / {total}</span></div>
                <div className="row"><span className="k">CDS channels used</span><span className="v">{channels.length}</span></div>
                <div className="row"><span className="k">Consents captured</span><span className="v">{consents}</span></div>
              </div>
              <div className="sep" />
              <div className="nx-notices">
                <div className="lbl">NOTICES</div>
                <div className="nx-notice">
                  {settled
                    ? "Settled — letter issued via Amazon SES."
                    : running
                    ? "Live coordination across CDS channels."
                    : "Awaiting a customer on the phone."}
                </div>
                <div className="nx-notice warn">
                  Human adjuster approval required before payout.
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function Metric({
  label,
  value,
  unit,
  green,
}: {
  label: string;
  value: string;
  unit: string;
  green?: boolean;
}) {
  return (
    <div className="metric">
      <span className="m-label">{label}</span>
      <div className="m-right">
        <span className={green ? "m-value green" : "m-value"} style={{ display: "inline-block", overflow: "hidden" }}>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={value}
              style={{ display: "inline-block" }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}
            >
              {value}
            </motion.span>
          </AnimatePresence>
        </span>
        <span className="m-unit">{unit}</span>
      </div>
    </div>
  );
}
