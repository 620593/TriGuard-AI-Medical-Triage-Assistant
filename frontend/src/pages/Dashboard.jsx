// eslint-disable-next-line no-unused-vars
import { motion } from "framer-motion";
import {
  Activity,
  Thermometer,
  Heart,
  Wind,
  TrendingUp,
  AlertCircle,
  Loader2,
} from "lucide-react";
import RiskBadge from "../components/RiskBadge";
import { useTriageReports } from "../hooks/useTriageReports";

const Dashboard = () => {
  const { reports, isLoading } = useTriageReports();

  const latestRisk =
    reports.length > 0 && reports[0].report
      ? reports[0].report.risk_level
      : "LOW";
  const lastAssessment =
    reports.length > 0
      ? new Date(reports[0].created_at).toLocaleString()
      : "NO RECENT ASSESSMENT";

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <header className="mb-10 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-2 text-gray-800 drop-shadow-sm">
            Health Dashboard
          </h1>
          <p className="text-gray-500 font-light">
            Your recent metrics and triage history.
          </p>
        </div>
        <div className="text-right">
          <RiskBadge level={latestRisk} />
          <p className="text-[10px] text-gray-500 mt-1 uppercase">
            LAST ASSESSMENT: {lastAssessment}
          </p>
        </div>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <StatCard
          icon={<Heart className="text-red-500" />}
          label="Heart Rate"
          value="72"
          unit="bpm"
          change="+2%"
        />
        <StatCard
          icon={<Thermometer className="text-orange-500" />}
          label="Body Temp"
          value="36.6"
          unit="°C"
          change="Optimal"
        />
        <StatCard
          icon={<Wind className="text-blue-500" />}
          label="Oxygen (O2)"
          value="98"
          unit="%"
          change="Stable"
        />
        <StatCard
          icon={<Activity className="text-teal-500" />}
          label="Activity"
          value="8.4k"
          unit="steps"
          change="+12%"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart Placeholder */}
        <div className="lg:col-span-2 skeuo-panel h-[400px] flex items-center justify-center relative overflow-hidden p-6">
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-medical-primary/5 to-transparent" />
          <p className="text-gray-500 flex items-center gap-2">
            <TrendingUp size={20} />
            Risk Trend Visualization coming soon
          </p>
        </div>

        {/* Sidebar Alerts */}
        <div className="space-y-6">
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-red-100 blur-2xl rounded-full" />
            <div className="flex items-start gap-4 text-red-700 z-10 relative">
              <AlertCircle className="shrink-0 mt-1 text-red-600" />
              <div>
                <h4 className="font-bold text-red-800">Medical Alert</h4>
                <p className="text-xs text-red-600 mt-1">
                  Based on your last symptoms, we recommend monitoring your
                  blood pressure closely.
                </p>
              </div>
            </div>
          </div>

          <div className="skeuo-panel p-6">
            <h4 className="font-bold text-gray-800 mb-4">Recent Triage Reports</h4>
            <div className="space-y-4">
              {isLoading ? (
                <div className="flex items-center gap-2 text-gray-500 py-4">
                  <Loader2 className="animate-spin" size={16} />
                  <span>Loading history...</span>
                </div>
              ) : reports.length > 0 ? (
                reports
                  .slice(0, 5)
                  .map((r) => (
                    <TestItem
                      key={r._id}
                      name={
                        r.report?.symptoms?.slice(0, 2).join(", ") ||
                        "General Triage"
                      }
                      date={new Date(r.created_at).toLocaleDateString()}
                      status={r.report?.risk_level || "UNKNOWN"}
                      urgent={
                        r.report?.risk_level === "CRITICAL" ||
                        r.report?.risk_level === "HIGH"
                      }
                    />
                  ))
              ) : (
                <p className="text-sm text-gray-500">No reports found.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ icon, label, value, unit, change }) => (
  <motion.div
    whileHover={{ scale: 1.02, y: -2 }}
    className="skeuo-panel p-6 group"
  >
    <div className="flex justify-between items-start mb-4">
      <div className="p-2 bg-[#ffedd5] rounded-xl shadow-sm border border-[#fed7aa] group-hover:bg-orange-100 transition-all">
        {icon}
      </div>
      {change && (
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full backdrop-blur-md ${
            change.startsWith("+")
              ? "bg-green-100 text-green-700 border border-green-200"
              : "bg-[#ffedd5] text-gray-600 border border-[#fed7aa]"
          }`}
        >
          {change}
        </span>
      )}
    </div>
    <div className="space-y-1">
      <p className="text-gray-500 text-sm font-medium">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold text-gray-800 drop-shadow-sm">
          {value}
        </span>
        <span className="text-gray-500 text-xs font-bold uppercase">
          {unit}
        </span>
      </div>
    </div>
  </motion.div>
);

const TestItem = ({ name, date, status, urgent }) => (
  <div className="flex items-center justify-between py-2 border-b border-[#fed7aa] last:border-0 hover:bg-orange-50 px-2 rounded-lg transition-colors cursor-pointer">
    <div>
      <p className="text-sm font-bold text-gray-800">{name}</p>
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">
        {date}
      </p>
    </div>
    <span
      className={`text-[10px] px-2 py-1 rounded-md border ${
        urgent
          ? "bg-red-50 text-red-600 border-red-200 font-bold"
          : "bg-[#ffedd5] text-gray-600 border-[#fed7aa]"
      }`}
    >
      {status}
    </span>
  </div>
);

export default Dashboard;
