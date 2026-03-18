import CalmResultCard from "./CalmResultCard";

function InlineMarkdown({ text }) {
  if (!text) return null;
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        const bold = part.match(/^\*\*(.+)\*\*$/);
        return bold ? (
          <strong key={i} className="font-semibold text-slate-900">
            {bold[1]}
          </strong>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </>
  );
}

function cleanText(text) {
  if (!text) return "";
  return String(text)
    .replace(/⚠️\s*IMPORTANT:?/gi, "")
    .replace(/IMPORTANT:/gi, "")
    .replace(/Assessment confidence:[^\n]*/gi, "")
    .replace(/\(Assessment confidence:[^\)]*\)/gi, "")
    .replace(/\n\s*\n\s*\n/g, "\n\n")
    .trim();
}

function DietarySection({ content, imageUrl }) {
  if (!content && !imageUrl) return null;

  const lines = String(content || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 5);

  return (
    <div className="rounded-xl border border-sky-100 bg-sky-50/40 p-3">
      <p className="text-sm font-medium text-slate-800 mb-2">Food support</p>

      {imageUrl ? (
        <div className="relative rounded-lg overflow-hidden border border-sky-100 aspect-video bg-slate-100 mb-3">
          <img
            src={imageUrl}
            alt="Suggested meal"
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        </div>
      ) : null}

      {lines.length > 0 ? (
        <p className="text-base leading-relaxed text-slate-700">
          <InlineMarkdown text={lines.join(" ")} />
        </p>
      ) : (
        <p className="text-base leading-relaxed text-slate-700">
          A few food and hydration adjustments may help you feel better while
          you recover.
        </p>
      )}
    </div>
  );
}

export default function TriageResponseCard({
  parsed,
  riskLevel,
  rawText,
  nutritionImageUrl,
}) {
  if (!parsed || !parsed.is_structured) {
    return (
      <CalmResultCard riskLevel={riskLevel}>
        <p className="text-base leading-relaxed text-slate-700 whitespace-pre-wrap">
          {cleanText(rawText || "")}
        </p>
      </CalmResultCard>
    );
  }

  const summary = cleanText(parsed.summary || "");
  const action = cleanText(parsed.action || "");
  const redFlags = cleanText(parsed.red_flags || "");

  return (
    <CalmResultCard riskLevel={riskLevel || parsed.risk_level}>
      {summary ? (
        <div>
          <p className="text-sm font-medium text-slate-800 mb-1">Summary</p>
          <p className="text-base leading-relaxed text-slate-700">
            <InlineMarkdown text={summary} />
          </p>
        </div>
      ) : null}

      {action ? (
        <div>
          <p className="text-sm font-medium text-slate-800 mb-1">Next step</p>
          <p className="text-base leading-relaxed text-slate-700">
            <InlineMarkdown text={action} />
          </p>
        </div>
      ) : null}

      {redFlags ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-medium text-slate-800 mb-1">
            When to get urgent help
          </p>
          <p className="text-base leading-relaxed text-slate-700">
            <InlineMarkdown text={redFlags} />
          </p>
        </div>
      ) : null}

      {(parsed.dietary || nutritionImageUrl) && (
        <DietarySection content={parsed.dietary} imageUrl={nutritionImageUrl} />
      )}
    </CalmResultCard>
  );
}
