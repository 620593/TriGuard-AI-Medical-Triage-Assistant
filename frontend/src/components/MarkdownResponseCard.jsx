/**
 * MarkdownResponseCard.jsx
 * -------------------------
 * Parses the backend's strict 7-section markdown format and renders each
 * section as a visually distinct, premium card block.
 *
 * Section format: ### Emoji Title\n content \n\n---\n\n ### Next Section
 *
 * Sections rendered:
 *   🧾 Symptoms Identified  → Pill badges
 *   🩺 Possible Conditions  → Italic italic-soft condition pills
 *   ❓ Follow-Up Questions   → Soft question card
 *   🧘 Recommended Actions  → Numbered step list
 *   🥗 Nutrition Advice      → Green tinted card
 *   💊 OTC Suggestions       → Warning-tinted card
 *   🚨 When to See a Doctor  → Risk-colour bordered card
 */

import { AlertTriangle, Clock, CheckCircle2, Pill, Leaf, HelpCircle } from "lucide-react";
import CalmResultCard, { normalizeRiskLevel } from "./CalmResultCard";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Strips markdown italics/bold/asterisks but keeps the text */
function stripMd(text) {
  return String(text || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .trim();
}

/** Parses bullet/numbered lines into an array of strings */
function parseLines(text) {
  return String(text || "")
    .split("\n")
    .map((l) => l.replace(/^(?:[•\-*]|\d+\.)\s*/, "").trim())
    .filter(Boolean);
}

/** Splits markdown into intro text, section blocks, and footer text. */
function parseDocument(raw) {
  if (!raw) {
    return { intro: "", sections: [], footer: "" };
  }

  const blocks = String(raw).split(/\n\s*---\s*\n/);
  const sections = [];
  const introParts = [];
  const footerParts = [];

  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed) continue;

    const headingMatch = trimmed.match(/^###\s+(.+?)\s*\n([\s\S]*)$/m);
    if (headingMatch) {
      const heading = headingMatch[1].trim();
      const body = headingMatch[2].trim();
      const introSplit = trimmed.indexOf(headingMatch[0]);
      if (introSplit > 0) {
        const intro = trimmed.slice(0, introSplit).trim();
        if (intro) {
          if (!sections.length) {
            introParts.push(intro);
          } else {
            footerParts.push(intro);
          }
        }
      }
      sections.push({ heading, body });
      continue;
    }

    if (!sections.length) {
      introParts.push(trimmed);
    } else {
      footerParts.push(trimmed);
    }
  }

  return {
    intro: introParts.join("\n\n").trim(),
    sections,
    footer: footerParts.join("\n\n").trim(),
  };
}

// ── Section Renderers ─────────────────────────────────────────────────────────

function SymptomsSection({ body }) {
  const items = parseLines(body);
  if (!items.length) return null;
  return (
    <div>
      <div className="flex flex-wrap gap-2 mt-1">
        {items.map((s, i) => (
          <span
            key={i}
            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium
                       bg-blue-50 border border-blue-200 text-blue-700"
          >
            {stripMd(s)}
          </span>
        ))}
      </div>
    </div>
  );
}

