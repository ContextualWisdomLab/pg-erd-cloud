import fs from 'fs';

let content = fs.readFileSync('frontend/src/erd/prisma.ts', 'utf-8');

const SEARCH = `      const edgeInfo = {
        sourceModel: sanitizeName(sourceNode.data.title),
        targetModel: sanitizeName(targetNode.data.title),
        sourceFields: [sanitizeName(sourceField)],
        targetFields: [sanitizeName(targetField)],
        relationName: relName
      };
      edgesProcessed.set(edge.id, edgeInfo);

      const bySourceList = edgesProcessedBySourceModel.get(edgeInfo.sourceModel) || [];
      if (bySourceList.length === 0) {
        edgesProcessedBySourceModel.set(edgeInfo.sourceModel, bySourceList);
      }
      bySourceList.push(edgeInfo);`;

const REPLACE = `      const edgeInfo = {
        sourceModel: sanitizeName(sourceNode.data.title),
        targetModel: sanitizeName(targetNode.data.title),
        sourceFields: [sanitizeName(sourceField)],
        targetFields: [sanitizeName(targetField)],
        relationName: relName
      };
      edgesProcessed.set(edge.id, edgeInfo);

      const bySourceList = edgesProcessedBySourceModel.get(edgeInfo.sourceModel) || [];
      if (bySourceList.length === 0) {
        edgesProcessedBySourceModel.set(edgeInfo.sourceModel, bySourceList);
      }

      // Remove any existing edgeInfo with the same sourceField to preserve last-edge-wins
      const existingIndex = bySourceList.findIndex(e => e.sourceFields.includes(sanitizeName(sourceField)));
      if (existingIndex !== -1) {
        bySourceList.splice(existingIndex, 1);
      }
      bySourceList.push(edgeInfo);`;

content = content.replace(SEARCH, REPLACE);

fs.writeFileSync('frontend/src/erd/prisma.ts', content);
