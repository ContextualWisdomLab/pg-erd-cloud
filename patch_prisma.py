import re

with open("frontend/src/erd/prisma.ts", "r") as f:
    content = f.read()

print(content.count(".find"))
