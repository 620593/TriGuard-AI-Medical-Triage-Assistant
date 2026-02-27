/**
 * TriageResponseCard.jsx  (Version 2 — Premium Redesign)
 * --------------------------------------------------------
 * Props:
 *   parsed         {object}  ParsedResponse from backend output_parser
 *   riskLevel      {string}  "low" | "moderate" | "high" | "critical"
 *   rawText        {string}  Fallback raw text when is_structured is false
 *   nutritionImage {string}  Filename of HuggingFace-generated meal image (optional)
 *   nutritionImageUrl {string}  Full URL built by parent (optional)
 */

import { motion } from "framer-motion";
import {
  Stethoscope,
  Zap,
  TriangleAlert,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Siren,
  Leaf,
  Info,
  ChefHat,
  ImageOff,
} from "lucide-react";

// ── Risk configuration ─────────────────────────────────────────────────────
const RISK = {
  low: {
    label: "Low Risk",
    score_color: "text-emerald-300",
    header_gradient: "from-emerald-950/80 to-emerald-900/40",
    border: "border-emerald-500/30",
    bar: "bg-gradient-to-r from-emerald-600 to-teal-400",
    bar_width: "22%",
    badge: "bg-emerald-500/20 text-emerald-300",
    icon: <ShieldCheck size={18} className="text-emerald-400" />,
    glow: "",
  },
  moderate: {
    label: "Moderate Risk",
    score_color: "text-amber-300",
    header_gradient: "from-amber-950/80 to-amber-900/40",
    border: "border-amber-500/30",
    bar: "bg-gradient-to-r from-amber-600 to-yellow-400",
    bar_width: "52%",
    badge: "bg-amber-500/20 text-amber-300",
    icon: <ShieldAlert size={18} className="text-amber-400" />,
    glow: "",
  },
  high: {
    label: "High Risk",
    score_color: "text-orange-300",
    header_gradient: "from-orange-950/80 to-orange-900/40",
    border: "border-orange-500/40",
    bar: "bg-gradient-to-r from-orange-600 to-red-400",
    bar_width: "76%",
    badge: "bg-orange-500/20 text-orange-300",
    icon: <ShieldX size={18} className="text-orange-400" />,
    glow: "shadow-[0_0_25px_rgba(249,115,22,0.12)]",
  },
  critical: {
    label: "Emergency",
    score_color: "text-red-300",
    header_gradient: "from-red-950/90 to-red-900/50",
    border: "border-red-500/50",
    bar: "bg-gradient-to-r from-red-700 via-rose-500 to-pink-400",
    bar_width: "100%",
    badge: "bg-red-500/25 text-red-200",
    icon: <Siren size={18} className="text-red-400 animate-pulse" />,
    glow: "shadow-[0_0_30px_rgba(220,38,38,0.2)]",
  },
};
const getRisk = (level) => RISK[(level || "low").toLowerCase()] ?? RISK.low;

// ── Animation helpers ──────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.32, ease: "easeOut", delay },
});

// ── Micro-components ───────────────────────────────────────────────────────

/** Parse "**bold**" markdown inside text strings */
function InlineMarkdown({ text }) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        const bold = part.match(/^\*\*(.+)\*\*$/);
        return bold ? (
          <strong key={i} className="font-semibold text-white">
            {bold[1]}
          </strong>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </>
  );
}

