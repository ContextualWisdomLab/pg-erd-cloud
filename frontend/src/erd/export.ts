import type { Node, Edge } from '@xyflow/react';
import type { TableNodeData } from './convert';

export function exportDDL(nodes: Node<TableNodeData>[], edges: Edge[]): string {
  let ddl = '-- Generated DDL\n\n';

  // Export tables
  for (const node of nodes) {
    const tableTitle = node.data.title || node.id;
    ddl += `CREATE TABLE "${tableTitle}" (\n`;

    const cols = node.data.columns || [];
    const colLines = cols.map((c) => {
      let line = `  "${c.column_name}" ${c.data_type}`;
      if (c.is_not_null) {
        line += ' NOT NULL';
      }
      return line;
    });

    // Handle primary keys
    const pkCols = cols.filter(c => c.is_pk).map(c => `"${c.column_name}"`);
    if (pkCols.length > 0) {
      colLines.push(`  PRIMARY KEY (${pkCols.join(', ')})`);
    }

    ddl += colLines.join(',\n');
    ddl += '\n);\n\n';
  }

  // Export foreign keys
  for (const edge of edges) {
    const sourceNode = nodes.find(n => n.id === edge.source);
    const targetNode = nodes.find(n => n.id === edge.target);

    if (sourceNode && targetNode) {
      const constraintName = edge.label ? edge.label : `fk_${edge.source}_${edge.target}`;
      ddl += `ALTER TABLE "${sourceNode.data.title || sourceNode.id}"\n`;
      ddl += `  ADD CONSTRAINT "${constraintName}"\n`;
      // For simplicity in UI without detailed column mapping we just put placeholder comments
      ddl += `  FOREIGN KEY (/* source columns */)\n`;
      ddl += `  REFERENCES "${targetNode.data.title || targetNode.id}" (/* target columns */);\n\n`;
    }
  }

  return ddl;
}
