const fs = require('fs');
const path = require('path');

const dirs = [
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\pages',
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\components',
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src'
];

function processFile(fullPath) {
  let content = fs.readFileSync(fullPath, 'utf8');
      
  // Remove shadows
  content = content.replace(/\bshadow(?:-[a-zA-Z0-9\[\]\-#]+)?\b/g, '');
  content = content.replace(/\bdrop-shadow(?:-[a-zA-Z0-9\[\]\-#\(\)]+)?\b/g, '');
  
  // Remove gradients and transitions that rely on them
  content = content.replace(/\bbg-gradient-to-[a-brt]+\b/g, '');
  content = content.replace(/\bfrom-[a-zA-Z0-9\[\]\-#\(\)]+\b/g, '');
  content = content.replace(/\bto-[a-zA-Z0-9\[\]\-#\(\)]+\b/g, '');
  content = content.replace(/\bbg-\[radial-gradient[^\]]+\]\b/g, '');
  content = content.replace(/\bbg-clip-text\b/g, '');
  content = content.replace(/\btext-transparent\b/g, '');
  
  // Also clean up multiple spaces created by replacements in classNames
  content = content.replace(/className=" *([^"]*?) *"/g, (match, p1) => {
    return `className="${p1.replace(/\s+/g, ' ').trim()}"`;
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
      if (file !== 'assets' && file !== 'api' && file !== 'contexts') {
        processDir(fullPath);
      }
    } else if (fullPath.endsWith('.jsx') || fullPath.endsWith('.js')) {
      processFile(fullPath);
    }
  }
}

processDir(dirs[0]);
processDir(dirs[1]);

const appPath = path.join(dirs[2], 'App.jsx');
if (fs.existsSync(appPath)) {
  processFile(appPath);
}
