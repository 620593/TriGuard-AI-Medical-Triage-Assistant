import CalmResultCard from "./CalmResultCard";

function parseXrayText(text) {
  const lines = String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const body = [];
  let actionSentence = "";
  let inActionBlock = false;

  for (const line of lines) {
    const lower = line.toLowerCase();

    if (
      lower.includes("triage summary") ||
      lower.startsWith("📊 risk level") ||
      lower.includes("assessment confidence") ||
      lower.includes("important:") ||
      lower.includes("must be reviewed") ||
      lower.includes("not a radiological diagnosis") ||
      lower.startsWith("⚠️ disclaimer") ||
      /^[-─]{3,}$/.test(line)
    ) {
      inActionBlock = false;
      continue;
    }

    if (lower.includes("what you can do")) {
      inActionBlock = true;
      continue;
    }

    if (inActionBlock && line.startsWith("•") && !actionSentence) {
      actionSentence = line.replace(/^•\s*/, "").trim();
      continue;
    }

    if (line.startsWith("•")) {
      continue;
    }

    body.push(line);
  }

  const paragraph = body.join(" ").replace(/\s+/g, " ").trim();

  return {
    paragraph:
      paragraph ||
      "We reviewed your X-ray and there are no urgent signs from this quick screen.",
    action:
      actionSentence ||
      "A doctor can take a closer look and guide you on the best next step.",
  };
}

export default function XrayResultCard({ text, riskLevel }) {
  const content = parseXrayText(text);

  return (
    <CalmResultCard riskLevel={riskLevel}>
      <p className="text-base leading-relaxed text-slate-700">
        {content.paragraph}
      </p>

      <p className="mt-3 text-base leading-relaxed text-slate-700">
        {content.action}
      </p>
    </CalmResultCard>
  );
}
