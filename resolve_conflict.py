import re

with open('backend/tests/test_ddl_export.py', 'r') as f:
    content = f.read()

# Replace merge conflict markers
# Look for <<<<<<< HEAD ... ======= ... >>>>>>>
content = re.sub(r'<<<<<<< HEAD.*?=======\n(.*?)\n>>>>>>>.*?\n', r'\1\n', content, flags=re.DOTALL)

with open('backend/tests/test_ddl_export.py', 'w') as f:
    f.write(content)
