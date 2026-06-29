with open('backend/app/spec/index_design.py', 'r') as f:
    content = f.read()

content = content.replace('return "\\n"\n.join(lines)', 'return "\\n".join(lines)')

with open('backend/app/spec/index_design.py', 'w') as f:
    f.write(content)
