import { Mic, MicOff } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const VoiceToggle = ({ isActive, onClick }) => {
  return (
    <div className="flex flex-col items-center space-y-2">
      <button
        onClick={onClick}
        className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 ${
          isActive
            ? "bg-red-500 text-white shadow-lg shadow-red-500/30 ring-4 ring-red-100 dark:ring-red-900/20"
            : "bg-medical-primary text-white shadow-lg shadow-teal-500/30"
        }`}
      >
        <AnimatePresence mode="wait">
          {isActive ? (
            <motion.div
              key="off"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
            >
              <MicOff size={24} />
            </motion.div>
          ) : (
            <motion.div
              key="on"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
            >
              <Mic size={24} />
            </motion.div>
          )}
        </AnimatePresence>

        {isActive && (
          <div className="absolute -inset-2 rounded-full border-2 border-red-400 animate-ping opacity-25" />
        )}
      </button>

      {isActive && (
        <div className="flex items-end justify-center h-4 space-x-[2px]">
          {[1, 2, 3, 4, 3, 2, 1].map((h, i) => (
            <motion.div
              key={i}
              className="w-[3px] bg-red-400 rounded-full"
              animate={{ height: ["20%", "100%", "20%"] }}
              transition={{
                repeat: Infinity,
                duration: 0.8,
                delay: i * 0.1,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>
      )}
      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
        {isActive ? "Listening..." : "Push to Talk"}
      </span>
    </div>
  );
};

export default VoiceToggle;
