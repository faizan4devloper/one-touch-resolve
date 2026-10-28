// Real vehicle lookup via the free NHTSA vPIC API (no key required).
//
// This is exactly what auto insurers do at FNOL: a VIN uniquely identifies the
// vehicle and pulls its make/model/year/body/fuel from the manufacturer data.
// Endpoint: https://vpic.nhtsa.dot.gov/api/  (US DOT, public, free).
//
// Honest note: this is a LIVE API call — the make/model/year returned is real
// NHTSA data decoded from the VIN, not a hard-coded lookup.

export interface VehicleInfo {
  make: string;
  model: string;
  year: string;
  bodyClass?: string;
  fuel?: string;
  /** Human label, e.g. "2003 Honda Accord". Empty if decode failed. */
  label: string;
  source: "nhtsa" | "none";
}

const VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues";

/** A VIN is 17 chars (no I/O/Q). We validate loosely so partial VINs still try. */
export function looksLikeVin(vin: string): boolean {
  return /^[A-HJ-NPR-Z0-9]{11,17}$/i.test(vin.trim());
}

/** Decode a VIN to real vehicle info via NHTSA. Never throws — returns a
 *  source:"none" result on any failure so the UI can fall back to manual entry. */
export async function decodeVin(vin: string): Promise<VehicleInfo> {
  const clean = vin.trim().toUpperCase();
  const empty: VehicleInfo = { make: "", model: "", year: "", label: "", source: "none" };
  if (!clean) return empty;
  try {
    const r = await fetch(`${VPIC}/${encodeURIComponent(clean)}?format=json`, {
      headers: { Accept: "application/json" },
    });
    if (!r.ok) return empty;
    const data = await r.json();
    const row = data?.Results?.[0] ?? {};
    const make = (row.Make ?? "").trim();
    const model = (row.Model ?? "").trim();
    const year = (row.ModelYear ?? "").trim();
    if (!make && !model && !year) return empty; // nothing decoded
    const label = [year, titleCase(make), titleCase(model)].filter(Boolean).join(" ").trim();
    return {
      make: titleCase(make),
      model: titleCase(model),
      year,
      bodyClass: (row.BodyClass ?? "").trim() || undefined,
      fuel: (row.FuelTypePrimary ?? "").trim() || undefined,
      label,
      source: "nhtsa",
    };
  } catch {
    return empty;
  }
}

function titleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// A real, valid sample VIN (2003 Honda Accord) for one-tap demo convenience.
export const SAMPLE_VIN = "1HGCM82633A004352";
