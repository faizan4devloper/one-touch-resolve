import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Lock, ShieldCheck, Car, Truck, Camera, Wrench, Mail, Activity, AlertTriangle, MapPin, Search,
} from "lucide-react";
import { IPhoneFrame } from "./IPhoneFrame";
import { useSession } from "../SessionContext";
import { decodeVin, looksLikeVin } from "./vehicle";
import { getDeviceLocation } from "./geo";
import { nearbyRepairShops, drivingEtaMin, type Shop } from "./nearby";
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

  // Start form — pre-filled with a sample demo persona for a one-tap start.
  // A sample VIN (2003 Honda Accord) so "Decode VIN" works out of the box.
  const [name, setName] = useState("Alex Rivera");
  const [vehicle, setVehicle] = useState("1HGCM82633A004352");
  const [location, setLocation] = useState("Market Street, San Francisco");
  const [scenario, setScenario] = useState(SCENARIOS[0].value);
  // Free-text description — when non-empty it OVERRIDES the preset and is sent
  // straight to the real Bedrock triage (proves the AI isn't scripted).
  const [customDesc, setCustomDesc] = useState("");

  // Real vehicle lookup (NHTSA vPIC) + real device GPS (Geolocation + OSM).
  const [vinBusy, setVinBusy] = useState(false);
  const [vinNote, setVinNote] = useState("");
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoNote, setGeoNote] = useState("");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [startError, setStartError] = useState("");
  // Real location-aware data (no static vendors): nearby shops + real ETA.
  const [shops, setShops] = useState<Shop[]>([]);
  const [shopsBusy, setShopsBusy] = useState(false);
  const [etaMin, setEtaMin] = useState<number | null>(null);

  const onDecodeVin = useCallback(async () => {
    if (vinBusy) return;
    setVinBusy(true);
    setVinNote("");
    const info = await decodeVin(vehicle);
    if (info.source === "nhtsa" && info.label) {
      setVehicle(info.label);
      setVinNote(`✓ NHTSA: ${info.label}${info.fuel ? ` · ${info.fuel}` : ""}`);
    } else {
      setVinNote("Couldn't decode that VIN — type your vehicle instead.");
    }
    setVinBusy(false);
  }, [vehicle, vinBusy]);

  const onUseLocation = useCallback(async () => {
    if (geoBusy) return;
    setGeoBusy(true);
    setGeoNote("");
    const g = await getDeviceLocation();
    if (g.source === "gps") {
      setLocation(g.address);
      setCoords({ lat: g.lat, lng: g.lng });
      setGeoNote(`✓ Live GPS · ${g.lat.toFixed(4)}, ${g.lng.toFixed(4)}`);
      // Real location-aware lookups keyed off the captured GPS. No fake fallback:
      // on failure the lists stay empty and the UI says so honestly.
      setShopsBusy(true);
      const found = await nearbyRepairShops(g.lat, g.lng);
      setShops(found);
      if (found[0]) {
        const eta = await drivingEtaMin({ lat: found[0].lat, lng: found[0].lng }, { lat: g.lat, lng: g.lng });
        setEtaMin(eta);
      }
      setShopsBusy(false);
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
        // Upload for real vision triage. The model first validates the image is
        // a vehicle; if not, we reject honestly and let the user re-upload.
        const res = await uploadPhoto(session.session_id, dataUrl, file.type || "image/jpeg");
        setTyping(false);
        const triage = (res && (res as any).triage) || {};
        if (triage.valid === false) {
          // Invalid / irrelevant image — do NOT advance. Show the agent's reason
          // and keep the photo step open so the user can send a real one.
          const rid = `reject-${Date.now()}`;
          seenRef.current.add(rid);
          setVisible((v) => [
            ...v,
            {
              id: rid, sender: "agent", kind: "safety", ts: Date.now() / 1000, choices: [],
              text: (triage.reject_reason || "That doesn't look like a photo of your vehicle.") +
                    " Please share a clear photo of the damage.",
            } as Msg,
          ]);
          setChoices(["Photo sent"]); // keep the upload action available for retry
          scrollDown();
          return; // stay on the photo step
        }
        // Valid vehicle photo — advance the journey.
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
                Simulate an accident — the agent coordinates everything. You just tap Yes / No.
              </p>

              <div className="start-steps">
                <div className="start-step">
                  <label>
                    Name
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your name"
                      autoComplete="name"
                    />
                  </label>
                </div>
                <div className="start-step">
                  <label>
                    Vehicle
                    <div className="field-with-btn">
                      <input
                        value={vehicle}
                        onChange={(e) => { setVehicle(e.target.value); setVinNote(""); }}
                        placeholder="VIN or make/model (e.g. 2022 Toyota Camry)"
                      />
                      <button
                        type="button"
                        className="field-btn"
                        onClick={onDecodeVin}
                        disabled={vinBusy || !looksLikeVin(vehicle)}
                        title="Decode VIN via NHTSA"
                      >
                        <Search size={14} strokeWidth={2.3} />
                        {vinBusy ? "…" : "Decode VIN"}
                      </button>
                    </div>
                    {vinNote && <span className="field-note">{vinNote}</span>}
                  </label>
                </div>
                <div className="start-step">
                  <label>
                    Location
                    <div className="field-with-btn">
                      <input
                        value={location}
                        onChange={(e) => { setLocation(e.target.value); }}
                        placeholder="Where are you?"
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
                    <AccidentMap lat={coords.lat} lng={coords.lng} etaMin={etaMin} />
                    <div className="nearby">
                      <div className="nearby-head">
                        Nearby repair shops <span className="nearby-src">· live OpenStreetMap</span>
                      </div>
                      {shopsBusy ? (
                        <ul className="nearby-list" aria-busy="true">
                          {[0, 1, 2].map((i) => (
                            <li key={i} className="nearby-skel">
                              <span className="skel-line skel-name" />
                              <span className="skel-line skel-st" />
                            </li>
                          ))}
                        </ul>
                      ) : shops.length > 0 ? (
                        <ul className="nearby-list">
                          {shops.map((s, i) => (
                            <li key={i}>
                              <span className="nearby-name">{s.name}</span>
                              {s.street && <span className="nearby-st">· {s.street}</span>}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="nearby-empty">No shops found nearby (or service unavailable).</div>
                      )}
                      {etaMin != null && (
                        <div className="nearby-eta">Real driving ETA to nearest shop: ~{etaMin} min <span className="nearby-src">· OSRM</span></div>
                      )}
                    </div>
                  </div>
                )}
                <div className="start-step">
                  <label>
                    What happened?
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
                      placeholder="…or describe it yourself (real AI triage)"
                      rows={2}
                    />
                    {customDesc.trim() && (
                      <span className="field-note">✓ Using your description for live AI triage</span>
                    )}
                  </label>
                </div>
              </div>

              {startError && <p className="start-error">{startError}</p>}
              <button className="cta" onClick={onStart} disabled={busy}>
                <Camera size={17} strokeWidth={2.4} />
                {busy ? "Connecting…" : "Start"}
              </button>
              <p className="fine">Real Amazon Bedrock triage · live SES email</p>
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
