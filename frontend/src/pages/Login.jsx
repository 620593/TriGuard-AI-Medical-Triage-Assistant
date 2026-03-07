import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { authAPI } from "../api/client";
import {
  LogIn,
  UserPlus,
  AlertCircle,
  Shield,
  Brain,
  Mic,
  Lock,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const token = localStorage.getItem("token");
  if (token) return <Navigate to="/dashboard" replace />;

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      let data;
      if (isLogin) {
        const response = await authAPI.login({
          email: formData.email,
          password: formData.password,
        });
        data = response.data;
      } else {
        const response = await authAPI.register(formData);
        data = response.data;
      }

      // Save to localStorage
      localStorage.setItem("token", data.access_token);
      localStorage.setItem(
        "user",
        JSON.stringify({
          user_id: data.user_id,
          name: data.name,
          email: formData.email,
        }),
      );

      navigate("/dashboard");
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "An error occurred during authentication.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#080e1c] font-mono">
      {/* LEFT PANEL */}
      <div className="hidden lg:flex flex-col justify-center w-[40%] bg-[#04070d] relative overflow-hidden px-12 border-r border-white/5 shadow-2xl">
        {/* Animated Radial Gradient Background */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(34,211,238,0.08),transparent_60%)] animate-pulse duration-[3000ms]" />

        <div className="relative z-10 flex flex-col h-full py-16">
          <div className="flex-1 flex flex-col justify-center mb-10">
            <Shield className="w-16 h-16 text-cyan-400 mb-6 drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]" />
            <h1
              className="text-4xl font-bold text-white mb-2"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              TriGuard AI
            </h1>
            <p className="text-slate-400 text-sm mb-10">
              Your intelligent health risk assistant
            </p>

            <div className="w-12 h-1 bg-gradient-to-r from-cyan-400 to-blue-500 rounded-full mb-10"></div>

            <div className="space-y-6">
              <div className="flex items-center space-x-4 text-slate-300">
                <div className="p-2 bg-white/5 rounded-lg border border-white/10">
                  <Brain className="w-5 h-5 text-cyan-400" />
                </div>
                <span className="text-sm font-medium">AI Symptom Analysis</span>
              </div>
              <div className="flex items-center space-x-4 text-slate-300">
                <div className="p-2 bg-white/5 rounded-lg border border-white/10">
                  <Mic className="w-5 h-5 text-blue-400" />
                </div>
                <span className="text-sm font-medium">Voice Triage</span>
              </div>
              <div className="flex items-center space-x-4 text-slate-300">
                <div className="p-2 bg-white/5 rounded-lg border border-white/10">
                  <Lock className="w-5 h-5 text-indigo-400" />
                </div>
                <span className="text-sm font-medium">Private & Secure</span>
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-600 font-medium">
            V6 &middot; Final Architecture
          </div>
        </div>
      </div>

      {/* RIGHT PANEL */}
      <div className="flex-1 flex flex-col justify-center items-center px-4 sm:px-6 relative">
        <div className="w-full max-w-md bg-[#080e1c] sm:bg-[#0f172a]/30 sm:border sm:border-white/5 sm:rounded-2xl sm:p-8 sm:shadow-2xl sm:backdrop-blur-sm relative z-10 overflow-hidden">
          {/* Tab Toggle */}
          <div className="flex p-1 bg-black/40 rounded-xl mb-8 border border-white/5 relative z-10">
            <button
              onClick={() => {
                setIsLogin(true);
                setError("");
              }}
              className={`flex-1 py-3 text-sm font-bold rounded-lg transition-all flex justify-center items-center ${
                isLogin
                  ? "text-cyan-400 shadow bg-white/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => {
                setIsLogin(false);
                setError("");
              }}
              className={`flex-1 py-3 text-sm font-bold rounded-lg transition-all flex justify-center items-center ${
                !isLogin
                  ? "text-cyan-400 shadow bg-white/5"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Create Account
            </button>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={isLogin ? "login" : "register"}
              initial={{ opacity: 0, x: isLogin ? -20 : 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: isLogin ? 20 : -20 }}
              transition={{ duration: 0.2 }}
              className="relative z-10"
            >
              <form onSubmit={handleSubmit} className="space-y-4">
                {!isLogin && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Full Name
                    </label>
                    <input
                      type="text"
                      name="name"
                      required={!isLogin}
                      value={formData.name}
                      onChange={handleChange}
                      className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-400 focus:border-cyan-400 transition-all shadow-inner"
                      placeholder="John Doe"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    name="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-400 focus:border-cyan-400 transition-all shadow-inner"
                    placeholder="you@example.com"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    name="password"
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-400 focus:border-cyan-400 transition-all shadow-inner"
                    placeholder="••••••••"
                  />
                </div>

                {error && (
                  <div className="flex items-center space-x-3 bg-red-950/40 text-red-500 p-4 rounded-xl border border-red-900/50 text-sm mt-4 shadow-inner">
                    <AlertCircle size={18} className="shrink-0 text-red-500" />
                    <p className="font-medium">{error}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 flex items-center justify-center space-x-2 py-3 mt-4 rounded-xl text-white text-sm font-bold shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_25px_rgba(6,182,212,0.5)] transition-all disabled:opacity-50 disabled:cursor-not-allowed border border-white/10"
                >
                  {isLoading ? (
                    <span className="animate-pulse flex items-center gap-2">
                      Processing...
                    </span>
                  ) : isLogin ? (
                    <>
                      <LogIn size={18} />
                      <span>Sign In with Email</span>
                    </>
                  ) : (
                    <>
                      <UserPlus size={18} />
                      <span>Create Account</span>
                    </>
                  )}
                </button>
              </form>
            </motion.div>
          </AnimatePresence>

          <div className="relative my-8 z-10">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10"></div>
            </div>
            <div className="relative flex justify-center text-xs font-semibold uppercase tracking-widest text-slate-500">
              <span className="px-4 bg-[#080e1c] sm:bg-[#0f172a]">
                Or continue with
              </span>
            </div>
          </div>

          <button
            onClick={() => {
              const BASE_URL = "http://localhost:8000/api/v3";
              window.location.href = BASE_URL + "/auth/google";
            }}
            className="w-full bg-white text-slate-900 flex items-center justify-center space-x-3 py-3 rounded-xl text-sm font-bold hover:bg-slate-100 transition-colors shadow-md relative z-10"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="currentColor"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="currentColor"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="currentColor"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            <span>Google</span>
          </button>
        </div>
      </div>
    </div>
  );
}
