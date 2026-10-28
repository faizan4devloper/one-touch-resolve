// ZCAA phone API client — talks to the same zcaa/api.py backend as the dashboard.

export type Sender = "agent" | "customer" | "system";

export interface Msg {
  id?: string;
  sender: Sender;
  text: string;
  choices: string[];
  kind: string; // text | status | safety | tow | rental | repair | summary | photo
  ts: number;
  image?: string; // data URL for a customer-sent damage photo
}

export interface Session {
  session_id: string;
  customer_name: string;
  policy_number: string;
  location: string;
  vehicle: string;
  step: string;
  facts: Record<string, any>;
  awaiting: boolean;
  messages: Msg[];
}

export interface TowView {
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
  tow?: TowView;
}

const BASE = "";

async function post<T>(path: string, body: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the service. Please retry in a moment.");
  }
  // During a backend restart the proxy can return a 503 HTML page. Don't blindly
  // JSON.parse it (that throws the cryptic "Unexpected token '<'"); surface a
  // clean, retryable error instead.
  if (!r.ok) {
    throw new Error(
      r.status === 503
        ? "Service is starting up — please retry in a few seconds."
        : `Request failed (${r.status}). Please retry.`
    );
  }
  const ct = r.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    throw new Error("Service is starting up — please retry in a few seconds.");
  }
  return (await r.json()) as T;
}

export interface StartInput {
  name: string;
  vehicle: string;
  location: string;
  description: string;
  policy?: string;
  phone?: string;
}

export function startSession(input: StartInput): Promise<Session> {
  return post<Session>("/api/start", {
    policy: "HO-8842190",
    phone: "+15555550100",
    ...input,
  });
}

export function respond(sessionId: string, answer: string): Promise<Session> {
  return post<Session>("/api/respond", { session_id: sessionId, answer });
}

// Upload a real damage photo (data URL) for Nova Pro VISION triage.
export function uploadPhoto(
  sessionId: string,
  dataUrl: string,
  contentType: string
): Promise<{ ok: boolean; triage: Record<string, any> }> {
  return post("/api/upload", { session_id: sessionId, image: dataUrl, content_type: contentType });
}

// Realtime: subscribe to Server-Sent Events for this session. The server pushes
// `session` (full chat) and `dashboard` (tow tracking) events on every change.
export function subscribe(
  sessionId: string,
  handlers: { onSession?: (s: Session) => void; onTow?: (t: TowView) => void }
): () => void {
  let es: EventSource | null = null;
  try {
    es = new EventSource(`${BASE}/api/stream?id=${encodeURIComponent(sessionId)}`);
  } catch {
    return () => {};
  }
  es.addEventListener("session", (e) => {
    try {
      handlers.onSession?.(JSON.parse((e as MessageEvent).data) as Session);
    } catch {
      /* ignore */
    }
  });
  es.addEventListener("dashboard", (e) => {
    try {
      const v = JSON.parse((e as MessageEvent).data) as DashboardView;
      if (v.tow) handlers.onTow?.(v.tow);
    } catch {
      /* ignore */
    }
  });
  return () => es?.close();
}
