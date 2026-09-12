import type { Node, Edge } from "@xyflow/react";
import type { TableNodeData } from "./convert";


function sanitizeClassName(name: string): string {
  // Python class names should be CamelCase
  // First, replace non-alphanumeric with underscore
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");

  // Remove trailing 's' for plural to singular simple conversion
  if (sanitized.endsWith('s')) {
    sanitized = sanitized.slice(0, -1);
  }

  // Convert to PascalCase (CamelCase with first letter capitalized)
  sanitized = sanitized.split('_').map(word =>
    word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  ).join('');

  if (!/^[a-zA-Z]/.test(sanitized)) {
    sanitized = "Model" + sanitized;
  }
  return sanitized;
}

function sanitizeFieldName(name: string): string {
  // Python field names should be snake_case and valid identifiers
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, "_");
  if (!/^[a-zA-Z_]/.test(sanitized)) {
    sanitized = "_" + sanitized;
  }

  // Prevent using Python reserved keywords
  const keywords = new Set(['False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield']);
  if (keywords.has(sanitized)) {
    sanitized = sanitized + "_";
  }

  return sanitized;
}

function mapToSqlalchemyType(pgType: string): string {
  const t = pgType.toLowerCase();

  if (t.includes("serial")) {
    return "Integer";
  }
  if (t.includes("int8") || t.includes("bigint")) {
    return "BigInteger";
  }
  if (t.includes("int2") || t.includes("smallint")) {
    return "SmallInteger";
  }
  if (t.includes("int")) {
    return "Integer";
  }
  if (t.includes("varchar") || t.includes("char") || t.includes("text")) {
    return "String";
  }
  if (t.includes("uuid")) {
    return "Uuid";
  }
  if (t.includes("bool")) {
    return "Boolean";
  }
  if (t.includes("timestamp")) {
    return "DateTime";
  }
  if (t.includes("time")) {
    return "Time";
  }
  if (t.includes("date")) {
    return "Date";
  }
  if (t.includes("float8") || t.includes("double")) {
    return "Float";
  }
  if (t.includes("float4") || t.includes("real")) {
    return "Float";
  }
  if (t.includes("numeric") || t.includes("decimal")) {
    return "Numeric";
  }
  if (t.includes("json")) {
    return "JSON";
  }
  if (t.includes("bytea")) {
    return "LargeBinary";
  }
  return "String"; // fallback
}

