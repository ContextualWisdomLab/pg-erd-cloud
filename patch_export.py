import re

with open("frontend/src/erd/export.ts", "r") as f:
    content = f.read()

# Replace .find with for loops in fkColumnsForEdge
new_fkColumnsForEdge = """function fkColumnsForEdge(
  edge: Edge,
  sourceNode: Node<TableNodeData>,
  targetNode: Node<TableNodeData>,
): { sourceColumns: string[]; targetColumns: string[] } | null {
  const data = edge.data as ForeignKeyEdgeData | undefined;
  const sourceColumns = data?.sourceColumns?.filter(Boolean) || [];
  const targetColumns = data?.targetColumns?.filter(Boolean) || [];
  if (sourceColumns.length > 0 && sourceColumns.length === targetColumns.length) {
    return { sourceColumns, targetColumns };
  }

  let sourceHandleColumn: string | undefined;
  for (const column of sourceNode.data.columns || []) {
    if (sourceColumnHandleId(column.column_name) === edge.sourceHandle) {
      sourceHandleColumn = column.column_name;
      break;
    }
  }

  let targetHandleColumn: string | undefined;
  for (const column of targetNode.data.columns || []) {
    if (targetColumnHandleId(column.column_name) === edge.targetHandle) {
      targetHandleColumn = column.column_name;
      break;
    }
  }

  if (sourceHandleColumn && targetHandleColumn) {
    return { sourceColumns: [sourceHandleColumn], targetColumns: [targetHandleColumn] };
  }

  const fallbackSource = (sourceNode.data.columns || [])
    .filter((column) => !column.is_pk)
    .map((column) => column.column_name);
  const fallbackTarget = (targetNode.data.columns || [])
    .filter((column) => column.is_pk)
    .map((column) => column.column_name);
  if (fallbackSource.length > 0 && fallbackSource.length === fallbackTarget.length) {
    return { sourceColumns: fallbackSource, targetColumns: fallbackTarget };
  }

  return null;
}"""

# Using regex to replace the function definition
content = re.sub(
    r"function fkColumnsForEdge\(.*?return null;\n}",
    new_fkColumnsForEdge,
    content,
    flags=re.DOTALL
)

with open("frontend/src/erd/export.ts", "w") as f:
    f.write(content)

with open("frontend/src/erd/prisma.ts", "r") as f:
    content = f.read()

# Replace .find with for loop in exportPrisma
new_prisma_logic = """    if (sourceField) {
      let isUnique = false;
      for (const c of sourceNode.data.columns) {
        if (c.column_name === sourceField) {
          isUnique = c.is_pk || false;
          break;
        }
      }

      const relList = incomingRelationsByNode.get(edge.target) || [];"""

content = content.replace(
    """    if (sourceField) {
      const isUnique = sourceNode.data.columns.find(c => c.column_name === sourceField)?.is_pk || false;

      const relList = incomingRelationsByNode.get(edge.target) || [];""",
    new_prisma_logic
)

with open("frontend/src/erd/prisma.ts", "w") as f:
    f.write(content)
