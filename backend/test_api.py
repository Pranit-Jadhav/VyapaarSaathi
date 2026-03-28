import requests
import os
import time

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("Testing Health Check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}, Response: {response.json()}")

def test_get_entries():
    print("\nTesting Get Entries...")
    response = requests.get(f"{BASE_URL}/api/entries")
    print(f"Status: {response.status_code}, Count: {len(response.json().get('entries', []))}")

def test_record_mock():
    print("\nTesting Record Audio (Mock)...")
    # In a real test, we'd send a small wav file. 
    # For now, we'll just test the endpoint existence if possible, 
    # but it requires a file. I'll create a dummy file.
    with open("dummy.wav", "wb") as f:
        f.write(b"dummy audio content")
    
    with open("dummy.wav", "rb") as f:
        files = {"file": ("dummy.wav", f, "audio/wav")}
        response = requests.post(f"{BASE_URL}/api/record", files=files)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
    else:
        print(f"Error: {response.text}")
    
    os.remove("dummy.wav")

def test_insights():
    print("\nTesting Insights...")
    response = requests.get(f"{BASE_URL}/api/insights")
    print(f"Status: {response.status_code}, Response: {response.json()}")

def test_pdf_data():
    print("\nTesting PDF Data...")
    response = requests.get(f"{BASE_URL}/api/pdf-data")
    print(f"Status: {response.status_code}, Response: {response.json()}")

if __name__ == "__main__":
    print("Starting Backend Verification...")
    try:
        test_health()
        test_get_entries()
        test_record_mock()
        test_insights()
        test_pdf_data()
    except Exception as e:
        print(f"Connection failed: {e}. Is the server running?")
