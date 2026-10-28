import { useEffect, useRef, useState } from "react";
import { Truck, MapPin } from "lucide-react";

/**
 * Real OpenStreetMap view of the accident location with an animated tow marker.
 *
 * HONEST LABELING:
 *  - The MAP and the ACCIDENT PIN are real: an OSM embed centered on the live
 *    GPS coordinates captured from the policyholder's device.
 *  - The TOW TRUCK marker is SIMULATED — it animates toward the accident to
 *    visualize the ETA. A production build would stream the tow operator's real
 *    GPS (Geotab/Samsara) here; a hackathon demo can't access a live tow fleet.
 */
export function AccidentMap({
  lat,
  lng,
  etaMin,
  arrived,
}: {
  lat: number;
  lng: number;
  etaMin?: number | null;
  arrived?: boolean;
}) {
  // bbox around the accident for the OSM embed (real tiles, real location).
  const d = 0.012;
  const bbox = `${lng - d}%2C${lat - d}%2C${lng + d}%2C${lat + d}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`;

  // Simulated tow progress 0→1 (drives the marker toward the pin). When arrived,
  // snap to the pin. Otherwise ease from a corner toward center over the ETA.
  const [t, setT] = useState(0);
  const raf = useRef<number | null>(null);
  useEffect(() => {
    if (arrived) { setT(1); return; }
    const total = Math.max(8, (etaMin ?? 8) * 1.2); // seconds of visible travel
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(0.92, (now - start) / 1000 / total); // never fully reach until arrived
      setT(p);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [etaMin, arrived]);

  // Tow marker travels from top-left toward the center pin.
  const towLeft = 12 + t * (50 - 12);
  const towTop = 14 + t * (50 - 14);

  return (
    <div className="amap">
      <iframe
        className="amap-frame"
        title="Accident location"
        src={src}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      {/* Accident pin (real coords, center) */}
      <span className="amap-pin amap-accident" style={{ left: "50%", top: "50%" }}>
        <MapPin size={20} strokeWidth={2.4} />
      </span>
      {/* Simulated tow marker moving toward the pin */}
      {!arrived && (
        <span className="amap-pin amap-tow" style={{ left: `${towLeft}%`, top: `${towTop}%` }}>
          <Truck size={16} strokeWidth={2.4} />
        </span>
      )}
      <div className="amap-cap">
        <span className="amap-live">● Live OSM · real GPS pin</span>
        <span className="amap-sim">
          {arrived ? "tow arrived" : `tow en route · ETA ${etaMin ?? "—"} min (simulated)`}
        </span>
      </div>
    </div>
  );
}
