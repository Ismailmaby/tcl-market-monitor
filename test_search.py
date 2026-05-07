import urllib.request, json, os

KEY = os.environ["ANTHROPIC_API_KEY"]

payload = json.dumps({
    "model": "claude-sonnet-4-6",
    "max_tokens": 200,
    "stream": False,
    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    "messages": [{"role": "user", "content": "Search for hotel news Dubai today"}]
}).encode()

req = urllib.request.Request(
    "https://lanyiapi.com/v1/messages",
    data=payload,
    headers={
        "x-api-key": KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "web-search-2025-03-05",
        "content-type": "application/json",
    }
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        print("SUCCESS: " + raw[:400])
except urllib.error.HTTPError as e:
    print("HTTP " + str(e.code) + ": " + e.read().decode()[:200])
except Exception as e:
    print("ERROR: " + str(e)[:100])
