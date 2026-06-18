import { motion } from "framer-motion";

export const CALM_RISK = {
  low: {
    label: "🟢 Low",
    tone: "bg-green-50 text-green-700",
  },
  moderate: {
    label: "🟡 Moderate",
    tone: "bg-amber-50 text-amber-700",
  },
  high: {
    label: "🟠 High",
    tone: "bg-[var(--bg-primary)] text-[var(--accent-active)]",
  },
  critical: {
    label: "🔴 Critical",
    tone: "bg-red-50 text-red-700",
  },
};

export const CALM_DISCLAIMER =
  "TriGuard is a screening aid — not a diagnosis. Please consult a qualified doctor for medical advice.";

export function normalizeRiskLevel(level) {
  const key = String(level || "low").toLowerCase();
  if (key === "medium") return "moderate";
  return CALM_RISK[key] ? key : "low";
}

export default function CalmResultCard({
  riskLevel,
  title = "Here's what we found",
  subtitle = "AI-assisted screening • Always verify with a doctor",
  disclaimer = CALM_DISCLAIMER,
  children,
  className = "",
}) {
  const risk = CALM_RISK[normalizeRiskLevel(riskLevel)];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={`w-full rounded-2xl bg-[var(--bg-secondary)] text-[var(--text-primary)]  border border-sky-100 p-5 ${className}`}
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-[var(--accent-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{subtitle}</p>
        </div>

        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${risk.tone}`}
        >
          {risk.label}
        </span>
      </div>

      <div className="space-y-3">{children}</div>

      <p className="mt-4 text-xs text-[var(--text-secondary)]">{disclaimer}</p>
    </motion.div>
  );
}
