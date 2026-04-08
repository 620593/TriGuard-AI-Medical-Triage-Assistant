const fs = require('fs');
const path = require('path');

const dirs = [
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\pages',
  'C:\\Users\\acer\\Desktop\\Mini Project\\TriGuard-AI-Medical-Triage-Assistant\\frontend\\src\\components',
];

function processFile(fullPath) {
  let content = fs.readFileSync(fullPath, 'utf8');
      
  content = content.replace(/\s+drop-(?=\s|")/g, '');
  content = content.replace(/\s+shadow(?=\s|")/g, '');
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
      if (file !== 'assets' && file !== 'contexts') {
        processDir(fullPath);
      }
    } else if (fullPath.endsWith('.jsx')) {
      processFile(fullPath);
    }
  }
}

dirs.forEach(processDir);
