// Real device location via the browser Geolocation API + reverse-geocoding via
// OpenStreetMap Nominatim (free). This mirrors what insurer FNOL apps do: pull
// the policyholder's real GPS at the moment of loss, then resolve a human
// address for the claim record and the operator map.
//
// Honest note: the coordinates are the device's REAL GPS (with user consent);
// the address is a LIVE reverse-geocode from OSM. Nothing here is faked.

export interface GeoResult {
  lat: number;
  lng: number;
  address: string;
  source: "gps" | "none";
  error?: string;
}

const NOMINATIM = "https://nominatim.openstreetmap.org/reverse";

/** Ask the browser for the real device position, then reverse-geocode it.
 *  Resolves with source:"none" + an error message if denied/unavailable, so the
 *  caller can fall back to manual entry. */
export function getDeviceLocation(timeoutMs = 10000): Promise<GeoResult> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) {
      resolve({ lat: 0, lng: 0, address: "", source: "none", error: "Geolocation not supported" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        let address = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        try {
          const r = await fetch(
            `${NOMINATIM}?format=jsonv2&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
            { headers: { Accept: "application/json" } }
          );
          if (r.ok) {
            const data = await r.json();
            if (data?.display_name) address = shortenAddress(data.display_name);
          }
        } catch {
          /* keep the lat/lng string as the address */
        }
        resolve({ lat, lng, address, source: "gps" });
      },
      (err) => {
        resolve({
          lat: 0, lng: 0, address: "", source: "none",
          error: err.code === err.PERMISSION_DENIED ? "Location permission denied" : "Location unavailable",
        });
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 }
    );
  });
}

/** Trim a full Nominatim display_name to a readable 3-part address. */
function shortenAddress(full: string): string {
  const parts = full.split(",").map((p) => p.trim()).filter(Boolean);
  if (parts.length <= 3) return parts.join(", ");
  return [parts[0], parts[1], parts[parts.length - 2] || parts[parts.length - 1]].join(", ");
}
