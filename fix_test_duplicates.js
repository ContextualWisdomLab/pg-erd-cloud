const fs = require('fs')
let content = fs.readFileSync('frontend/src/erd/convert.test.ts', 'utf8')

// We added expect(Object.keys...) to other tests incorrectly during previous manipulation because of global replace.
// Let's remove them from other tests.
content = content.replace(/    expect\(graph\.edges\)\.toHaveLength\(1\)\n    expect\(Object\.keys\(graph\.edges\)\)\.toHaveLength\(1\)\n    expect\(graph\.edges\.every\(Boolean\)\)\.toBe\(true\)/g, '    expect(graph.edges).toHaveLength(1)')

// Add it back only to the specific test where it belongs:
content = content.replace(/    expect\(graph\.edges\)\.toHaveLength\(1\)\n    for \(const edge of graph\.edges\) \{/g, `    expect(graph.edges).toHaveLength(1)
    expect(Object.keys(graph.edges)).toHaveLength(1)
    expect(graph.edges.every(Boolean)).toBe(true)
    for (const edge of graph.edges) {`)

// Remove duplicate assertions inside the loop
content = content.replace(/      expect\(edge\.animated\)\.toBe\(false\)\n      expect\(edge\.type\)\.toBe\('smoothstep'\)\n      expect\(edge\.data\)\.toBeDefined\(\)\n      expect\(edge\.label\)\.toBeDefined\(\)\n      expect\(edge\.animated\)\.toBe\(false\)\n      expect\(edge\.type\)\.toBe\('smoothstep'\)\n      expect\(edge\.data\)\.toBeDefined\(\)\n      expect\(edge\.label\)\.toBeDefined\(\)/g, `      expect(edge.animated).toBe(false)
      expect(edge.type).toBe('smoothstep')
      expect(edge.data).toBeDefined()
      expect(edge.label).toBeDefined()`)


fs.writeFileSync('frontend/src/erd/convert.test.ts', content, 'utf8')
