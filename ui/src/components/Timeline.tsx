import { AnimatePresence, motion } from "motion/react";
import {
  FileImage, MousePointerClick, Radio, ShieldAlert, Truck, Car, Wrench,
  Mail, Activity, Send,
} from "lucide-react";
import type { StepKind, TimelineItem } from "../data";
import { ChannelTag } from "./ChannelTag";

type KindStyle = { Icon: typeof FileImage; color: string; soft: string; tag: string };

const KIND: Record<StepKind, KindStyle> = {
  tap: { Icon: MousePointerClick, color: "var(--run)", soft: "var(--run-soft)", tag: "consent" },
  text: { Icon: Radio, color: "var(--ch-rcs)", soft: "var(--brand-soft)", tag: "message" },
  status: { Icon: Activity, color: "var(--ink-3)", soft: "var(--surface-2)", tag: "status" },
  safety: { Icon: ShieldAlert, color: "var(--blocked)", soft: "var(--blocked-soft)", tag: "safety" },
  tow: { Icon: Truck, color: "var(--wait)", soft: "var(--wait-soft)", tag: "tow" },
  rental: { Icon: Car, color: "var(--brand-2)", soft: "var(--brand-soft)", tag: "rental" },
  repair: { Icon: Wrench, color: "var(--ok)", soft: "var(--ok-soft)", tag: "repair" },
  summary: { Icon: Mail, color: "var(--brand-2)", soft: "var(--brand-soft)", tag: "summary" },
  fanout: { Icon: Send, color: "var(--brand)", soft: "var(--brand-soft)", tag: "fan-out" },
};

const FALLBACK: KindStyle = {
  Icon: FileImage,
  color: "var(--ink-3)",
  soft: "var(--surface-2)",
  tag: "event",
};

export function Timeline({
  items,
  live,
}: {
  items: TimelineItem[];
  live: boolean;
}) {
  return (
    <div className={`timeline${items.length === 0 ? " is-empty" : ""}`}>
      {items.length > 0 && <div className="rail" />}
      <ul className="tl-list">
        <AnimatePresence initial={false}>
          {items.map((s, i) => {
            const k = KIND[s.kind as StepKind] ?? FALLBACK;
            const isLast = live && i === items.length - 1;
            const Icon = k.Icon;
            return (
              <motion.li
                key={`${i}-${s.text.slice(0, 12)}`}
                className="tl-item"
                layout
                initial={{ opacity: 0, y: 8, filter: "blur(2px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.32, ease: [0.22, 0.61, 0.36, 1] }}
              >
                <div className="tl-node">
                  <span
                    className="ring"
                    style={{
                      background: k.soft,
                      boxShadow: `0 0 0 3px var(--surface)${
                        isLast ? `, 0 0 0 5px ${k.color}22` : ""
                      }`,
                    }}
                  >
                    <Icon size={11} color={k.color} strokeWidth={2.4} />
                  </span>
                </div>
                <div className="tl-body">
                  <div className="tl-meta">
                    <span className="tl-actor">{s.actor}</span>
                    <span className="tl-kind" style={{ color: k.color, background: k.soft }}>
                      {k.tag}
                    </span>
                    {s.channel && <ChannelTag channel={s.channel} />}
                  </div>
                  <div className="tl-label">{s.text}</div>
                  {s.recipients && s.recipients.length > 0 && (
                    <div className="tl-recipients" aria-label="sent to">
                      {s.recipients.map((r) => (
                        <span className="tl-rcpt" key={r.role}>
                          <span className="tl-rcpt-role">{r.role.replace(/_/g, " ")}</span>
                          {r.channel && <ChannelTag channel={r.channel} compact />}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>

        {items.length === 0 && (
          <li className="tl-empty">
            <span className="tl-empty-ic">
              <Activity size={18} strokeWidth={2} />
            </span>
            <div className="tl-empty-title">Waiting for a customer</div>
            <div className="tl-empty-sub">
              Agent activity will stream here the moment a claim starts on the phone.
            </div>
          </li>
        )}
      </ul>
    </div>
  );
}
