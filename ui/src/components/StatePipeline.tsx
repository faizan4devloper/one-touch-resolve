import { motion } from "motion/react";
import type { ClaimState } from "../data";
import { CLAIM_STATES } from "../data";

export function StatePipeline({ current }: { current: ClaimState }) {
  const idx = CLAIM_STATES.indexOf(current);
  return (
    <div className="pipeline">
      {CLAIM_STATES.map((s, i) => {
        const cls = i < idx ? "st done" : i === idx ? "st active" : "st";
        return (
          <div key={s} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <motion.span
              className={cls}
              animate={{ scale: i === idx ? 1.04 : 1 }}
              transition={{ type: "spring", stiffness: 420, damping: 30 }}
            >
              {s.replace(/_/g, " ")}
            </motion.span>
            {i < CLAIM_STATES.length - 1 && (
              <span className="seg">
                <motion.span
                  className="seg-fill"
                  initial={false}
                  animate={{ scaleX: i < idx ? 1 : 0 }}
                  transition={{ duration: 0.45, ease: [0.22, 0.61, 0.36, 1] }}
                />
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
