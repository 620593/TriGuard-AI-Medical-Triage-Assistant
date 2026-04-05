// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Activity,
  Zap,
  Heart,
  ArrowRight,
  Mic,
  Search,
  FileText,
} from "lucide-react";
import { Link } from "react-router-dom";

const Landing = () => {
  return (
    <div className="overflow-hidden">
      {/* Hero Section */}
      <section className="relative pt-20 pb-32 px-6">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl aspect-[2/1] bg-gradient-to-b from-medical-primary/10 to-transparent rounded-full blur-3xl -z-10" />

        <div className="max-w-5xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center space-x-2 skeuo-panel !rounded-full px-4 py-2 mb-8"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-medical-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-medical-primary"></span>
            </span>
            <span className="text-sm font-medium">v3.0 Production Ready</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold text-gray-800 mb-8 leading-tight drop-shadow-sm"
          >
            Intelligent Triage. <br />
            <span className="bg-gradient-to-r from-orange-500 to-amber-500 bg-clip-text text-transparent drop-shadow-sm">
              Safe & Fast Advice.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-gray-500 max-w-3xl mx-auto mb-12 drop-shadow-sm font-light"
          >
            Your AI-powered medical companion for symptom checking, X-ray
            analysis, and health risk assessment—accessible anywhere, anytime.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link
              to="/triage"
              className="px-8 py-4 skeuo-btn-primary flex items-center space-x-2 text-lg"
            >
              <span>Start Free Triage</span>
              <ArrowRight size={20} />
            </Link>
            <button className="px-8 py-4 skeuo-btn flex items-center space-x-2 text-lg">
              How it works
            </button>
          </motion.div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Mic className="text-orange-500" />}
              title="Voice Mode"
              description="Speak naturally about your concerns. Our AI understands medical symptoms across multiple languages."
            />
            <FeatureCard
              icon={<Search className="text-amber-500" />}
              title="OCR & X-Ray"
              description="Upload medical reports or X-ray images for instant AI-powered pre-diagnosis and risk analysis."
            />
            <FeatureCard
              icon={<Shield className="text-rose-500" />}
              title="Risk Guard"
              description="Immediate crisis override system. If your symptoms indicate danger, we guide you to urgent care."
            />
          </div>
        </div>
      </section>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <motion.div
    whileHover={{ y: -5, scale: 1.02 }}
    className="skeuo-panel p-6 relative group overflow-hidden bg-white border border-[#fed7aa] rounded-2xl shadow-sm transition-all duration-200"
  >
    <div className="absolute inset-0 bg-gradient-to-br from-orange-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    <div className="w-12 h-12 rounded-2xl bg-[#ffedd5] flex items-center justify-center mb-6 border border-[#fed7aa] shadow-sm">
      {icon}
    </div>
    <h3 className="text-xl font-bold mb-4 text-gray-800">{title}</h3>
    <p className="text-gray-500 leading-relaxed text-sm font-light">
      {description}
    </p>
  </motion.div>
);

export default Landing;
