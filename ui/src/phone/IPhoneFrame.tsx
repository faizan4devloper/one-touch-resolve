import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Signal, Wifi, BatteryFull } from "lucide-react";
import { DeviceFrameset } from "react-device-frameset";
import "react-device-frameset/styles/marvel-devices.min.css";

// The iPhone X frameset renders a fixed 375 x 812 screen. We compute a zoom so
// the whole device (incl. its bezel) fits the available viewport — this is the
// battle-tested library sizing model, so it never squishes/clips like a
// hand-rolled frame. Bezel ≈ 20px each side, so device ≈ 415 x 852.
const SCREEN_W = 375;
const SCREEN_H = 812;
// The marvel iPhone X frameset draws a bezel beyond the screen: ~22px each side
// and ~24px top/bottom. Use generous outer dimensions so the fit calc never
// lets the device overflow the viewport.
const DEVICE_W = 375 + 44;
const DEVICE_H = 812 + 48;

export function IPhoneFrame({ children }: { children: React.ReactNode }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);
  const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });

  useLayoutEffect(() => {
    const compute = () => {
      // Size to the frame's own container when available (so it fits inside a
      // split-screen column), falling back to the visible viewport otherwise.
      const host = stageRef.current?.parentElement ?? stageRef.current;
      const rect = host?.getBoundingClientRect();
      const vh = rect?.height || window.visualViewport?.height || window.innerHeight;
      const vw = rect?.width || window.visualViewport?.width || window.innerWidth;
      // Account for stage padding and the frameset's bezel beyond the screen.
      const availH = vh - 8;
      const availW = vw - 8;
      const z = Math.min(availH / DEVICE_H, availW / DEVICE_W, 1.55);
      setZoom(Math.max(0.42, z));
    };
    compute();
    // Recompute on viewport resize AND when the container resizes (split panes).
    window.addEventListener("resize", compute);
    window.visualViewport?.addEventListener("resize", compute);
    let ro: ResizeObserver | undefined;
    const host = stageRef.current?.parentElement;
    if (host && "ResizeObserver" in window) {
      ro = new ResizeObserver(compute);
      ro.observe(host);
    }
    return () => {
      window.removeEventListener("resize", compute);
      window.visualViewport?.removeEventListener("resize", compute);
      ro?.disconnect();
    };
  }, []);

  return (
    <div className="ip-stage" ref={stageRef}>
      <DeviceFrameset device="iPhone X" width={SCREEN_W} height={SCREEN_H} zoom={zoom}>
        <div className="ip-app">
          {/* iOS status bar */}
          <div className="ip-status">
            <span className="ip-time">{time}</span>
            <div className="ip-status-right">
              <Signal size={15} strokeWidth={2.4} />
              <Wifi size={15} strokeWidth={2.4} />
              <BatteryFull size={22} strokeWidth={1.8} />
            </div>
          </div>
          {children}
        </div>
      </DeviceFrameset>
    </div>
  );
}
