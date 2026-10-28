import type { ChannelKind } from "../data";
import { ChannelLogo } from "./ChannelLogo";

const LABEL: Record<ChannelKind, string> = {
  whatsapp: "WhatsApp",
  rcs: "RCS",
  sms: "SMS",
  email: "Email",
};

// System/status timeline rows have no channel; render nothing in that case.
// `compact` renders the logo only (no text label) to save horizontal space in
// dense rows like the party roster.
export function ChannelTag({ channel, compact = false }: { channel: ChannelKind | ""; compact?: boolean }) {
  if (!channel) return null;
  return (
    <span className={compact ? "chtag chtag-compact" : "chtag"} title={LABEL[channel]}>
      <ChannelLogo channel={channel} size={13} />
      {!compact && LABEL[channel]}
    </span>
  );
}
