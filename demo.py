#!/usr/bin/env python3
"""
Simple demo of the Web Automation Server functionality.
"""

import requests
import time
import json

def demo():
    base_url = "http://127.0.0.1:8000"
    
    print("🤖 Web Automation Server Demo")
    print("=" * 40)
    
    # Test welcome
    print("1. Testing welcome endpoint...")
    response = requests.get(f"{base_url}/api/v1/welcome")
    print(f"   ✓ {response.json()['application']}")
    
    # Create session with a simple test page
    print("\n2. Creating automation session...")
    session_data = {
        "url": "https://httpbin.org/forms/post"
    }
    
    response = requests.post(f"{base_url}/api/v1/session", json=session_data)
    session_info = response.json()
    session_id = session_info['session_id']
    print(f"   ✓ Session created: {session_id[:8]}...")
    
    # Wait for session to start
    print("\n3. Waiting for browser to load...")
    time.sleep(8)
    
    # Check status
    response = requests.get(f"{base_url}/api/v1/session/{session_id}")
    status = response.json()
    print(f"   ✓ Status: {status['status']}")
    if 'current_url' in status:
        print(f"   ✓ Current URL: {status['current_url']}")
        print(f"   ✓ Page title: {status.get('page_title', 'N/A')}")
    
    # Test JavaScript execution
    print("\n4. Testing JavaScript execution...")
    script_data = {
        "script": "return document.title;"
    }
    response = requests.post(f"{base_url}/api/v1/session/{session_id}/execute", json=script_data)
    result = response.json()
    print(f"   ✓ Page title via JS: {result['result']}")
    
    # Test login functionality (will try to fill form if found)
    print("\n5. Testing login functionality...")
    login_data = {
        "username": "demo-user",
        "password": "demo-password"
    }
    response = requests.post(f"{base_url}/api/v1/session/{session_id}/login", json=login_data)
    login_result = response.json()
    print(f"   ✓ Login attempt: {login_result['login_attempted']}")
    
    # List all sessions
    print("\n6. Listing active sessions...")
    response = requests.get(f"{base_url}/api/v1/sessions")
    sessions = response.json()
    print(f"   ✓ Active sessions: {sessions['count']}")
    
    # Clean up
    print("\n7. Cleaning up session...")
    response = requests.delete(f"{base_url}/api/v1/session/{session_id}")
    print(f"   ✓ Session deleted")
    
    print("\n🎉 Demo completed successfully!")
    print("\nKey features demonstrated:")
    print("  • Browser automation with virtual display")
    print("  • URL navigation and page loading")
    print("  • JavaScript execution")
    print("  • Automatic login form detection")
    print("  • Session management")
    print("  • RESTful API interface")

if __name__ == "__main__":
    try:
        demo()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running:")
        print("   web-automation-server --config web-automation.conf")
    except Exception as e:
        print(f"❌ Demo failed: {e}")