// Real channel logos as inline SVG (official-style marks). Used in channel tags
// and message rows so channels are recognizable at a glance.
import type { ChannelKind } from "../data";

type Props = { size?: number };

// WhatsApp — official green speech bubble with phone.
export function WhatsAppLogo({ size = 14 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#25D366"
        d="M12 2a10 10 0 0 0-8.6 15.05L2 22l5.1-1.34A10 10 0 1 0 12 2Z"
      />
      <path
        fill="#fff"
        d="M16.6 14.3c-.25-.13-1.47-.72-1.7-.8-.23-.09-.4-.13-.56.13-.17.25-.64.8-.79.97-.14.17-.29.19-.54.06a6.9 6.9 0 0 1-2.03-1.25 7.6 7.6 0 0 1-1.4-1.75c-.15-.25 0-.39.11-.51.11-.11.25-.29.37-.43.13-.14.17-.25.25-.42.09-.17.04-.32-.02-.45-.06-.13-.56-1.35-.77-1.85-.2-.48-.4-.42-.56-.42h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1 0 1.23.9 2.42 1.02 2.59.13.17 1.77 2.7 4.29 3.79.6.26 1.07.41 1.43.53.6.19 1.15.16 1.58.1.48-.07 1.47-.6 1.68-1.18.2-.58.2-1.07.14-1.18-.06-.11-.23-.17-.48-.29Z"
      />
    </svg>
  );
}

// RCS / Google Messages — chat bubble in Google blue.
export function RcsLogo({ size = 14 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#1A73E8"
        d="M12 3C6.9 3 3 6.6 3 11c0 2.3 1.1 4.3 2.9 5.7v3.6l3.4-1.9c.9.2 1.8.3 2.7.3 5.1 0 9-3.6 9-8s-3.9-8-9-8Z"
      />
      <circle cx="8.5" cy="11" r="1.15" fill="#fff" />
      <circle cx="12" cy="11" r="1.15" fill="#fff" />
      <circle cx="15.5" cy="11" r="1.15" fill="#fff" />
    </svg>
  );
}

// SMS — message bubble in violet.
export function SmsLogo({ size = 14 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#8B7CF6"
        d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4a2 2 0 0 1-2-2V6c0-1.1.9-2 2-2Z"
      />
      <path fill="#fff" d="M7 9h10v1.5H7zM7 12h7v1.5H7z" />
    </svg>
  );
}

// Email — envelope in amber.
export function EmailLogo({ size = 14 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" fill="#BB7503" />
      <path
        fill="none"
        stroke="#fff"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.5 7l8.5 6 8.5-6"
      />
    </svg>
  );
}

export function ChannelLogo({ channel, size }: { channel: ChannelKind; size?: number }) {
  switch (channel) {
    case "whatsapp": return <WhatsAppLogo size={size} />;
    case "rcs": return <RcsLogo size={size} />;
    case "sms": return <SmsLogo size={size} />;
    case "email": return <EmailLogo size={size} />;
  }
}
