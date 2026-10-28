import Phone from "../phone/Phone";
import Operator from "../App";
import { useSession } from "../SessionContext";
import "./demo.css";

/**
 * Staged demo layout:
 *   1. BEFORE anything happens → the phone sits CENTERED alone (no empty
 *      operator panel staring back).
 *   2. The moment the customer starts the accident (a session id appears), the
 *      phone slides to the LEFT and the operator "Mission Control" panel slides
 *      in on the right — the classic "watch both sides" reveal.
 *
 * The active session id flows through SessionContext (the phone sets it on
 * start; the operator reads it). `started` is simply "do we have a session yet".
 */
export default function Demo({ onExit }: { onExit: () => void }) {
  const { sessionId } = useSession();
  const started = Boolean(sessionId);

  return (
    <div className="demo-root">
      {/* Exit is always reachable, even before the split appears. */}
      {!started && (
        <button className="demo-exit" onClick={onExit} title="Back to start">
          Exit
        </button>
      )}

      <div className={`demo-split${started ? " is-split" : " is-centered"}`}>
        {/* LEFT — customer phone (centered until a session starts) */}
        <section className="pane pane-phone">
          <div className="phone-host">
            <Phone />
          </div>
        </section>

        {/* RIGHT — operator web, revealed once the claim is live */}
        <section className="pane pane-web" aria-hidden={!started}>
          <div className="web-host">
            {started && (
              /* key forces a clean remount when a new session starts, so the
                 operator view re-pins to the latest claim. */
              <Operator key={sessionId ?? "idle"} embedded sessionId={sessionId} onExit={onExit} />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
