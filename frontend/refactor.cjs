const fs = require('fs');
const path = require('path');

const dirs = [
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\pages',
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\components'
];

const replaces = [
  [/text-gray-800/g, 'text-[var(--text-primary)]'],
  [/text-gray-500/g, 'text-[var(--text-secondary)]'],
  [/text-gray-600/g, 'text-[var(--text-secondary)]'],
  [/text-gray-400/g, 'text-[var(--text-secondary)]'],
  [/text-slate-800/g, 'text-[var(--text-primary)]'],
  [/text-slate-500/g, 'text-[var(--text-secondary)]'],
  [/text-slate-400/g, 'text-[var(--text-secondary)]'],
  [/bg-white/g, 'bg-[var(--bg-secondary)]'],
  [/bg-orange-50/g, 'bg-[var(--bg-primary)]'],
  [/from-orange-50/g, 'from-[var(--bg-primary)]'],
  [/border-\[\#fed7aa\]/g, 'border-[var(--panel-border)]'],
  [/bg-\[\#ffedd5\]/g, 'bg-[var(--accent-light)]'],
  [/from-orange-500/g, 'from-[var(--accent-primary)]'],
  [/to-amber-500/g, 'to-[var(--accent-hover)]'],
  [/text-orange-500/g, 'text-[var(--accent-primary)]'],
  [/text-orange-400/g, 'text-[var(--accent-primary)]'],
  [/text-amber-500/g, 'text-[var(--accent-hover)]'], 
  [/text-orange-600/g, 'text-[var(--accent-active)]'],
  [/text-rose-500/g, 'text-red-500'],
  [/bg-orange-100/g, 'bg-[var(--accent-light)]'],
  [/border-orange-200/g, 'border-[var(--panel-border)]'],
  [/text-orange-700/g, 'text-[var(--accent-active)]'],
  [/bg-\[\#f97316\]/g, 'bg-[var(--accent-primary)]'],
  [/hover:bg-\[\#ea580c\]/g, 'hover:bg-[var(--accent-hover)]'],
  [/ring-orange-300/g, 'ring-[var(--accent-primary)]'],
  [/border-orange-300/g, 'border-[var(--accent-primary)]'],
  [/ring-orange-400/g, 'ring-[var(--accent-primary)]'],
  [/border-slate-200/g, 'border-[var(--border-color)]']
];

function processDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      processDir(fullPath);
    } else if (fullPath.endsWith('.jsx') || fullPath.endsWith('.js')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      replaces.forEach(([regex, replacement]) => {
        content = content.replace(regex, replacement);
      });
      fs.writeFileSync(fullPath, content);
      console.log(`Processed ${fullPath}`);
    }
  }
}

dirs.forEach(processDir);
console.log('Refactoring complete.');
