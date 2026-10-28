import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ArrowRight, ShieldCheck, Zap, Users, Sparkles } from "lucide-react";

/**
 * Branded intro — a short slide sequence shown before the landing hero. Sets up
 * the story (problem → what it does → the tech) so the app "opens like a
 * product." MANUAL advance only (click, →/Space, or the Next button); Skip or
 * the final CTA enters the live demo. Reuses the hero's indigo brand tokens.
 */
const ease = [0.22, 0.61, 0.36, 1] as const;

type Slide = {
  kicker: string;
  Icon: typeof Zap;
  title: React.ReactNode;
  sub: React.ReactNode;
  chips?: string[];
};

const SLIDES: Slide[] = [
  {
    kicker: "AWS CDS · Agentic AI Partner Hackathon",
    Icon: Sparkles,
    title: (<>One Touch <span className="intro-accent">Resolve</span></>),
    sub: "An agentic engine that coordinates every party in an insurance claim — FNOL to settlement, with zero calls.",
  },
  {
    kicker: "The problem",
    Icon: Zap,
    title: (<><span className="intro-accent">40.7 days</span> to settle a claim</>),
    sub: "The delay isn't the adjuster — it's fragmentation. Policyholder, roadside, rental and repair each live in a different system. Nobody owns the coordination.",
  },
  {
    kicker: "What makes it different",
    Icon: Users,
    title: (<>Multi-party. <span className="intro-accent">One gated outcome.</span></>),
    sub: "One AI agent per party, driven in parallel. A commit gate blocks settlement until every party commits — and re-plans when one is blocked.",
  },
  {
    kicker: "Built on AWS",
    Icon: ShieldCheck,
    title: (<>Real multimodal AI, <span className="intro-accent">live</span></>),
    sub: "Amazon Bedrock Nova Pro vision reads the damage photo and branches the plan on what it actually sees.",
    chips: ["Amazon SES · live", "Bedrock Nova Pro vision", "AgentCore Runtime + Memory", "WhatsApp · RCS · SMS · Email", "DynamoDB"],
  },
];

export default function IntroSlides({ onDone }: { onDone: () => void }) {
  const [i, setI] = useState(0);
  const last = i === SLIDES.length - 1;

  const next = () => setI((n) => Math.min(SLIDES.length - 1, n + 1));
  const prev = () => setI((n) => Math.max(0, n - 1));

  // Manual navigation only — arrow keys / space advance, no auto-slide.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Enter" && last) onDone();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [last, onDone]);

  const s = SLIDES[i];
  const Icon = s.Icon;

  return (
    <div className="intro">
      {/* top bar: brand + skip */}
      <div className="intro-nav">
        <div className="intro-brand">
          <img src="./hcltech-logo.jpg" alt="HCLTech" width={28} height={28} />
          <span>One Touch Resolve</span>
        </div>
        <button className="intro-skip" onClick={onDone}>Skip intro →</button>
      </div>

      {/* progress segments */}
      <div className="intro-prog">
        {SLIDES.map((_, k) => (
          <span key={k} className={"seg" + (k <= i ? " on" : "")} />
        ))}
      </div>

      <div className="intro-stage">
        <AnimatePresence mode="wait">
          <motion.div
            key={i}
            className="intro-slide"
            initial={{ opacity: 0, y: 18, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -14, filter: "blur(4px)" }}
            transition={{ duration: 0.55, ease }}
          >
            <div className="intro-kick"><Icon size={15} strokeWidth={2.3} /> {s.kicker}</div>
            <h1 className="intro-h1">{s.title}</h1>
            <p className="intro-sub">{s.sub}</p>
            {s.chips && (
              <div className="intro-chips">
                {s.chips.map((c) => <span key={c} className="intro-chip">{c}</span>)}
              </div>
            )}
            {last && (
              <motion.button
                className="intro-cta"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25, duration: 0.45, ease }}
                onClick={onDone}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
              >
                Start the live demo <ArrowRight size={18} strokeWidth={2.4} />
              </motion.button>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="intro-dots">
        <div className="dots-wrap">
          {SLIDES.map((_, k) => (
            <button
              key={k}
              className={"dot" + (k === i ? " on" : "")}
              aria-label={`Go to slide ${k + 1}`}
              onClick={() => setI(k)}
            />
          ))}
        </div>
        {!last && (
          <button className="intro-next" onClick={next}>
            Next <ArrowRight size={15} strokeWidth={2.4} />
          </button>
        )}
      </div>
    </div>
  );
}
