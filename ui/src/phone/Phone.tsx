import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Lock, ShieldCheck, Car, Truck, Camera, Wrench, Mail, Activity, AlertTriangle, MapPin, Search,
} from "lucide-react";
import { IPhoneFrame } from "./IPhoneFrame";
import { useSession } from "../SessionContext";
import { decodeVin, looksLikeVin, SAMPLE_VIN } from "./vehicle";
import { getDeviceLocation } from "./geo";
import { AccidentMap } from "../components/AccidentMap";
import {
  startSession,
  respond,
  subscribe,
  uploadPhoto,
  type Msg,
  type Session,
  type TowView,
} from "./api";

const SCENARIOS = [
  {
    label: "Severe crash \u00b7 tow",
    value:
      "Head-on collision at speed, front end destroyed, airbags deployed, fluid leaking, car cannot move",
  },
  {
    label: "Minor bump \u00b7 repair",
    value: "Rear-end bump at a stoplight, minor rear bumper scuff, car drives fine",
  },
  {
    label: "Side impact \u00b7 moderate",
    value: "Side collision, door dented and mirror broken, drivable but damaged",
  },
];

function clockOf(ts: number) {
  const d = ts ? new Date(ts * 1000) : new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function isPositive(choice: string) {
  return /^(y|okay|great|safe|we're|photo|done)/i.test(choice) && !/(not|no,)/i.test(choice);
}

export default function Phone() {
  const { setSessionId } = useSession();
  const [started, setStarted] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [visible, setVisible] = useState<Msg[]>([]);
  const [typing, setTyping] = useState(false);
  const [choices, setChoices] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const threadRef = useRef<HTMLDivElement>(null);
  const unsubRef = useRef<(() => void) | null>(null);
  // Ids already rendered (server message ids + synthetic tow-stage ids), so we
  // never double-render regardless of whether an update arrives via respond()
  // or via the SSE `session`/`dashboard` push.
  const seenRef = useRef<Set<string>>(new Set());
  const towStageRef = useRef(-1);
  const animatingRef = useRef(false);

  // Start form — blank so a new user enters THEIR own details (personalized).
  const [name, setName] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [location, setLocation] = useState("");
  const [scenario, setScenario] = useState(SCENARIOS[0].value);
  // Free-text description — when non-empty it OVERRIDES the preset and is sent
  // straight to the real Bedrock triage (proves the AI isn't scripted).
  const [customDesc, setCustomDesc] = useState("");

  // Real vehicle lookup (NHTSA vPIC) + real device GPS (Geolocation + OSM).
  const [vin, setVin] = useState("");
  const [vinBusy, setVinBusy] = useState(false);
  const [vinNote, setVinNote] = useState("");
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoNote, setGeoNote] = useState("");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [startError, setStartError] = useState("");

  const onDecodeVin = useCallback(async () => {
    if (vinBusy) return;
    setVinBusy(true);
    setVinNote("");
    const info = await decodeVin(vin);
    if (info.source === "nhtsa" && info.label) {
      setVehicle(info.label);
      setVinNote(`✓ NHTSA: ${info.label}${info.fuel ? ` · ${info.fuel}` : ""}`);
    } else {
      setVinNote("Couldn't decode that VIN — type your vehicle instead.");
    }
    setVinBusy(false);
  }, [vin, vinBusy]);

  const onUseLocation = useCallback(async () => {
    if (geoBusy) return;
    setGeoBusy(true);
    setGeoNote("");
    const g = await getDeviceLocation();
    if (g.source === "gps") {
      setLocation(g.address);
      setCoords({ lat: g.lat, lng: g.lng });
      setGeoNote(`✓ Live GPS · ${g.lat.toFixed(4)}, ${g.lng.toFixed(4)}`);
    } else {
      setGeoNote(g.error || "Location unavailable — type it instead.");
    }
    setGeoBusy(false);
  }, [geoBusy]);

  const scrollDown = useCallback(() => {
    requestAnimationFrame(() => {
      const el = threadRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  // Merge the server's authoritative message list into the view. Only messages
  // whose id we haven't seen are appended; agent messages get a typing beat.
  // Guarded by animatingRef so overlapping calls (respond + SSE) don't interleave.
  const mergeServer = useCallback(
    async (msgs: Msg[]) => {
      if (animatingRef.current) return;
      animatingRef.current = true;
      try {
        for (const m of msgs) {
          const id = m.id ?? `${m.sender}-${m.ts}-${m.text.slice(0, 12)}`;
          if (seenRef.current.has(id)) continue;
          seenRef.current.add(id);
          if (m.sender === "agent") {
            setChoices([]);
            setTyping(true);
            await sleep(600);
            setTyping(false);
          }
          setVisible((prev) => [...prev, { ...m, id }]);
          scrollDown();
          await sleep(110);
        }
      } finally {
        animatingRef.current = false;
      }
    },
    [scrollDown]
  );

  const syncSession = useCallback(
    async (s: Session) => {
      setSession(s);
      await mergeServer(s.messages);
      setChoices(s.awaiting ? lastChoices(s) : []);
    },
    [mergeServer]
  );

  const onStart = useCallback(async () => {
    if (busy || started) return;
    setBusy(true);
    setStartError("");
    setStarted(true);
    try {
      const s = await startSession({
        name,
        vehicle,
        location,
        description: customDesc.trim() || scenario,
      });
      // Publish the active session id via context so the operator view (split
      // demo) pins to the same claim — no sessionStorage, no polling.
      setSessionId(s.session_id);
      await syncSession(s);
      // One subscription for the session's lifetime. Close any prior one first
      // (guards StrictMode double-invoke and re-taps).
      unsubRef.current?.();
      unsubRef.current = subscribe(s.session_id, {
        onSession: (srv) => {
          void syncSession(srv);
        },
        onTow: (t) => handleTow(t),
      });
    } catch (e) {
      // Backend not ready / transient 503 — revert to the form with a clear note.
      setStarted(false);
      setStartError(e instanceof Error ? e.message : "Couldn't start — please retry.");
    } finally {
      setBusy(false);
    }
  }, [busy, started, name, vehicle, location, scenario, customDesc, syncSession, setSessionId]);

  const onAnswer = useCallback(
    async (answer: string) => {
      if (!session || busy) return;
      setBusy(true);
      setChoices([]);
      // No optimistic echo: the server list (via respond() and/or the SSE
      // `session` push) is the single source of truth, deduped by message id in
      // mergeServer(). This structurally prevents the tap from rendering twice
      // (one optimistic + one server copy). The tap already gives feedback by
      // clearing the reply buttons; the server echo lands within ~100ms.
      try {
        const s = await respond(session.session_id, answer);
        await syncSession(s);
      } finally {
        setBusy(false);
      }
    },
    [session, busy, syncSession, scrollDown]
  );

  // Real damage-photo upload: read the chosen/captured image, show it in the
  // chat, upload it for REAL Nova Pro vision triage, then advance the journey.
  const fileRef = useRef<HTMLInputElement>(null);
  const onPickPhoto = useCallback(
    async (file: File) => {
      if (!session || busy) return;
      setBusy(true);
      setChoices([]);
      try {
        const dataUrl: string = await new Promise((resolve, reject) => {
          const fr = new FileReader();
          fr.onload = () => resolve(String(fr.result));
          fr.onerror = reject;
          fr.readAsDataURL(file);
        });
        // Show the customer's real photo in the thread immediately.
        const pid = `photo-${Date.now()}`;
        seenRef.current.add(pid);
        setVisible((v) => [
          ...v,
          { id: pid, sender: "customer", text: "📷 [damage photo]", choices: [], kind: "photo", ts: Date.now() / 1000, image: dataUrl } as Msg,
        ]);
        scrollDown();
        setTyping(true);
        // Upload for real vision triage, then advance with the "Photo sent" tap.
        await uploadPhoto(session.session_id, dataUrl, file.type || "image/jpeg");
        setTyping(false);
        const s = await respond(session.session_id, "Photo sent");
        await syncSession(s);
      } finally {
        setTyping(false);
        setBusy(false);
      }
    },
    [session, busy, syncSession, scrollDown]
  );

  const handleTow = useCallback(
    (t: TowView) => {
      if (!t.active || typeof t.stage !== "number") return;
      if (t.stage <= towStageRef.current) return;
      towStageRef.current = t.stage;
      const id = `tow-${t.stage}`;
      if (seenRef.current.has(id)) return;
      seenRef.current.add(id);
      const label = t.arrived
        ? `${t.text}`
        : `${t.text}${t.eta_remaining_min ? ` · ETA ${t.eta_remaining_min} min` : ""}`;
      setVisible((v) => [...v, { id, sender: "system", text: label, choices: [], kind: "tow", ts: 0 }]);
      scrollDown();
    },
    [scrollDown]
  );

  useEffect(() => () => unsubRef.current?.(), []);

  const conversationDone = useMemo(
    () => session?.step === "DONE" && choices.length === 0,
    [session, choices]
  );

  return (
    <IPhoneFrame>
      <div className="phone">
        <header className="bar">
          <div className="avatar">AA</div>
          <div className="who">
            <div className="name">Accident Assist</div>
            <div className="pres">
              <span className="live" /> zero-call · online
            </div>
          </div>
          <Lock size={15} className="hdr-ic" />
        </header>

        <main ref={threadRef} className="thread">
          <div className="daynote">Today · end-to-end encrypted · you only tap Yes / No</div>
          <AnimatePresence initial={false}>
            {visible.map((m) => (
              <motion.div
                key={m.id}
                className={m.sender === "system" ? `system ${m.kind}` : `msg ${m.sender}`}
                initial={{ opacity: 0, y: 10, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 460, damping: 30, mass: 0.7 }}
              >
                {m.sender === "system" ? (
                  <span className="sys-row">
                    <SystemIcon kind={m.kind} />
                    <span>{m.text}</span>
                  </span>
                ) : m.image ? (
                  <>
                    <img className="msg-photo" src={m.image} alt="damage" />
                    <span className="t">{clockOf(m.ts)}</span>
                  </>
                ) : (
                  <>
                    {m.text}
                    <span className="t">{clockOf(m.ts)}</span>
                  </>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          <AnimatePresence>
            {typing && (
              <motion.div
                className="typing"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <i />
                <i />
                <i />
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        <footer className="replies">
          {choices.length === 1 && choices[0] === "Photo sent" ? (
            <>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                capture="environment"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onPickPhoto(f);
                  e.currentTarget.value = "";
                }}
              />
              <motion.button
                className="qr primary full"
                onClick={() => fileRef.current?.click()}
                disabled={busy}
                whileTap={{ scale: 0.96 }}
              >
                <Camera size={16} strokeWidth={2.4} style={{ marginRight: 8, verticalAlign: "-3px" }} />
                {busy ? "Analyzing photo…" : "Take / upload damage photo"}
              </motion.button>
            </>
          ) : choices.length > 0 ? (
            choices.map((c) => (
              <motion.button
                key={c}
                className={
                  "qr" + (isPositive(c) ? " primary" : "") + (choices.length === 1 ? " full" : "")
                }
                onClick={() => onAnswer(c)}
                disabled={busy}
                whileTap={{ scale: 0.96 }}
              >
                {c}
              </motion.button>
            ))
          ) : (
            <div className="hint">
              {conversationDone
                ? "Conversation complete — check your email for the summary."
                : busy
                ? "…"
                : "Waiting for the assistant…"}
            </div>
          )}
        </footer>
      </div>

      <AnimatePresence>
        {!started && (
          <motion.div
            className="start"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: 0.3 }}
          >
            <motion.div
              className="start-card"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
            >
              <div className="brand">
                <span className="brand-mark">AA</span> One Touch Resolve
              </div>
              <p className="intro-tag">
                Simulate a car accident and watch the agent coordinate every party
                for you. <b>You only tap Yes / No</b> — no calls, no forms after this.
              </p>

              <div className="start-steps">
                <div className="start-step">
                  <span className="step-n">1</span>
                  <label>
                    Your name
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Enter your name"
                      autoComplete="name"
                    />
                  </label>
                </div>
                <div className="start-step">
                  <span className="step-n">2</span>
                  <label>
                    Your vehicle <span className="step-hint">VIN decodes via NHTSA (live)</span>
                    <div className="field-with-btn">
                      <input
                        value={vin}
                        onChange={(e) => { setVin(e.target.value); setVinNote(""); }}
                        placeholder="Enter VIN to auto-fill"
                        autoCapitalize="characters"
                      />
                      <button
                        type="button"
                        className="field-btn"
                        onClick={onDecodeVin}
                        disabled={vinBusy || !looksLikeVin(vin)}
                        title="Decode VIN via NHTSA"
                      >
                        <Search size={14} strokeWidth={2.3} />
                        {vinBusy ? "…" : "Decode"}
                      </button>
                    </div>
                    <input
                      style={{ marginTop: 7 }}
                      value={vehicle}
                      onChange={(e) => setVehicle(e.target.value)}
                      placeholder="…or type it: e.g. 2022 Toyota Camry"
                    />
                    {vinNote ? (
                      <span className="field-note">{vinNote}</span>
                    ) : (
                      <button type="button" className="field-link" onClick={() => setVin(SAMPLE_VIN)}>
                        Use a sample VIN
                      </button>
                    )}
                  </label>
                </div>
                <div className="start-step">
                  <span className="step-n">3</span>
                  <label>
                    Where are you? <span className="step-hint">live device GPS</span>
                    <div className="field-with-btn">
                      <input
                        value={location}
                        onChange={(e) => { setLocation(e.target.value); }}
                        placeholder="e.g. Market Street, San Francisco"
                      />
                      <button
                        type="button"
                        className="field-btn"
                        onClick={onUseLocation}
                        disabled={geoBusy}
                        title="Use my real GPS location"
                      >
                        <MapPin size={14} strokeWidth={2.3} />
                        {geoBusy ? "…" : "Locate"}
                      </button>
                    </div>
                    {geoNote && <span className="field-note">{geoNote}</span>}
                  </label>
                </div>
                {coords && (
                  <div className="start-map">
                    <AccidentMap lat={coords.lat} lng={coords.lng} etaMin={8} />
                  </div>
                )}
                <div className="start-step">
                  <span className="step-n">4</span>
                  <label>
                    What happened? <span className="step-hint">drives the live Bedrock triage</span>
                    <div className="scenario-chips">
                      {SCENARIOS.map((s) => (
                        <button
                          type="button"
                          key={s.label}
                          className={"scenario-chip" + (!customDesc.trim() && scenario === s.value ? " active" : "")}
                          onClick={() => { setScenario(s.value); setCustomDesc(""); }}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                    <textarea
                      className="scenario-text"
                      value={customDesc}
                      onChange={(e) => setCustomDesc(e.target.value)}
                      placeholder="…or describe it in your own words — the real AI will triage what you write"
                      rows={2}
                    />
                    {customDesc.trim() && (
                      <span className="field-note">✓ Using your description for live AI triage</span>
                    )}
                  </label>
                </div>
              </div>

              <div className="chips">
                <span className="chip">
                  <ShieldCheck size={13} /> Bedrock triage
                </span>
                <span className="chip">
                  <Truck size={13} /> Live tow ETA
                </span>
                <span className="chip">
                  <Car size={13} /> SES summary
                </span>
              </div>

              {startError && <p className="start-error">{startError}</p>}
              <button className="cta" onClick={onStart} disabled={busy}>
                <Camera size={17} strokeWidth={2.4} />
                {busy ? "Connecting…" : "Start — the agent will message you"}
              </button>
              <p className="fine">
                Next: the agent texts you on WhatsApp and guides you with Yes/No taps ·
                real Amazon Bedrock triage · real email summary via Amazon SES
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </IPhoneFrame>
  );
}

// helpers -------------------------------------------------------------------
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function SystemIcon({ kind }: { kind: string }) {
  const common = { size: 14, strokeWidth: 2.2 };
  switch (kind) {
    case "tow":
      return <Truck {...common} />;
    case "rental":
      return <Car {...common} />;
    case "repair":
      return <Wrench {...common} />;
    case "summary":
      return <Mail {...common} />;
    case "safety":
      return <AlertTriangle {...common} />;
    default:
      return <Activity {...common} />;
  }
}

function lastChoices(s: Session): string[] {
  for (let i = s.messages.length - 1; i >= 0; i--) {
    if (s.messages[i].choices?.length) return s.messages[i].choices;
  }
  return [];
}
