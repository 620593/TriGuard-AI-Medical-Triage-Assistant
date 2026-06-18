import { CheckCircle, Info, AlertCircle } from "lucide-react";

const RiskBadge = ({ level = "LOW" }) => {
  const configs = {
    LOW: {
      color: "bg-green-50 text-green-700 border border-green-100",
      icon: <CheckCircle size={14} />,
      label: "🟢 Low",
    },
    MEDIUM: {
      color: "bg-amber-50 text-amber-700 border border-amber-100",
      icon: <Info size={14} />,
      label: "🟡 Moderate",
    },
    HIGH: {
      color: "bg-[var(--bg-primary)] text-[var(--accent-active)] border border-orange-100",
      icon: <Info size={14} />,
      label: "🟠 High",
    },
    CRITICAL: {
      color: "bg-red-50 text-red-700 border border-red-100",
      icon: <AlertCircle size={14} />,
      label: "🔴 Critical",
    },
  };

  const normalizedLevel = String(level).toUpperCase();
  const finalLevel =
    normalizedLevel === "MODERATE" ? "MEDIUM" : normalizedLevel;
  const config = configs[finalLevel] || configs.LOW;

  return (
    <div
      className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium ${config.color}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </div>
  );
};

export default RiskBadge;
