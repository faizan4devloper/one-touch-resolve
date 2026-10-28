import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * App-wide session context. The customer Phone sets the active claim session id
 * here when a journey starts; the operator views read it to pin their live
 * subscription to the same claim. This replaces the old sessionStorage polling
 * hack used by the multi-page build.
 */
interface SessionCtx {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
}

const Ctx = createContext<SessionCtx | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  return <Ctx.Provider value={{ sessionId, setSessionId }}>{children}</Ctx.Provider>;
}

export function useSession(): SessionCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used within <SessionProvider>");
  return ctx;
}
