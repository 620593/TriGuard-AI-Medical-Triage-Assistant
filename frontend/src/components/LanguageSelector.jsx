import { Globe } from "lucide-react";

export default function LanguageSelector({ language, setLanguage }) {
  return (
    <div className="relative group inline-block">
      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
        className="appearance-none skeuo-btn px-4 py-1.5 pr-8 !rounded-full text-sm flex items-center outline-none cursor-pointer bg-transparent text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-teal-500/50"
      >
        <option value="en" className="text-slate-800 dark:text-slate-800">English</option>
        <option value="hi" className="text-slate-800 dark:text-slate-800">Hindi (हिंदी)</option>
        <option value="te" className="text-slate-800 dark:text-slate-800">Telugu (తెలుగు)</option>
      </select>
      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 dark:text-slate-400">
        <Globe size={14} />
      </div>
    </div>
  );
}
