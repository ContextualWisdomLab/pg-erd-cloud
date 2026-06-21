import re

with open("frontend/src/App.tsx", "r") as f:
    content = f.read()

replaced = re.sub(
    r"<<<<<<< HEAD\n  const nodesById = useMemo\(\(\) => {\n    return new Map\(nodes\.map\(n => \[n\.id, n\]\)\);\n  }, \[nodes\]\);\n\n  const businessGroupsById = useMemo\(\(\) => {\n    return new Map\(businessGroups\.map\(\(g\) => \[g\.id, g\]\)\);\n  }, \[businessGroups\]\);\n\n=======\n  // ⚡ Bolt: Removed nodesById Map creation inside useMemo which iterates over all nodes and allocates memory.\n  // Using nodes\.find\(\) for single lookups is O\(N\) but avoids Map construction overhead, providing ~10x speedup and reducing GC pressure.\n>>>>>>> origin/main",
    "  const businessGroupsById = useMemo(() => {\n    return new Map(businessGroups.map((g) => [g.id, g]));\n  }, [businessGroups]);\n\n  // ⚡ Bolt: Removed nodesById Map creation inside useMemo which iterates over all nodes and allocates memory.\n  // Using nodes.find() for single lookups is O(N) but avoids Map construction overhead, providing ~10x speedup and reducing GC pressure.",
    content
)

with open("frontend/src/App.tsx", "w") as f:
    f.write(replaced)