function ConditionsSection({ body }) {
  const lines = String(body || "").split("\n").filter(Boolean);
  const summary = lines.filter((l) => !l.startsWith("•") && !l.startsWith("-") && !l.startsWith("*")).join(" ");
  const conditions = lines.filter((l) => l.startsWith("•") || l.startsWith("-") || l.startsWith("*"));

  return (
    <div className="space-y-2">
      {summary && (
        <p className="text-sm text-slate-600 leading-relaxed">{stripMd(summary)}</p>
      )}
      {conditions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {conditions.map((c, i) => {
            const text = c.replace(/^[•\-\*]\s*/, "").replace(/\*(Possible but not confirmed)\*/i, "").trim();
            return (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs
                           bg-purple-50 border border-purple-200 text-purple-700"
              >
                <span>{stripMd(text)}</span>
                <span className="text-purple-400 text-[10px] italic">~possible</span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ActionsSection({ body }) {
  const items = parseLines(body);
  if (!items.length) return null;
  return (
    <ol className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-3">
          <span className="flex-shrink-0 w-5 h-5 rounded-full bg-teal-50 border border-teal-200
                           text-teal-600 text-[10px] font-bold flex items-center justify-center mt-0.5">
            {i + 1}
          </span>
          <span className="text-sm text-slate-700 leading-relaxed">{stripMd(item)}</span>
        </li>
      ))}
    </ol>
  );
}

function FollowupSection({ body }) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
      <div className="flex items-start gap-2">
        <HelpCircle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-amber-800 leading-relaxed">{stripMd(body)}</p>
      </div>
    </div>
  );
}

function NutritionSection({ body }) {
  const lines = String(body || "").split("\n").filter(Boolean);
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 space-y-2">
      {lines.map((line, i) => {
        const stripped = line.replace(/^[•\-\*]\s*|^\*\*(.*?)\*\*:?\s*/g, "").trim();
        const isHeader = line.startsWith("**");
        const isHydration = line.startsWith("💧");
        const isLifestyle = line.startsWith("🏃");
        if (!stripped && !isHydration && !isLifestyle) return null;
        if (isHeader && !isHydration && !isLifestyle) {
          return (
            <p key={i} className="text-xs font-semibold text-emerald-700 mt-1 uppercase tracking-wide">
              {line.replace(/\*\*/g, "").replace(/:/g, "")}
            </p>
          );
        }
        return (
          <div key={i} className="flex items-start gap-2">
            <Leaf size={12} className="text-emerald-600 mt-0.5 flex-shrink-0" />
            <span className="text-sm text-slate-700 leading-relaxed">{stripMd(stripped || line)}</span>
          </div>
        );
      })}
    </div>
  );
}

function OtcSection({ body }) {
  const lines = parseLines(body);
  return (
    <div className="rounded-xl border border-orange-200 bg-orange-50 p-3 space-y-2">
      {lines.map((line, i) => (
        <div key={i} className="flex items-start gap-2">
          <Pill size={13} className="text-orange-600 mt-0.5 flex-shrink-0" />
          <span className="text-sm text-slate-700 leading-relaxed">{stripMd(line)}</span>
        </div>
      ))}
    </div>
  );
}

function DoctorSection({ body, riskLevel }) {
  const risk = (riskLevel || "").toLowerCase();
  const borderColor =
    risk === "critical" || risk === "high"
      ? "border-red-200 bg-red-50"
      : risk === "moderate"
      ? "border-amber-200 bg-amber-50"
      : "border-slate-200 bg-slate-50";

  const Icon =
    risk === "critical" || risk === "high"
      ? AlertTriangle
      : risk === "moderate"
      ? Clock
      : CheckCircle2;

  const iconColor =
    risk === "critical" || risk === "high"
      ? "text-red-500"
      : risk === "moderate"
      ? "text-amber-500"
      : "text-emerald-600";

  return (
    <div className={`rounded-xl border p-3 ${borderColor}`}>
      <div className="flex items-start gap-2">
        <Icon size={16} className={`${iconColor} mt-0.5 flex-shrink-0`} />
        <p className="text-sm text-slate-700 leading-relaxed">{stripMd(body)}</p>
      </div>
    </div>
  );
}

function GenericSection({ body }) {
  /** Handles XRay Review, What We See, and any unlabelled section. */
  const lines = String(body || "").split("\n").filter(Boolean);
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        const isBullet = line.startsWith("•") || line.startsWith("-") || line.startsWith("*");
        const isBold   = line.startsWith("**") && line.endsWith("**");
        const cleaned  = stripMd(line);
        if (!cleaned) return null;
        if (isBold) {
          return (
            <p key={i} className="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-1">
              {cleaned}
            </p>
          );
        }
        if (isBullet) {
          const text = cleaned.replace(/^[•\-\*]\s*/, "");
          return (
            <div key={i} className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mt-2 flex-shrink-0" />
              <span className="text-sm text-slate-700 leading-relaxed">{text}</span>
            </div>
          );
        }
        return (
          <p key={i} className="text-sm text-slate-700 leading-relaxed">
            {cleaned}
          </p>
        );
      })}
    </div>
  );
}

