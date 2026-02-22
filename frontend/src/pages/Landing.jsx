import { motion } from "framer-motion";
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
            className="inline-flex items-center space-x-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-4 py-2 rounded-full mb-8 shadow-sm"
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
            className="text-5xl md:text-7xl font-bold text-slate-900 dark:text-white mb-8 leading-tight"
          >
            Intelligent Triage. <br />
            <span className="bg-gradient-to-r from-medical-primary to-medical-secondary bg-clip-text text-transparent">
              Safe & Fast Advice.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-slate-500 max-w-3xl mx-auto mb-12"
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
              className="px-8 py-4 bg-medical-primary text-white rounded-2xl font-bold flex items-center space-x-2 hover:bg-medical-secondary transition-all shadow-lg shadow-teal-500/20"
            >
              <span>Start Free Triage</span>
              <ArrowRight size={20} />
            </Link>
            <button className="px-8 py-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl font-bold hover:bg-slate-50 transition-all">
              How it works
            </button>
          </motion.div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-24 px-6 bg-slate-50 dark:bg-slate-950/50">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Mic className="text-purple-500" />}
              title="Voice Mode"
              description="Speak naturally about your concerns. Our AI understands medical symptoms across multiple languages."
            />
            <FeatureCard
              icon={<Search className="text-blue-500" />}
              title="OCR & X-Ray"
              description="Upload medical reports or X-ray images for instant AI-powered pre-diagnosis and risk analysis."
            />
            <FeatureCard
              icon={<Shield className="text-emerald-500" />}
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
  <motion.div whileHover={{ y: -5 }} className="glass-card hover:bg-white">
    <div className="w-12 h-12 rounded-2xl bg-white dark:bg-slate-800 flex items-center justify-center mb-6 shadow-sm border border-slate-100 dark:border-slate-700">
      {icon}
    </div>
    <h3 className="text-xl font-bold mb-4">{title}</h3>
    <p className="text-slate-500 leading-relaxed text-sm">{description}</p>
  </motion.div>
);

export default Landing;
