1. Add concise JSDoc to `fkColumnsForEdge` and `exportDDL`.
- `fkColumnsForEdge`: document precedence (explicit composite columns → handle lookup → PK/non-PK fallback) and why the cache is passed in.
- `exportDDL`: document that precomputed handle maps are an internal acceleration and must not change emitted DDL.

2. Optimize Work-conservation in cache building. Right now, in `exportDDL`, it iterates through all nodes and precomputes the `nodeHandleCache`. But if there are no edges, or if edges already have explicit source/target columns, building this cache is wasted work.
Instead of an eager cache of everything up front, I should either:
- Build the cache lazily (when `nodeHandleCache.get()` is called, generate the handle maps for that node if it doesn't exist).
- Only build it for the source and target nodes that are involved in the edges loop when `sourceHandleColumn` and `targetHandleColumn` lookups are needed.
Wait, `fkColumnsForEdge` first checks explicit columns:
```typescript
  const data = edge.data as ForeignKeyEdgeData | undefined;
  const sourceColumns = data?.sourceColumns?.filter(Boolean) || [];
  const targetColumns = data?.targetColumns?.filter(Boolean) || [];
  if (sourceColumns.length > 0 && sourceColumns.length === targetColumns.length) {
    return { sourceColumns, targetColumns };
  }
```
If we lazily build the cache inside `fkColumnsForEdge`, we only pay the cost when needed.

Let's refactor the cache to a class or just pass a simple factory/lazy cache function to avoid allocating a Map for every single node.
Or just update `exportDDL`:
```typescript
  const nodeHandleCache = new Map<string, NodeHandleCache>();
  const getHandleCache = (node: Node<TableNodeData>) => {
      let cache = nodeHandleCache.get(node.id);
      if (!cache) {
          const sourceHandles = new Map<string, string>();
          const targetHandles = new Map<string, string>();
          for (const col of node.data.columns || []) {
            sourceHandles.set(sourceColumnHandleId(col.column_name), col.column_name);
            targetHandles.set(targetColumnHandleId(col.column_name), col.column_name);
          }
          cache = { sourceHandles, targetHandles };
          nodeHandleCache.set(node.id, cache);
      }
      return cache;
  }
```
Then pass `getHandleCache` to `fkColumnsForEdge`.

Let's test performance differences (Measurement) in a benchmark.
