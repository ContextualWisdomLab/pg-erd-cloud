import re

with open("frontend/src/erd/export.ts", "r") as f:
    content = f.read()

# Make sure we didn't miss any Array.find in export.ts
print(content.count(".find"))
