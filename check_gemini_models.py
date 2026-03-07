import sys
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, "server")
from app.core.config import settings

api_key = settings.GEMINI_API_KEY
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

resp = requests.get(url, verify=False)
print(f"HTTP Status: {resp.status_code}")
print(f"Response text (first 500 chars): {resp.text[:500]}")
data = resp.json()

print("=== generateContent 지원 모델 목록 ===")
if "models" in data:
    for m in data["models"]:
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            print(m["name"])
else:
    print("에러:", data)
