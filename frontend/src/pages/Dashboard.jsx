import { motion } from "framer-motion";
import {
  Activity,
  Thermometer,
  Heart,
  Wind,
  TrendingUp,
  AlertCircle,
} from "lucide-react";
import RiskBadge from "../components/RiskBadge";

const Dashboard = () => {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <header className="mb-10 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-2">Health Dashboard</h1>
          <p className="text-slate-500">
            Your recent metrics and triage history.
          </p>
        </div>
        <div className="text-right">
          <RiskBadge level="LOW" />
          <p className="text-[10px] text-slate-400 mt-1">
            LAST ASSESSMENT: TODAY, 2:45 PM
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
        <div className="lg:col-span-2 glass-card h-[400px] flex items-center justify-center relative overflow-hidden">
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-medical-primary/5 to-transparent" />
          <p className="text-slate-400 flex items-center gap-2">
            <TrendingUp size={20} />
            Risk Trend Visualization coming soon
          </p>
        </div>

        {/* Sidebar Alerts */}
        <div className="space-y-6">
          <div className="glass-card bg-red-50/50 border-red-100">
            <div className="flex items-start gap-4 text-red-700">
              <AlertCircle className="shrink-0 mt-1" />
              <div>
                <h4 className="font-bold">Medical Alert</h4>
                <p className="text-xs">
                  Based on your last symptoms, we recommend monitoring your
                  blood pressure closely.
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card">
            <h4 className="font-bold mb-4">Recent Tests</h4>
            <div className="space-y-4">
              <TestItem
                name="Blood Analysis"
                date="Feb 12, 2026"
                status="Normal"
              />
              <TestItem
                name="X-Ray (Chest)"
                date="Feb 05, 2026"
                status="Review Required"
                urgent
              />
              <TestItem name="Eye Scan" date="Jan 28, 2026" status="Normal" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const StatCard = ({ icon, label, value, unit, change }) => (
  <motion.div whileHover={{ scale: 1.02 }} className="glass-card">
    <div className="flex justify-between items-start mb-4">
      <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-xl">
        {icon}
      </div>
      {change && (
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
            change.startsWith("+")
              ? "bg-green-100 text-green-700"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {change}
        </span>
      )}
    </div>
    <div className="space-y-1">
      <p className="text-slate-500 text-sm font-medium">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold">{value}</span>
        <span className="text-slate-400 text-xs font-bold uppercase">
          {unit}
        </span>
      </div>
    </div>
  </motion.div>
);

const TestItem = ({ name, date, status, urgent }) => (
  <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0 dark:border-slate-800">
    <div>
      <p className="text-sm font-bold">{name}</p>
      <p className="text-[10px] text-slate-400 uppercase">{date}</p>
    </div>
    <span
      className={`text-[10px] px-2 py-1 rounded-md ${
        urgent
          ? "bg-red-100 text-red-600 font-bold"
          : "bg-slate-100 text-slate-600"
      }`}
    >
      {status}
    </span>
  </div>
);

export default Dashboard;
