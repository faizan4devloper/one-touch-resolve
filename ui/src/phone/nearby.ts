// Real, location-aware lookups keyed off the captured GPS — no static vendor data.
//
//  * nearbyRepairShops(lat,lng): REAL car-repair businesses from OpenStreetMap
//    via the Overpass API (free, no key). These are actual shops near the
//    accident, not fabricated names.
//  * drivingEtaMin(from,to): REAL driving time via OSRM (free, no key).
//
// HONEST BY DESIGN: both functions return empty/null on any failure (never a
// fake fallback). The UI shows an honest "no shops found / service unavailable"
// state instead of inventing data.

export interface Shop {
  name: string;
  street: string;
  lat: number;
  lng: number;
}

const OVERPASS_ENDPOINTS = [
  "https://overpass-api.de/api/interpreter",
  "https://overpass.kumi.systems/api/interpreter",
  "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
];
const OSRM = "https://router.project-osrm.org/route/v1/driving";

/** Real car-repair shops within ~6km of the point. Tries multiple real Overpass
 *  mirrors (a busy instance returns 406/429); returns [] only if all fail.
 *  No fabricated data is ever returned. */
export async function nearbyRepairShops(lat: number, lng: number, limit = 4): Promise<Shop[]> {
  const q =
    `[out:json][timeout:20];(` +
    `node["shop"="car_repair"](around:6000,${lat},${lng});` +
    `node["amenity"="car_repair"](around:6000,${lat},${lng});` +
    `);out body ${limit * 3};`;
  for (const endpoint of OVERPASS_ENDPOINTS) {
    try {
      const r = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "data=" + encodeURIComponent(q),
      });
      if (!r.ok) continue; // busy mirror -> try the next real one
      const ct = r.headers.get("content-type") || "";
      if (!ct.includes("json")) continue;
      const data = await r.json();
      const shops: Shop[] = (data.elements || [])
        .map((e: any) => ({
          name: (e.tags?.name || "").trim(),
          street: (e.tags?.["addr:street"] || e.tags?.["addr:full"] || "").trim(),
          lat: e.lat,
          lng: e.lon,
        }))
        .filter((s: Shop) => s.name)
        .slice(0, limit);
      if (shops.length) return shops;
    } catch {
      /* try next mirror */
    }
  }
  return []; // all mirrors unavailable — honest empty, never fabricated
}

/** Real driving ETA in minutes from `from` to `to`. null on failure. */
export async function drivingEtaMin(
  from: { lat: number; lng: number },
  to: { lat: number; lng: number }
): Promise<number | null> {
  try {
    const url = `${OSRM}/${from.lng},${from.lat};${to.lng},${to.lat}?overview=false`;
    const r = await fetch(url);
    if (!r.ok) return null;
    const d = await r.json();
    if (d.code !== "Ok" || !d.routes?.[0]) return null;
    return Math.max(1, Math.round(d.routes[0].duration / 60));
  } catch {
    return null;
  }
}
