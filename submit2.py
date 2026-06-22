import subprocess
import os

branch = "jules-9151621095465363927-ffb06526"
title = "🎨 Palette: ERD 테이블 및 컬럼 편집 기능 구현"

body = ""
with open("pr_description.md", "r") as f:
    body = f.read()

print("Using branch:", branch)
print("Title:", title)
print("Body:", body)
