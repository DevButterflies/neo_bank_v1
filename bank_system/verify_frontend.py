import time
import urllib.request

for url in ['http://localhost:8000/health', 'http://localhost:8000/ready', 'http://localhost:8000/']:
    for attempt in range(30):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                raw = response.read().decode('utf-8', 'replace')
                print(f'URL:{url} STATUS:{response.status}')
                print(raw[:500])
                break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit(f'Failed to reach {url}')
