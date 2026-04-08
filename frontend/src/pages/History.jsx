import { useState, useEffect } from "react";
// eslint-disable-next-line no-unused-vars
import { motion } from "framer-motion";
import {
  Calendar,
  MapPin,
  ChevronRight,
  Activity,
  Shield,
  AlertCircle,
  Loader2,
  FileText,
  Search,
  Trash2,
} from "lucide-react";
import { triageAPI } from "../api/client";
import RiskBadge from "../components/RiskBadge";

const History = () => {
  const [reports, setReports] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const [isDeleting, setIsDeleting] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [reportsRes] = await Promise.all([
          triageAPI.getReports(),
          triageAPI.getSessions(),
        ]);
        setReports(reportsRes.data);
      } catch (error) {
        console.error("Discovery error:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleDelete = async (reportId, e) => {
    e.stopPropagation(); // Prevent card click
    if (window.confirm("Are you sure you want to delete this triage record?")) {
      try {
        setIsDeleting(reportId);
        await triageAPI.deleteReport(reportId);
        setReports((prev) => prev.filter((r) => r._id !== reportId));
      } catch (error) {
        console.error("Failed to delete report:", error);
        alert("Failed to delete the report. Please try again.");
      } finally {
        setIsDeleting(null);
      }
    }
  };

  const filteredReports = reports.filter((r) => {
    if (!searchTerm) return true;

    const terms = searchTerm.toLowerCase().split(/\s+/).filter(Boolean);
    const data = r.report || {};

    // For each word the user typed, we check if it matches ANY field.
    // We require ALL words to match somewhere in the document.
    return terms.every((term) => {
      const hasSymptom = (data.symptoms || []).some((s) =>
        s.toLowerCase().includes(term),
      );
      const hasRiskLevel = (data.risk_level || "").toLowerCase().includes(term);
      const hasScore = String(data.risk_score || "").includes(term);
      const hasAnyText = JSON.stringify(data).toLowerCase().includes(term);

      const date = new Date(r.created_at)
        .toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
        .toLowerCase();
      const hasDate = date.includes(term);

      return hasSymptom || hasRiskLevel || hasScore || hasDate || hasAnyText;
    });
  });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3 text-[var(--accent-primary)]">
          <Shield className="text-[var(--accent-primary)]" />
          Triage History
        </h1>
        <p className="text-[var(--text-secondary)] mt-2 font-light">
          View and manage your past AI health assessments.
        </p>
      </header>

      {/* Search & Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
            size={18}
          />
          <input
            type="text"
            placeholder="Search symptoms or risk level..."
            className="w-full pl-12 pr-4 py-3 skeuo-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--text-secondary)]">
          <Loader2 className="animate-spin mb-4" size={32} />
          <p>Retrieving your encrypted health data...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReports.length > 0 ? (
            filteredReports.map((report) => (
              <ReportCard
                key={report._id}
                report={report}
                onDelete={(e) => handleDelete(report._id, e)}
                isDeleting={isDeleting === report._id}
              />
            ))
          ) : (
            <div className="text-center py-20 skeuo-panel p-6">
              <FileText className="mx-auto text-[var(--text-secondary)] mb-4" size={48} />
              <p className="text-[var(--text-secondary)]">
                No medical reports found matching your criteria.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ReportCard = ({ report, onDelete, isDeleting }) => {
  const { created_at, report: data } = report;
  const date = new Date(created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="skeuo-panel p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 hover:-translate-y-1 transition-transform cursor-pointer"
    >
      <div className="flex items-center gap-4">
        <div
          className={`p-3 rounded-2xl backdrop-blur-md border ${data?.risk_level === "CRITICAL" ? "bg-red-50 text-red-600 border-red-200" : "bg-[var(--accent-light)] text-[var(--accent-active)] border-[var(--panel-border)]"}`}
        >
          <Activity size={24} />
        </div>
        <div>
          <h3 className="font-bold text-lg leading-tight text-[var(--accent-primary)]">
            {data?.symptoms?.slice(0, 3).join(", ") || "General Assessment"}
          </h3>
          <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)] mt-1 uppercase font-bold tracking-wider">
            <span className="flex items-center gap-1">
              <Calendar size={12} /> {date}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 pt-4 md:pt-0">
        <div className="text-right">
          <RiskBadge level={data?.risk_level} />
          <p className="text-[10px] text-[var(--text-secondary)] mt-1 uppercase font-bold">
            SCORE: {data?.risk_score || "N/A"}/10
          </p>
        </div>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="p-2 ml-4 rounded-full bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700 transition-colors border border-red-200 hover:border-red-300 disabled:opacity-50"
          title="Delete Record"
        >
          {isDeleting ? (
            <Loader2 size={20} className="animate-spin" />
          ) : (
            <Trash2 size={20} />
          )}
        </button>
      </div>
    </motion.div>
  );
};

export default History;
