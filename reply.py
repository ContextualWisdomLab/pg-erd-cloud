import urllib.request
import urllib.parse
import json

req = urllib.request.Request(
    'http://localhost:8000/api/v1/health',
    headers={'User-Agent': 'Mozilla/5.0'}
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(e)
