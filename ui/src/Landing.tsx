import { motion } from "motion/react";
import { ArrowRight, Users, Radio, ShieldCheck } from "lucide-react";

/**
 * Showcase landing (hero) page — centered dev-tool style with an engaging
 * staggered entrance animation (Framer Motion). The CTA starts the live demo.
 */
const ease = [0.22, 0.61, 0.36, 1] as const;

// Parent orchestrates a staggered reveal of its children.
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

      {/* centered hero — staggered reveal */}
      <motion.main className="hero-main" variants={container} initial="hidden" animate="show">
        <motion.span className="hero-kicker" variants={item}>
          Omnichannel claims coordination agent
        </motion.span>

        <motion.h1 className="hero-h1" variants={item}>
          Settle claims in <span className="accent">minutes</span>,
          <br /> not <span className="strike">40 days</span>.
        </motion.h1>

        <motion.p className="hero-sub" variants={item}>
          One Touch Resolve is an agentic engine that coordinates every party in a
          claim — claimant, roadside, rental, repair — across WhatsApp, RCS, SMS and
          email, driving First Notice of Loss to settlement with <b>zero calls</b>.
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

        {/* three proof points */}
        <motion.div className="hero-points" variants={item}>
          <div className="hpt">
            <span className="hpt-ic"><Users size={16} strokeWidth={2.2} /></span>
            Multi-party commit gate
          </div>
          <div className="hpt">
            <span className="hpt-ic"><Radio size={16} strokeWidth={2.2} /></span>
            Channel-aware continuity
          </div>
          <div className="hpt">
            <span className="hpt-ic"><ShieldCheck size={16} strokeWidth={2.2} /></span>
            Code-verified outcomes
          </div>
        </motion.div>

        {/* CDS services credibility row */}
        <motion.div className="hero-svcs" variants={item}>
          <span className="hero-svcs-label">Powered by</span>
          <span className="hero-chip">AWS End User Messaging · RCS · SMS</span>
          <span className="hero-chip">EUM Social · WhatsApp</span>
          <span className="hero-chip">Amazon SES</span>
          <span className="hero-chip accent-chip">Amazon Bedrock AgentCore</span>
        </motion.div>
      </motion.main>

      <motion.footer
        className="hero-foot"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7, duration: 0.5 }}
      >
        Submission · AWS Communication Developer Services Agentic AI Partner Hackathon
      </motion.footer>
    </div>
  );
}
