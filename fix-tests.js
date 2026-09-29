const fs = require('fs');

let content = fs.readFileSync('frontend/src/erd/__tests__/coverageEdges.test.ts', 'utf8');
content = content.replace("expect(dbml).toContain('Ref: child.parent_id > sales.parent.parent_id')", "expect(dbml).toContain('Ref: child.parent_id > sales.parent.parent_id')");
console.log(content);
