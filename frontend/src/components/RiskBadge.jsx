import { AlertTriangle, CheckCircle, Info, AlertCircle } from "lucide-react";

const RiskBadge = ({ level = "LOW" }) => {
  const configs = {
    LOW: {
      color:
        "bg-green-500/20 text-green-300 border border-green-500/30 backdrop-blur-md",
      icon: <CheckCircle size={14} />,
      label: "Low Risk",
    },
    MEDIUM: {
      color:
        "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 backdrop-blur-md",
      icon: <Info size={14} />,
      label: "Medium Risk",
    },
    HIGH: {
      color:
        "bg-red-500/20 text-red-300 border border-red-500/30 backdrop-blur-md",
      icon: <AlertTriangle size={14} />,
      label: "High Risk",
    },
    CRITICAL: {
      color:
        "bg-red-600 text-white animate-pulse shadow-[0_0_15px_rgba(220,38,38,0.7)]",
      icon: <AlertCircle size={14} />,
      label: "Immediate Action Required",
    },
  };

  const normalizedLevel = String(level).toUpperCase();
  const finalLevel =
    normalizedLevel === "MODERATE" ? "MEDIUM" : normalizedLevel;
  const config = configs[finalLevel] || configs.LOW;

  return (
    <div
      className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold ${config.color}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </div>
  );
};

export default RiskBadge;
