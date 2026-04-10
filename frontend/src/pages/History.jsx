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
  X,
} from "lucide-react";
import { triageAPI } from "../api/client";
import RiskBadge from "../components/RiskBadge";

const History = () => {
  const [reports, setReports] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const [isDeleting, setIsDeleting] = useState(null);
  const [selectedChat, setSelectedChat] = useState(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");

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

  const handleOpenChat = async (report) => {
    const sessionId = report?.session_id;
    if (!sessionId) {
      setSelectedChat({
        sessionId: "",
        messages: [],
        title: "No conversation data found for this report.",
      });
      return;
    }

    setIsChatLoading(true);
    setChatError("");

    try {
      const res = await triageAPI.getSessionChat(sessionId);
      const messages = res?.data?.messages || [];
      setSelectedChat({
        sessionId,
        messages,
        title: `Conversation (${messages.length} messages)`,
      });
    } catch (err) {
      console.error("Failed to load session chat:", err);
      setChatError("Could not load full chat history for this report.");
      setSelectedChat({
        sessionId,
        messages: [],
        title: "Conversation unavailable",
      });
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <header className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3 text-white drop-shadow-md">
          <Shield className="text-teal-400 drop-shadow-sm" />
          Triage History
        </h1>
        <p className="text-slate-300 mt-2 font-light">
          View and manage your past AI health assessments.
        </p>
      </header>

      {/* Search & Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
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
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
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
                onOpenChat={() => handleOpenChat(report)}
                onDelete={(e) => handleDelete(report._id, e)}
                isDeleting={isDeleting === report._id}
              />
            ))
          ) : (
            <div className="text-center py-20 skeuo-panel p-6">
              <FileText className="mx-auto text-slate-300 mb-4" size={48} />
              <p className="text-slate-500">
                No medical reports found matching your criteria.
              </p>
            </div>
          )}
        </div>
      )}

      {selectedChat && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-3xl max-h-[85vh] skeuo-panel p-5 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4 border-b border-slate-700/50 pb-3">
              <div>
                <h2 className="text-xl font-bold text-white">
                  {selectedChat.title}
                </h2>
                {selectedChat.sessionId && (
                  <p className="text-xs text-slate-400 mt-1">
                    Session: {selectedChat.sessionId}
                  </p>
                )}
              </div>
              <button
                className="p-2 rounded-full bg-slate-700/40 text-slate-300 hover:bg-slate-700/70"
                onClick={() => setSelectedChat(null)}
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="overflow-y-auto pr-1 space-y-3">
              {isChatLoading ? (
                <div className="py-10 text-center text-slate-400 flex flex-col items-center gap-3">
                  <Loader2 className="animate-spin" size={24} />
                  <p>Loading full chat history...</p>
                </div>
              ) : chatError ? (
                <p className="text-red-300 text-sm">{chatError}</p>
              ) : selectedChat.messages.length === 0 ? (
                <p className="text-slate-400 text-sm">
                  No saved chat messages for this session.
                </p>
              ) : (
                selectedChat.messages.map((m, idx) => {
                  const isUser = m.role === "user";
                  return (
                    <div
                      key={`${m.role}-${idx}`}
                      className={`p-3 rounded-xl border ${isUser ? "bg-slate-800/60 border-slate-700 text-slate-100" : "bg-teal-500/10 border-teal-500/30 text-slate-100"}`}
                    >
                      <p className="text-[10px] uppercase tracking-wider mb-1 text-slate-400 font-bold">
                        {isUser ? "You" : "TriGuard"}
                      </p>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">
                        {m.content}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ReportCard = ({ report, onOpenChat, onDelete, isDeleting }) => {
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
      onClick={onOpenChat}
      className="skeuo-panel p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 hover:-translate-y-1 transition-transform cursor-pointer"
    >
      <div className="flex items-center gap-4">
        <div
          className={`p-3 rounded-2xl backdrop-blur-md border ${data?.risk_level === "CRITICAL" ? "bg-red-500/20 text-red-300 border-red-500/30" : "bg-teal-500/10 text-teal-400 border-teal-500/20"}`}
        >
          <Activity size={24} />
        </div>
        <div>
          <h3 className="font-bold text-lg leading-tight text-white">
            {data?.symptoms?.slice(0, 3).join(", ") || "General Assessment"}
          </h3>
          <div className="flex items-center gap-3 text-xs text-slate-400 mt-1 uppercase font-bold tracking-wider">
            <span className="flex items-center gap-1">
              <Calendar size={12} /> {date}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end border-t md:border-t-0 pt-4 md:pt-0">
        <div className="text-right">
          <RiskBadge level={data?.risk_level} />
          <p className="text-[10px] text-slate-400 mt-1 uppercase font-bold">
            SCORE: {data?.risk_score || "N/A"}/10
          </p>
        </div>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="p-2 ml-4 rounded-full bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-colors border border-red-500/0 hover:border-red-500/50 disabled:opacity-50"
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
