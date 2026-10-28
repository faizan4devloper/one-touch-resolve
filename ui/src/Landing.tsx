import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";

/**
 * Minimal landing (hero) — logo, headline, and a single CTA into the live demo.
 */
const ease = [0.22, 0.61, 0.36, 1] as const;

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
};

export default function Landing({ onStart }: { onStart: () => void }) {
  const start = onStart;

  return (
    <div className="hero">
      {/* top bar */}
      <motion.header
        className="hero-nav"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease }}
      >
        <div className="hero-logo">
          <img src="./hcltech-logo.jpg" alt="HCLTech" width={30} height={30} />
          <span>One Touch Resolve</span>
        </div>
        <span className="hero-pill">AWS CDS · Agentic AI</span>
      </motion.header>

      {/* centered hero — minimal */}
      <motion.main className="hero-main" variants={container} initial="hidden" animate="show">
        <motion.h1 className="hero-h1" variants={item}>
          Settle claims in <span className="accent">minutes</span>,
          <br /> not <span className="strike">40 days</span>.
        </motion.h1>

        <motion.p className="hero-sub" variants={item}>
          An agentic engine that coordinates every party in a claim — with <b>zero calls</b>.
        </motion.p>

        <motion.button
          className="hero-cta"
          variants={item}
          onClick={start}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
        >
          Start the live demo
          <ArrowRight size={18} strokeWidth={2.4} />
        </motion.button>
      </motion.main>

      <motion.footer
        className="hero-foot"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7, duration: 0.5 }}
      >
        AWS Communication Developer Services · Agentic AI Partner Hackathon
      </motion.footer>
    </div>
  );
}
