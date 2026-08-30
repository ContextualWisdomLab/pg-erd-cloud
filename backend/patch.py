import re

with open("app/auth.py", "r") as f:
    content = f.read()

content = content.replace("from jose import jwt", "import jwt")

with open("app/auth.py", "w") as f:
    f.write(content)
