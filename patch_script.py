import re

with open('frontend/src/erd/export.ts', 'r') as f:
    content = f.read()

search = """  const heights = new Map(
    nodes.map((node) => {
      // ponytail: cap rendered index rows; add full index export when the canvas carries index nodes.
      const indexRows = Math.min((indexes.get(node.id)?.length || 0) + (node.data.indexes?.length || 0), 8);
      return [node.id, headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0))];
    }),
  );
  const minX = Math.min(...nodes.map((n) => n.position.x), 0);
  const minY = Math.min(...nodes.map((n) => n.position.y), 0);
  const maxX = Math.max(...nodes.map((n) => n.position.x + width), width);
  const maxY = Math.max(...nodes.map((n) => n.position.y + (heights.get(n.id) || headerHeight)), headerHeight);"""

replace = """  const heights = new Map<string, number>();

  let minX = 0;
  let minY = 0;
  let maxX = width;
  let maxY = headerHeight;

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    // ponytail: cap rendered index rows; add full index export when the canvas carries index nodes.
    const indexRows = Math.min((indexes.get(node.id)?.length || 0) + (node.data.indexes?.length || 0), 8);
    const height = headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0));
    heights.set(node.id, height);
    if (node.position.x < minX) minX = node.position.x;
    if (node.position.y < minY) minY = node.position.y;
    if (node.position.x + width > maxX) maxX = node.position.x + width;
    if (node.position.y + height > maxY) maxY = node.position.y + height;
  }"""

if search in content:
    content = content.replace(search, replace)
    with open('frontend/src/erd/export.ts', 'w') as f:
        f.write(content)
    print("Success")
else:
    print("Not found")
