const fs = require('fs');
let content = fs.readFileSync('frontend/src/App.tsx', 'utf8');

content = content.replace(
  /setNodes\(\(nds\) => nds\.filter\(\(n\) => n\.id !== editingTable\.id\)\);/g,
  `setNodes((nds) => nds.filter((n) => n.id !== editingTable.id));
                        setEdges((eds) => eds.filter((e) => e.source !== editingTable.id && e.target !== editingTable.id));`
);

fs.writeFileSync('frontend/src/App.tsx', content);
