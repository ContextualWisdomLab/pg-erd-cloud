import re
with open('backend/app/spec/relationship_inference.py', 'r') as f:
    content = f.read()
content = re.sub(r'\n    rel_by_oid: dict\[Any, dict\[str, Any\]\] = \{r\.get\("relation_oid"\): r for r in relations\}\n', '\n', content)
with open('backend/app/spec/relationship_inference.py', 'w') as f:
    f.write(content)
