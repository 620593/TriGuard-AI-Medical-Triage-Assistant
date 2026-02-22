import { AlertTriangle, CheckCircle, Info, AlertCircle } from "lucide-react";

const RiskBadge = ({ level = "LOW" }) => {
  const configs = {
    LOW: {
      color:
        "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      icon: <CheckCircle size={14} />,
      label: "Low Risk",
    },
    MEDIUM: {
      color:
        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
      icon: <Info size={14} />,
      label: "Medium Risk",
    },
    HIGH: {
      color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      icon: <AlertTriangle size={14} />,
      label: "High Risk",
    },
    CRITICAL: {
      color: "bg-red-600 text-white animate-pulse",
      icon: <AlertCircle size={14} />,
      label: "Immediate Action Required",
    },
  };

  const config = configs[level] || configs.LOW;

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
