// ZCAA operator (Mission Control) — live data types + pollers.
//
// The dashboard is a SECOND VIEW of the same live claim the customer is tapping
// through on the phone. It polls /api/dashboard and renders the real journey.
// State lives on the server (zcaa/session.py); this file only types the payload
// and provides small presentation helpers the components share.

export type ChannelKind = "whatsapp" | "rcs" | "sms" | "email";

// Operator claim pipeline (maps from ZCAA journey steps on the server).
export type ClaimState = "REPORTED" | "TRIAGE" | "ASSIST" | "REPAIR" | "SETTLED";
export const CLAIM_STATES: ClaimState[] = [
  "REPORTED",
  "TRIAGE",
  "ASSIST",
  "REPAIR",
  "SETTLED",
];

// The kinds of timeline entries the server emits (Message.kind + a couple of
// derived kinds). Used to pick an icon/colour in <Timeline/>.
export type StepKind =
  | "tap"
  | "text"
  | "status"
  | "safety"
  | "tow"
  | "rental"
  | "repair"
  | "summary"
  | "fanout";

export interface Party {
  role: string;
  name: string;
  channel: ChannelKind | "";
  status: string;
  note?: string;
}

export interface Recipient {
  role: string;
  channel: ChannelKind | "";
}

export interface TimelineItem {
  actor: string;
  kind: StepKind | string; // tolerate unknown kinds from the server
  text: string;
  channel: ChannelKind | "";
  // For a multi-party fan-out (one update → several parties), the parties it
  // went to and the channel each was reached on. Rendered as inline chips.
  recipients?: Recipient[];
}

export interface Triage {
  severity?: string;
  est_repair_days?: number;
  summary?: string;
  source?: string;
  drivable?: boolean;
  reasoning?: string;
  damage?: string;
}

export interface TowStatus {
  active: boolean;
  arrived?: boolean;
  stage?: number;
  text?: string;
  eta_remaining_min?: number;
  ref?: string;
  provider?: string;
}

export interface DashboardView {
  exists: boolean;
  session_id?: string;
  customer?: string;
  vehicle?: string;
  location?: string;
  claim_id?: string;
  state?: ClaimState;
  step?: string;
  triage?: Triage;
  photo?: string;
  parties?: Party[];
  timeline?: TimelineItem[];
  channels?: ChannelKind[];
  consents?: number;
  tow?: TowStatus;
  settled?: boolean;
}

// API origin resolution:
//  1. VITE_API_BASE (build-time) wins if set, e.g. "http://1.2.3.4:8080".
//  2. Otherwise SAME-ORIGIN. The dashboard server (serve.mjs) reverse-proxies
//     /api/* to the backend, so the browser only ever talks to one port. This
//     is required behind the Cloud9/VFS preview proxy, which exposes a single
//     port — pointing calls at a second port (e.g. :8080) returns 503.
function resolveApiBase(): string {
  const injected = import.meta.env?.VITE_API_BASE as string | undefined;
  if (injected) return injected.replace(/\/$/, "");
  return "";
}
const API_BASE = resolveApiBase();

export async function fetchDashboard(sessionId?: string): Promise<DashboardView> {
  const q = sessionId ? `?id=${encodeURIComponent(sessionId)}` : "";
  try {
    const r = await fetch(`${API_BASE}/api/dashboard${q}`, { cache: "no-store" });
    if (!r.ok) return { exists: false };
    return (await r.json()) as DashboardView;
  } catch {
    return { exists: false };
  }
}

export async function fetchTow(sessionId: string): Promise<TowStatus> {
  try {
    const r = await fetch(`${API_BASE}/api/tow?id=${encodeURIComponent(sessionId)}`, {
      cache: "no-store",
    });
    if (!r.ok) return { active: false };
    return (await r.json()) as TowStatus;
  } catch {
    return { active: false };
  }
}

// True realtime: subscribe to the server's Server-Sent Events stream. The server
// pushes a `dashboard` event the instant any session changes (and while a tow is
// in progress). Returns an unsubscribe function. Falls back to null if the
// browser can't open the stream, so the caller can revert to polling.
export function subscribeDashboard(
  sessionId: string | undefined,
  onView: (v: DashboardView) => void,
  onState: (connected: boolean) => void
): () => void {
  const q = sessionId ? `?id=${encodeURIComponent(sessionId)}` : "";
  let es: EventSource | null = null;
  let everOpened = false;
  try {
    es = new EventSource(`${API_BASE}/api/stream${q}`);
  } catch {
    onState(false);
    return () => {};
  }
  es.addEventListener("open", () => {
    everOpened = true;
    onState(true);
  });
  es.addEventListener("dashboard", (e) => {
    try {
      onView(JSON.parse((e as MessageEvent).data) as DashboardView);
      onState(true);
    } catch {
      /* ignore malformed frame */
    }
  });
  es.addEventListener("error", () => {
    // EventSource auto-reconnects. After a successful open, a transient error is
    // just the browser re-establishing the stream — do NOT report a disconnect
    // (that would trigger the polling fallback and cause request "blinking").
    // Only surface failure if the stream never opened at all.
    if (!everOpened) onState(false);
  });
  return () => es?.close();
}

