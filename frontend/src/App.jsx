import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import {
  Activity,
  Shield,
  LayoutDashboard,
  History,
  MessageSquare,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";

import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import TriageChat from "./pages/TriageChat";
import HistoryPage from "./pages/History";

function App() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        {/* Modern Navigation */}
        <nav className="skeuo-panel !rounded-none !border-x-0 !border-t-0 sticky top-0 z-50 px-6 py-4 flex items-center justify-between shadow-[0_4px_10px_rgba(0,0,0,0.05)]">
          <Link to="/" className="flex items-center space-x-2">
            <Shield className="w-8 h-8 text-medical-primary drop-shadow-md" />
            <span className="text-2xl font-bold bg-gradient-to-r from-[#0d9488] to-[#0f766e] bg-clip-text text-transparent drop-shadow-sm">
              TriGuard AI
            </span>
          </Link>

          {/* Navigation Menu */}
          <div
            className={`${isMenuOpen ? "absolute top-[72px] left-0 right-0 bg-black/80 backdrop-blur-xl border-b border-white/10 shadow-lg p-4 flex flex-col space-y-3" : "hidden"} md:flex md:static md:flex-row md:space-y-0 md:space-x-4 items-center`}
          >
            <Link
              to="/dashboard"
              onClick={() => setIsMenuOpen(false)}
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <LayoutDashboard size={16} />
              <span>Dashboard</span>
            </Link>
            <Link
              to="/triage"
              onClick={() => setIsMenuOpen(false)}
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <MessageSquare size={16} />
              <span>AI Triage</span>
            </Link>
            <Link
              to="/reports"
              onClick={() => setIsMenuOpen(false)}
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <History size={16} />
              <span>History</span>
            </Link>
          </div>

          <button
            className="md:hidden skeuo-btn p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </nav>

        {/* Content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/triage" element={<TriageChat />} />
            <Route path="/reports" element={<HistoryPage />} />
          </Routes>
        </main>

        <footer className="p-8 text-center text-slate-500 text-sm">
          &copy; 2026 TriGuard AI — Medical Triage System. All rights reserved.
        </footer>
      </div>
    </Router>
  );
}

export default App;