/** Numbered red-flag list — splits on "1." "2." "3." patterns */
function RedFlagList({ content }) {
  if (!content) return null;
  // Split on numbered patterns like "1. " "2. " etc.
  const items = content
    .split(/(?<!\d)(\d+)\.\s+/g)
    .reduce((acc, part, idx, arr) => {
      // Parts at odd indices are the numbers; even are the text
      if (/^\d+$/.test(part)) return acc;
      const text = part.trim();
      if (text) acc.push(text);
      return acc;
    }, []);

  if (items.length <= 1) {
    // No numbered list detected — render as plain text
    return (
      <p className="text-sm text-slate-300 leading-relaxed">
        <InlineMarkdown text={content} />
      </p>
    );
  }

  return (
    <ul className="space-y-1.5 mt-1">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5">
          <span className="mt-0.5 w-5 h-5 shrink-0 rounded-full bg-amber-500/25 flex items-center justify-center text-amber-300 text-xs font-bold">
            {i + 1}
          </span>
          <span className="text-sm text-slate-300 leading-relaxed">
            <InlineMarkdown text={item} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Dietary tips — numbered card grid */
function DietarySection({ content, imageUrl }) {
  if (!content && !imageUrl) return null;

  // Parse "1. **Title**: body" or "1. text" patterns
  let items = [];
  if (content) {
    const lines = content
      .split(/\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    let current = null;
    for (const line of lines) {
      const headMatch = line.match(/^(\d+)\.\s+\*\*(.+?)\*\*[:\-]?\s*(.*)/);
      const numMatch = line.match(/^(\d+)\.\s+(.*)/);
      if (headMatch) {
        if (current) items.push(current);
        current = { title: headMatch[2], body: headMatch[3] };
      } else if (numMatch) {
        if (current) items.push(current);
        current = { title: null, body: numMatch[2] };
      } else if (current) {
        current.body += " " + line;
      }
    }
    if (current) items.push(current);
  }

  return (
    <motion.div
      {...fadeUp(0.4)}
      className="rounded-2xl overflow-hidden border border-emerald-700/30 bg-gradient-to-br from-emerald-950/60 to-slate-900/80"
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-emerald-700/20 bg-emerald-900/20">
        <div className="w-7 h-7 rounded-lg bg-emerald-500/20 flex items-center justify-center">
          <ChefHat size={14} className="text-emerald-400" />
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-emerald-400">
            Dietary Suggestions
          </p>
          <p className="text-[10px] text-emerald-600">
            Evidence-based nutritional guidance
          </p>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* AI-generated meal image */}
        {imageUrl ? (
          <div className="relative rounded-xl overflow-hidden border border-emerald-700/30 aspect-video bg-emerald-950/40">
            <img
              src={imageUrl}
              alt="AI-generated suggested meal"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.nextSibling.style.display = "flex";
              }}
            />
            {/* Fallback if image fails */}
            <div
              className="hidden w-full h-full items-center justify-center flex-col gap-2 text-slate-600"
              style={{ display: "none" }}
            >
              <ImageOff size={28} />
              <p className="text-xs">Image unavailable</p>
            </div>
            {/* Label overlay */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
              <p className="text-xs text-emerald-300 font-medium">
                🤖 AI-generated meal suggestion
              </p>
            </div>
          </div>
        ) : null}

        {/* Tip cards grid */}
        {items.length > 0 && (
          <div className="grid gap-2">
            {items.slice(0, 5).map((item, i) => (
              <div
                key={i}
                className="flex gap-3 p-2.5 rounded-xl bg-white/4 border border-emerald-800/25 hover:bg-emerald-900/20 transition-colors"
              >
                <span className="mt-0.5 w-6 h-6 shrink-0 flex items-center justify-center rounded-full bg-emerald-600/30 text-emerald-300 text-xs font-bold">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  {item.title && (
                    <p className="text-xs font-semibold text-emerald-300 mb-0.5">
                      {item.title}
                    </p>
                  )}
                  <p className="text-xs text-slate-400 leading-relaxed">
                    <InlineMarkdown text={item.body} />
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Consultant note */}
        <p className="text-[10px] text-slate-600 italic text-center">
          Consult a registered dietitian for personalised advice.
        </p>
      </div>
    </motion.div>
  );
}

// ── Main Card ──────────────────────────────────────────────────────────────

export default function TriageResponseCard({
  parsed,
  riskLevel,
  rawText,
  nutritionImageUrl,
}) {
  // Fallback: not structured → render raw (emergency alerts, vision results)
  if (!parsed || !parsed.is_structured) {
    const isCritical =
      riskLevel === "critical" || (rawText && rawText.includes("🚨"));
    return (
      <div className="space-y-2">
        {isCritical && (
          <div className="flex items-center gap-2 text-red-300 text-sm font-bold px-1 mb-2 animate-pulse">
            <Siren size={16} /> Emergency Alert
          </div>
        )}
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {rawText || ""}
        </p>
      </div>
    );
  }

  const cfg = getRisk(riskLevel || parsed.risk_level);
  const score = parsed.risk_score || "";

  return (
    <div className="space-y-3 w-full max-w-full">
      {/* ── 1. Risk Header Card ────────────────────────────────────────── */}
      <motion.div
        {...fadeUp(0)}
        className={`rounded-2xl border ${cfg.border} ${cfg.glow} overflow-hidden`}
      >
        <div className={`bg-gradient-to-br ${cfg.header_gradient} px-4 py-3`}>
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center ${cfg.badge}`}
              >
                {cfg.icon}
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-widest font-medium">
                  Risk Assessment
                </p>
                <p className={`text-base font-bold ${cfg.score_color}`}>
                  {cfg.label}
                </p>
              </div>
            </div>
            {score && (
              <div className={`text-right`}>
                <p className="text-xs text-slate-500 mb-0.5">Score</p>
                <p
                  className={`font-mono text-xl font-black ${cfg.score_color}`}
                >
                  {score}
                </p>
              </div>
            )}
          </div>

          {/* Animated progress bar */}
          <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
            <motion.div
              className={`h-full rounded-full ${cfg.bar}`}
              initial={{ width: 0 }}
              animate={{ width: cfg.bar_width }}
              transition={{
                duration: 1,
                ease: [0.34, 1.56, 0.64, 1],
                delay: 0.15,
              }}
            />
          </div>
        </div>
      </motion.div>

      {/* ── 2. Assessment ─────────────────────────────────────────────── */}
      {parsed.summary && (
        <motion.div
          {...fadeUp(0.09)}
          className="rounded-2xl border border-teal-700/25 bg-gradient-to-br from-teal-950/50 to-slate-900/60 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-teal-500/20 flex items-center justify-center">
              <Stethoscope size={12} className="text-teal-400" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-teal-400">
              Assessment
            </p>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">
            <InlineMarkdown text={parsed.summary} />
          </p>
        </motion.div>
      )}

      {/* ── 3. What to Do Now ─────────────────────────────────────────── */}
      {parsed.action && (
        <motion.div
          {...fadeUp(0.17)}
          className="rounded-2xl border border-sky-700/25 bg-gradient-to-br from-sky-950/50 to-slate-900/60 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-sky-500/20 flex items-center justify-center">
              <Zap size={12} className="text-sky-400" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-sky-400">
              What To Do Now
            </p>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">
            <InlineMarkdown text={parsed.action} />
          </p>
        </motion.div>
      )}

      {/* ── 4. Red Flags ──────────────────────────────────────────────── */}
      {parsed.red_flags && (
        <motion.div
          {...fadeUp(0.25)}
          className="rounded-2xl border border-amber-700/30 bg-gradient-to-br from-amber-950/50 to-slate-900/60 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg bg-amber-500/20 flex items-center justify-center">
              <TriangleAlert size={12} className="text-amber-400" />
            </div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-amber-400">
              Seek Immediate Help If…
            </p>
          </div>
          <RedFlagList content={parsed.red_flags} />
        </motion.div>
      )}

      {/* ── 5. Dietary Suggestions + AI Image ─────────────────────────── */}
      {(parsed.dietary || nutritionImageUrl) && (
        <DietarySection content={parsed.dietary} imageUrl={nutritionImageUrl} />
      )}

      {/* ── 6. Disclaimer ─────────────────────────────────────────────── */}
      {parsed.disclaimer && (
        <motion.div
          {...fadeUp(0.48)}
          className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-white/3 border border-white/6"
        >
          <Info size={11} className="mt-0.5 shrink-0 text-slate-600" />
          <p className="text-[11px] text-slate-500 leading-relaxed italic">
            {parsed.disclaimer}
          </p>
        </motion.div>
      )}
    </div>
  );
}
