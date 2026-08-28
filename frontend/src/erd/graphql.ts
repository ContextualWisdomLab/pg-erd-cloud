import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";

function escapeString(str: string): string {
  return str.replace(/"/g, '\\"').replace(/\n/g, '\\n');
}

function safeId(str: string): string {
  if (!str) return "";
  // GraphQL type names must start with a letter and contain only letters, numbers, and underscores
  let id = str.replace(/[^a-zA-Z0-9_]/g, '_');
  if (/^[0-9]/.test(id)) {
    id = '_' + id;
  }
  // Convert table names like "public.users" or "users" to PascalCase
  const parts = id.split('_').filter(Boolean);
  return parts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join('');
}

export function parseColumnNameFromHandle(handleId: string): string | null {
  if (!handleId || !handleId.startsWith('src-c-') && !handleId.startsWith('tgt-c-')) {
    // Legacy fallback or just missing prefix
    return handleId.replace(/^(src|tgt)-/, '');
  }
  const payload = handleId.replace(/^(src|tgt)-c-/, '');
  if (payload === 'empty') return '';
  const codes = payload.split('-');
  return String.fromCodePoint(...codes.map(c => parseInt(c, 16)));
}

function mapDataType(type: string): string {
  const t = type.toLowerCase();
  if (t.includes('int') || t.includes('serial')) return 'Int';
  if (t.includes('float') || t.includes('double') || t.includes('numeric') || t.includes('decimal') || t.includes('real')) return 'Float';
  if (t.includes('bool') || t.includes('boolean')) return 'Boolean';
  if (t.includes('uuid')) return 'ID';
  return 'String'; // Text, varchar, date, timestamp, json, etc.
}

export function exportGraphql(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  let output = "";

  if (nodes.length === 0) {
    return output;
  }

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  // To build relations, we need to know what to add to which type.
  // We'll collect the related fields first.
  const relatedFields = new Map<string, string[]>(); // Map of typeName -> string[] of field definitions

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);

    if (sourceNode && targetNode) {
      const sourceTypeName = safeId(sourceNode.data.title.split('.').pop() || sourceNode.data.title);
      const targetTypeName = safeId(targetNode.data.title.split('.').pop() || targetNode.data.title);

      const parsedSource = parseColumnNameFromHandle(edge.sourceHandle || "");
      const sourceCol = (sourceNode.data.columns || []).find(c => c.column_name === parsedSource);

      const parsedTarget = parseColumnNameFromHandle(edge.targetHandle || "");
      const targetCol = (targetNode.data.columns || []).find(c => c.column_name === parsedTarget);

      if (sourceCol && targetCol) {
        // Source node has the foreign key pointing to Target node.
        // So source type belongs to target type, and target type has many source types.

        // Add field to source type
        const sFields = relatedFields.get(sourceTypeName) || [];
        // fieldname might be the target type name in camelCase
        let targetFieldName = targetTypeName.charAt(0).toLowerCase() + targetTypeName.slice(1);
        sFields.push(`  ${targetFieldName}: ${targetTypeName}`);
        relatedFields.set(sourceTypeName, sFields);

        // Add field to target type (One-to-Many by default for ERDs)
        const tFields = relatedFields.get(targetTypeName) || [];
        let sourceArrayName = sourceTypeName.charAt(0).toLowerCase() + sourceTypeName.slice(1);
        if (!sourceArrayName.endsWith('s')) {
          sourceArrayName += 's';
        } else if (sourceArrayName.endsWith('ys')) {
          sourceArrayName = sourceArrayName.slice(0, -2) + 'ies';
        }
        tFields.push(`  ${sourceArrayName}: [${sourceTypeName}!]!`);
        relatedFields.set(targetTypeName, tFields);
      }
    }
  }

  for (const node of nodes) {
    const typeName = safeId(node.data.title.split('.').pop() || node.data.title);

    if (node.data.comment) {
      output += `"""\n${escapeString(node.data.comment)}\n"""\n`;
    }

    output += `type ${typeName} {\n`;

    for (const col of node.data.columns || []) {
      if (!col.column_name) continue;

      const fieldName = col.column_name.replace(/[^a-zA-Z0-9_]/g, '_');
      if (col.column_comment) {
        output += `  """\n  ${escapeString(col.column_comment)}\n  """\n`;
      }

      const isPk = col.is_pk;
      const gqlType = isPk ? 'ID' : mapDataType(col.data_type || '');
      const required = col.is_not_null || isPk ? '!' : '';

      output += `  ${fieldName}: ${gqlType}${required}\n`;
    }

    const relations = relatedFields.get(typeName);
    if (relations && relations.length > 0) {
      output += relations.join('\n') + '\n';
    }

    output += "}\n\n";
  }

  return output.trim() + "\n";
}
