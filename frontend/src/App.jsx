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
// Placeholder for Reports since we didn't specify it yet, let's just use it same as dashboard or empty
const Reports = () => <div className="p-8">Reports & History Content</div>;

function App() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        {/* Modern Navigation */}
        <nav className="glass sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-2">
            <Shield className="w-8 h-8 text-medical-primary" />
            <span className="text-2xl font-bold bg-gradient-to-r from-medical-primary to-medical-secondary bg-clip-text text-transparent">
              TriGuard AI
            </span>
          </Link>

          {/* Desktop Menu */}
          <div className="hidden md:flex items-center space-x-8">
            <Link
              to="/dashboard"
              className="flex items-center space-x-1 hover:text-medical-primary transition-colors"
            >
              <LayoutDashboard size={18} />
              <span>Dashboard</span>
            </Link>
            <Link
              to="/triage"
              className="flex items-center space-x-1 hover:text-medical-primary transition-colors"
            >
              <MessageSquare size={18} />
              <span>AI Triage</span>
            </Link>
            <Link
              to="/reports"
              className="flex items-center space-x-1 hover:text-medical-primary transition-colors"
            >
              <History size={18} />
              <span>History</span>
            </Link>
          </div>

          <button
            className="md:hidden"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X /> : <Menu />}
          </button>
        </nav>

        {/* Content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/triage" element={<TriageChat />} />
            <Route path="/reports" element={<Reports />} />
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
