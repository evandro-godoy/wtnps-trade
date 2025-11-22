"""
Debug server startup - run endpoint directly
"""
import sys
sys.path.insert(0, r'c:\projects\wtnps-trade')

from fastapi.testclient import TestClient
from newapp.main import app

client = TestClient(app)

print("Testing GET / endpoint...")
try:
    response = client.get("/")
    print(f"✅ Status: {response.status_code}")
    print(f"Content length: {len(response.text)} chars")
    
    # Save to file for inspection
    with open(r"c:\projects\wtnps-trade\debug_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Response saved to debug_response.html")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
