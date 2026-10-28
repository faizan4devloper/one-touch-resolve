import { Lock, LockOpen } from "lucide-react";

export function GateIndicator({ open, reason }: { open: boolean; reason: string }) {
  const color = open ? "var(--ok)" : "var(--blocked)";
  const soft = open ? "var(--ok-soft)" : "var(--blocked-soft)";
  const Icon = open ? LockOpen : Lock;
  return (
    <div className="gate" style={{ background: soft, border: `1px solid ${color}33` }}>
      <div className="left">
        <Icon size={14} color={color} strokeWidth={2.3} />
        <span className="lbl" style={{ color }}>
          Commit gate {open ? "open" : "held"}
        </span>
      </div>
      <span className="reason">{reason}</span>
    </div>
  );
}
