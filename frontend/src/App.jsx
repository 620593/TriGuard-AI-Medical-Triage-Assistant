import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useNavigate,
  Navigate,
} from "react-router-dom";
import {
  Activity,
  Shield,
  LayoutDashboard,
  History,
  MessageSquare,
  Menu,
  X,
  LogIn,
  LogOut,
  User,
} from "lucide-react";
import { useState, useEffect } from "react";

import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import TriageChat from "./pages/TriageChat";
import HistoryPage from "./pages/History";
import Login from "./pages/Login";

function Navigation() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    navigate("/login");
  };

  return (
    <nav className="skeuo-panel !rounded-none !border-x-0 !border-t-0 sticky top-0 z-50 px-6 py-4 flex items-center justify-between shadow-[0_4px_10px_rgba(0,0,0,0.05)]">
      <Link to="/" className="flex items-center space-x-2">
        <Shield className="w-8 h-8 text-medical-primary drop-shadow-md" />
        <span className="text-2xl font-bold bg-gradient-to-r from-[#0d9488] to-[#0f766e] bg-clip-text text-transparent drop-shadow-sm hidden sm:inline-block">
          TriGuard AI
        </span>
      </Link>

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

        {user ? (
          <div className="flex items-center space-x-4 ml-4">
            <div className="hidden lg:flex items-center space-x-2 text-sm text-slate-300">
              <User size={16} />
              <span>{user.name}</span>
            </div>
            <button
              onClick={() => {
                handleLogout();
                setIsMenuOpen(false);
              }}
              className="text-red-400 hover:text-red-300 transition-colors flex items-center space-x-1 text-sm font-medium"
            >
              <LogOut size={16} />
              <span>Logout</span>
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            onClick={() => setIsMenuOpen(false)}
            className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm border-medical-primary text-medical-primary"
          >
            <LogIn size={16} />
            <span>Sign In</span>
          </Link>
        )}
      </div>

      <button
        className="md:hidden skeuo-btn p-2"
        onClick={() => setIsMenuOpen(!isMenuOpen)}
      >
        {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
    </nav>
  );
}

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return children;
};

function OAuthHandler() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const name = params.get("name");
    const uid = params.get("uid");

    if (token) {
      localStorage.setItem("token", token);
      localStorage.setItem(
        "user",
        JSON.stringify({
          user_id: decodeURIComponent(uid || ""),
          name: decodeURIComponent(name || ""),
        }),
      );
      window.history.replaceState({}, "", "/dashboard");
      navigate("/dashboard", { replace: true });
    }
  }, []);

  return null;
}

function App() {
  return (
    <Router>
      <OAuthHandler />
      <div className="min-h-screen flex flex-col">
        <Navigation />

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/triage"
              element={
                <ProtectedRoute>
                  <TriageChat />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <HistoryPage />
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
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
