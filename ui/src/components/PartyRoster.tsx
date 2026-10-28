import { User, Wrench, Package, Landmark, ShieldCheck, Truck, Car } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { Party } from "../data";
import { ChannelTag } from "./ChannelTag";

// Live ZCAA statuses are free-form (safe, engaged, dispatched, reserved,
// booked) as well as the classic commit-gate ones (committed, blocked,
// notified, pending). Map each to a colour token, defaulting gracefully.
function statusStyle(status: string): { color: string; soft: string; label: string } {
  const s = status.toLowerCase();
  if (["committed", "booked", "reserved", "safe", "confirmed"].includes(s))
    return { color: "var(--ok)", soft: "var(--ok-soft)", label: s };
  if (["blocked", "failed"].includes(s))
    return { color: "var(--blocked)", soft: "var(--blocked-soft)", label: s };
  if (["dispatched", "engaged", "notified", "awaiting"].includes(s))
    return { color: "var(--wait)", soft: "var(--wait-soft)", label: s === "notified" ? "awaiting" : s };
  return { color: "var(--ink-4)", soft: "var(--surface-2)", label: s || "pending" };
}

const ROLE_ICON: Record<string, typeof User> = {
  claimant: User,
  repair_shop: Wrench,
  parts_supplier: Package,
  lienholder: Landmark,
  adjuster: ShieldCheck,
  roadside: Truck,
  rental: Car,
};

export function PartyRoster({ parties }: { parties: Party[] }) {
  if (!parties || parties.length === 0)
    return <p className="empty">Awaiting first notice of loss…</p>;
  return (
    <ul className="roster">
      <AnimatePresence initial={false}>
        {parties.map((p) => {
          const st = statusStyle(p.status);
          const Icon = ROLE_ICON[p.role] ?? User;
          return (
            <motion.li
              className="party"
              key={p.role}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.3, ease: [0.22, 0.61, 0.36, 1] }}
            >
              <div className="who">
                <span className="role-ic" style={{ color: st.color, background: st.soft, transition: "color .35s ease, background .35s ease" }}>
                  <Icon size={15} strokeWidth={2.1} />
                </span>
                <div style={{ minWidth: 0 }}>
                  <div className="name">{p.name || p.role.replace(/_/g, " ")}</div>
                  <div className="note">{p.note}</div>
                </div>
              </div>
              <div className="right">
                <ChannelTag channel={p.channel} compact />
                <span className="pstatus" style={{ color: st.color, background: st.soft, transition: "color .35s ease, background .35s ease" }}>
                  <span className="pstatus-dot" style={{ background: st.color }} />
                  {st.label}
                </span>
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}
