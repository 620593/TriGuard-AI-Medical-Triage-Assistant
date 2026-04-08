const fs = require('fs');
const path = require('path');

const dirs = [
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\pages',
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\components',
];

function processFile(fullPath) {
  let content = fs.readFileSync(fullPath, 'utf8');
      
  // Replace text-[var(--text-primary)] to text-[var(--accent-primary)] in headings
  content = content.replace(/<(h[1-3])\s+className="([^"]*?)text-\[var\(--text-primary\)\]([^"]*?)"/g, (match, p1, p2, p3) => {
    return `<${p1} className="${p2}text-[var(--accent-primary)]${p3}"`;
  });
  
  // also catch cases where it was text-slate-900 or something else remaining
  content = content.replace(/<(h[1-3])\s+className="([^"]*?)text-slate-900([^"]*?)"/g, (match, p1, p2, p3) => {
    return `<${p1} className="${p2}text-[var(--accent-primary)]${p3}"`;
  });

  fs.writeFileSync(fullPath, content);
  console.log(`Processed ${fullPath}`);
}

function processDir(dir) {
  if (!fs.existsSync(dir)) return;
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      if (file !== 'assets' && file !== 'contexts') {
        processDir(fullPath);
      }
    } else if (fullPath.endsWith('.jsx')) {
      processFile(fullPath);
    }
  }
}

dirs.forEach(processDir);
