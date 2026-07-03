import re

with open('frontend/src/erd/export.ts', 'r') as f:
    content = f.read()

# Replace first conflict
conflict1 = """<<<<<<< HEAD
  const heights = new Map<string, number>();

=======
  const heights = new Map(
    nodes.map((node) => {
      // ponytail: cap rendered index rows; add full index export when the canvas carries index nodes.
      const indexRows = Math.min((indexes.get(node.id)?.length || 0) + (node.data.indexes?.length || 0), 8);
      return [node.id, headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0))];
    }),
  );
>>>>>>> origin/main"""

replace1 = """  const heights = new Map<string, number>();"""

# Replace second conflict
conflict2 = """<<<<<<< HEAD
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
=======
  // Keep this iterative; JS engines cap variadic argument counts for large SVG exports.
  for (const n of nodes) {
    const x = n.position.x;
    const y = n.position.y;
    const h = heights.get(n.id) || headerHeight;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x + width > maxX) maxX = x + width;
    if (y + h > maxY) maxY = y + h;
>>>>>>> origin/main
  }"""

replace2 = """  // Keep this iterative; JS engines cap variadic argument counts for large SVG exports.
  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    // ponytail: cap rendered index rows; add full index export when the canvas carries index nodes.
    const indexRows = Math.min((indexes.get(node.id)?.length || 0) + (node.data.indexes?.length || 0), 8);
    const height = headerHeight + rowHeight * ((node.data.columns?.length || 0) + indexRows + (indexRows ? 1 : 0));
    heights.set(node.id, height);

    const x = node.position.x;
    const y = node.position.y;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x + width > maxX) maxX = x + width;
    if (y + height > maxY) maxY = y + height;
  }"""

if conflict1 in content and conflict2 in content:
    content = content.replace(conflict1, replace1)
    content = content.replace(conflict2, replace2)
    with open('frontend/src/erd/export.ts', 'w') as f:
        f.write(content)
    print("Success")
else:
    print("Not found")