function IntroSection({ text }) {
  if (!text) return null;

  const lines = String(text)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className="rounded-xl border border-sky-100 bg-sky-50/60 p-3 space-y-2">
      {lines.map((line, i) => {
        const cleaned = stripMd(line);
        if (!cleaned) return null;
        return (
          <p key={i} className="text-sm text-slate-700 leading-relaxed">
            {cleaned}
          </p>
        );
      })}
    </div>
  );
}

function FooterSection({ text }) {
  if (!text) return null;

  return (
    <p className="text-xs text-slate-500 leading-relaxed border-t border-slate-100 pt-2">
      {stripMd(text)}
    </p>
  );
}

// ── Section icon/color map ────────────────────────────────────────────────────

const SECTION_META = {
  "🧾": { label: "Symptoms Identified", accent: "text-blue-600" },
  "🩺": { label: "Possible Conditions", accent: "text-purple-600" },
  "❓": { label: "A Quick Question", accent: "text-amber-600" },
  "🧘": { label: "Recommended Actions", accent: "text-teal-600" },
  "🥗": { label: "Nutrition Advice", accent: "text-emerald-600" },
  "💊": { label: "OTC Suggestions", accent: "text-orange-600" },
  "🚨": { label: "When to See a Doctor", accent: "text-red-600" },
  "📋": { label: "Your Health History", accent: "text-sky-600" },
  "🩻": { label: "X-Ray Review", accent: "text-indigo-600" },
  "👁️": { label: "What We See", accent: "text-cyan-600" },
};

function getEmoji(heading) {
  if (!heading) return null;
  const match = heading.match(/^[\p{Emoji}]/u);
  return match ? match[0] : null;
}

function getSectionLabel(heading) {
  return String(heading || "")
    .replace(/^[\p{Emoji}\s]+/u, "")
    .replace(/^#\s*/g, "")
    .trim()
    .toLowerCase();
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function MarkdownResponseCard({ text, riskLevel }) {
  if (!text) return null;

  const { intro, sections, footer } = parseDocument(text);

  if (!sections.length && !intro) {
    return (
      <CalmResultCard riskLevel={riskLevel}>
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{text}</p>
      </CalmResultCard>
    );
  }

  return (
    <CalmResultCard riskLevel={riskLevel}>
      <div className="space-y-3">
        <IntroSection text={intro} />
        {sections.map((section, idx) => {
          const { heading, body } = section;
          const emoji = heading ? getEmoji(heading) : null;
          const label = getSectionLabel(heading);
          const meta = emoji ? SECTION_META[emoji] : null;
          const accentColor = meta?.accent || "text-teal-600";

          // Choose renderer by emoji
          let content;
          if (emoji === "🧾" || label.includes("symptom")) content = <SymptomsSection body={body} />;
          else if (emoji === "🩺" || label.includes("condition")) content = <ConditionsSection body={body} />;
          else if (emoji === "❓" || label.includes("follow-up") || label.includes("quick question")) content = <FollowupSection body={body} />;
          else if (emoji === "🧘" || label.includes("action")) content = <ActionsSection body={body} />;
          else if (emoji === "🥗" || label.includes("nutrition")) content = <NutritionSection body={body} />;
          else if (emoji === "💊" || label.includes("otc")) content = <OtcSection body={body} />;
          else if (emoji === "🚨" || label.includes("doctor")) content = <DoctorSection body={body} riskLevel={riskLevel} />;
          else {
            // Generic section (history, xray review, body image, etc.) — rich text
            content = <GenericSection body={body} />;
          }

          return (
            <div
              key={idx}
              className="rounded-xl border border-slate-100 bg-slate-50/60 p-3
                         hover:border-slate-200 transition-colors duration-150"
            >
              {heading && (
                <div className={`flex items-center gap-1.5 mb-2 ${accentColor}`}>
                  <span className="text-sm">{emoji}</span>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    {heading.replace(/^[\p{Emoji}\s]+/u, "").trim()}
                  </span>
                </div>
              )}
              {content}
            </div>
          );
        })}
        <FooterSection text={footer} />
      </div>
    </CalmResultCard>
  );
}
