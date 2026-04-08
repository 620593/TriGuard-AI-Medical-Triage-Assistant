import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useNavigate,
  Navigate,
} from "react-router-dom";
import {
  Shield,
  LayoutDashboard,
  History,
  MessageSquare,
  Menu,
  X,
  LogIn,
  LogOut,
  User,
  Moon,
  Sun,
  Palette
} from "lucide-react";
import { useState, useEffect } from "react";

import { ThemeProvider, useTheme } from "./contexts/ThemeContext";

import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import TriageChat from "./pages/TriageChat";
import HistoryPage from "./pages/History";
import Login from "./pages/Login";

function Navigation() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const { theme, setTheme, accent, setAccent } = useTheme();

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

  const toggleTheme = () => setTheme(theme === "light" ? "dark" : "light");

  const accents = ["orange", "blue", "green"];
  const cycleAccent = () => {
    const nextIndex = (accents.indexOf(accent) + 1) % accents.length;
    setAccent(accents[nextIndex]);
  };

  return (
    <nav className="w-full fixed top-0 left-0 right-0 bg-[var(--bg-secondary)] border-b border-[var(--panel-border)] z-50">
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center space-x-6">
          <Link to="/" className="flex items-center space-x-2">
            <Shield className="w-8 h-8 text-[var(--accent-primary)]" />
            <span className="text-2xl font-bold text-[var(--text-primary)] hidden sm:inline-block">
              TriGuard AI
            </span>
          </Link>

          {/* Desktop Links - Left/Center */}
          <div className="hidden md:flex items-center space-x-2">
            <Link
              to="/dashboard"
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <LayoutDashboard size={16} />
              <span>Dashboard</span>
            </Link>
            <Link
              to="/triage"
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <MessageSquare size={16} />
              <span>AI Triage</span>
            </Link>
            <Link
              to="/reports"
              className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm"
            >
              <History size={16} />
              <span>History</span>
            </Link>
          </div>
        </div>

        {/* Right side icons */}
        <div className="flex items-center space-x-3">
          <button
            onClick={cycleAccent}
            className="p-2 skeuo-btn rounded-full border-transparent hover:bg-[var(--accent-light)]"
            title="Change Accent Color"
          >
            <Palette size={20} className="text-[var(--accent-primary)]" />
          </button>
          <button
            onClick={toggleTheme}
            className="p-2 skeuo-btn rounded-full border-transparent hover:bg-[var(--accent-light)]"
            title="Toggle Dark Mode"
          >
            {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
          </button>

          <div className="hidden md:flex items-center ml-2 border-l border-[var(--panel-border)] pl-4">
            {user ? (
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2 text-sm text-[var(--text-secondary)] font-medium">
                  <User size={16} />
                  <span>{user.name}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="text-red-500 hover:text-red-600 transition-colors flex items-center space-x-1 text-sm font-medium"
                >
                  <LogOut size={16} />
                  <span>Logout</span>
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm text-[var(--accent-primary)] border-[var(--accent-primary)]"
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
        </div>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="absolute top-full left-0 right-0 bg-[var(--bg-secondary)] border-b border-[var(--panel-border)] p-4 flex flex-col space-y-3 md:hidden z-50">
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
          <div className="border-t border-[var(--panel-border)] pt-3 mt-2">
            {user ? (
              <div className="flex flex-col space-y-3">
                <div className="flex items-center space-x-2 text-sm text-[var(--text-secondary)] font-medium">
                  <User size={16} />
                  <span>{user.name}</span>
                </div>
                <button
                  onClick={() => {
                    handleLogout();
                    setIsMenuOpen(false);
                  }}
                  className="text-red-500 hover:text-red-600 transition-colors flex items-center space-x-2 text-sm font-medium w-full text-left"
                >
                  <LogOut size={16} />
                  <span>Logout</span>
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                onClick={() => setIsMenuOpen(false)}
                className="skeuo-btn px-4 py-2 flex items-center space-x-2 text-sm text-[var(--accent-primary)] border-[var(--accent-primary)]"
              >
                <LogIn size={16} />
                <span>Sign In</span>
              </Link>
            )}
          </div>
        </div>
      )}
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
    <ThemeProvider>
      <Router>
        <OAuthHandler />
        <div className="min-h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-200">
          <Navigation />

          <main className="flex-1 w-full pt-20">
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

          <footer className="p-8 text-center text-[var(--text-secondary)] text-sm">
            &copy; 2026 TriGuard AI — Medical Triage System. All rights reserved.
          </footer>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;
