with open(".jules/bolt.md", "r") as f:
    content = f.read()

# Remove the extra entry about DBML
import re
content = re.sub(r'## 2026-07-28 - Optimize array map loops in DBML exports\n.*?\n\n', '', content, flags=re.DOTALL)

with open(".jules/bolt.md", "w") as f:
    f.write(content)