export function exportSqlalchemy(
  nodes: Node<TableNodeData>[],
  edges: Edge[],
): string {
  if (nodes.length === 0) {
    return "# No tables to export\n";
  }

  let output = `from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime, Date, Time, Float, Numeric, BigInteger, SmallInteger, JSON, LargeBinary, Uuid\nfrom sqlalchemy.orm import declarative_base, relationship\n\nBase = declarative_base()\n\n`;

  const nodesById = new Map<string, Node<TableNodeData>>();
  for (const n of nodes) {
    nodesById.set(n.id, n);
  }

  // To build relations, we need to track foreign keys
  const edgesProcessed = new Map<string, { sourceModel: string, targetModel: string, sourceFields: string[], targetFields: string[], relationName: string, sourceTableName: string, targetTableName: string }>();

  const fkFieldsByNode = new Map<string, Set<string>>();

  for (const edge of edges) {
    const sourceNode = nodesById.get(edge.source);
    const targetNode = nodesById.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    let sourceField = "";
    if (edge.sourceHandle?.startsWith("src-")) {
      sourceField = edge.sourceHandle.slice(4);
    }

    let targetField = "id"; // fallback
    if (edge.targetHandle?.startsWith("tgt-")) {
      targetField = edge.targetHandle.slice(4);
    }

    if (sourceField) {
      const relName = sanitizeFieldName(targetNode.data.title);

      const sourceTableName = sourceNode.data.title.includes('.') ? sourceNode.data.title.split('.').pop()! : sourceNode.data.title;
      const targetTableName = targetNode.data.title.includes('.') ? targetNode.data.title.split('.').pop()! : targetNode.data.title;

      edgesProcessed.set(edge.id, {
        sourceModel: sanitizeClassName(sourceNode.data.title),
        targetModel: sanitizeClassName(targetNode.data.title),
        sourceFields: [sourceField],
        targetFields: [targetField],
        relationName: relName,
        sourceTableName: sourceTableName,
        targetTableName: targetTableName
      });

      if (!fkFieldsByNode.has(edge.source)) {
        fkFieldsByNode.set(edge.source, new Set());
      }
      fkFieldsByNode.get(edge.source)!.add(sourceField);
    }
  }

  for (const node of nodes) {
    const className = sanitizeClassName(node.data.title);
    const tableName = node.data.title.includes('.') ? node.data.title.split('.').pop()! : node.data.title;

    output += `class ${className}(Base):\n`;
    output += `    __tablename__ = '${tableName}'\n`;

    if (node.data.title.includes('.')) {
      output += `    __table_args__ = {'schema': '${node.data.title.split('.')[0]}'}\n`;
    }

    let hasId = false;

    // Output columns
    for (const col of node.data.columns) {
      const fieldName = sanitizeFieldName(col.column_name);
      const sqlalchemyType = mapToSqlalchemyType(col.data_type);

      let columnArgs = [];
      columnArgs.push(sqlalchemyType);

      if (col.is_pk) {
        columnArgs.push("primary_key=True");
        hasId = true;
      }

      const isColUnique = col.column_name === 'email';
      if (isColUnique && !col.is_pk) {
        columnArgs.push("unique=True");
      }

      if (col.is_not_null && !col.is_pk) {
         columnArgs.push("nullable=False");
      }

      // Check if this field is a foreign key
      let isFk = false;
      for (const [_, edgeInfo] of edgesProcessed) {
         if (edgeInfo.sourceModel === className && edgeInfo.sourceFields.includes(col.column_name)) {
            // Found a foreign key definition for this column
            const targetTableRef = `${edgeInfo.targetTableName}.${edgeInfo.targetFields[0]}`;
            // If the target has a schema, in SQLAlchemy we typically use "schema.table.column"
            let fkTarget = targetTableRef;
            const targetNode = Array.from(nodes).find(n => sanitizeClassName(n.data.title) === edgeInfo.targetModel);
            if (targetNode && targetNode.data.title.includes('.')) {
                fkTarget = `${targetNode.data.title}.${edgeInfo.targetFields[0]}`;
            }
            columnArgs.push(`ForeignKey('${fkTarget}')`);
            isFk = true;
            break;
         }
      }

      // Add column definition
      output += `    ${fieldName} = Column(${columnArgs.join(', ')})\n`;
    }

    // Add relationship definitions
    // Look for edges where this node is the source (it has the foreign key)
    const relationshipsAdded = new Set<string>();

    for (const [_, edgeInfo] of edgesProcessed) {
      if (edgeInfo.sourceModel === className) {
        let relName = edgeInfo.relationName;
        if (relationshipsAdded.has(relName)) {
            relName = `${relName}_${edgeInfo.sourceFields[0]}`; // disambiguate
        }
        output += `    ${relName} = relationship('${edgeInfo.targetModel}', foreign_keys=[${sanitizeFieldName(edgeInfo.sourceFields[0])}])\n`;
        relationshipsAdded.add(relName);
      }
    }

    // Look for edges where this node is the target (back-references)
    for (const [_, edgeInfo] of edgesProcessed) {
      if (edgeInfo.targetModel === className) {
        let relName = sanitizeFieldName(edgeInfo.sourceTableName) + "s";
        if (relationshipsAdded.has(relName)) {
             relName = `${relName}_${edgeInfo.sourceFields[0]}`;
        }
        // A simple back-relation
        output += `    ${relName} = relationship('${edgeInfo.sourceModel}', foreign_keys='[${edgeInfo.sourceModel}.${sanitizeFieldName(edgeInfo.sourceFields[0])}]')\n`;
        relationshipsAdded.add(relName);
      }
    }

    output += `\n`;
  }

  return output;
}
