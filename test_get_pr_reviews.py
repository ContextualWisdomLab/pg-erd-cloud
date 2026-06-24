import os
import requests
import sys

token = os.environ.get('GH_TOKEN')
pr_number = os.environ.get('PR_NUMBER')
repo = os.environ.get('GH_REPOSITORY')

if not token or not pr_number or not repo:
    print("Missing environment variables.")
    sys.exit(1)

url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    reviews = response.json()
    for r in reviews:
        print(f"Review by {r.get('user', {}).get('login')}: {r.get('state')}")
        body = r.get("body", "")
        if "Trusted OpenCode" in body or "OpenCode" in body:
            print(f"Body snippet: {body[:500]}")
            print("-" * 40)
else:
    print(f"Failed to fetch reviews: {response.status_code}")
    print(response.text)
