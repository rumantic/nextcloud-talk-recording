#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Simple test script for the Web Automation Server.
"""

import requests
import json
import time
import sys


def test_web_automation_server():
    """
    Test the web automation server functionality.
    """
    base_url = "http://127.0.0.1:8000"
    
    print("Testing Web Automation Server API...")
    
    # Test welcome endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/welcome")
        if response.status_code == 200:
            welcome_data = response.json()
            print(f"✓ Welcome endpoint works: {welcome_data['application']}")
        else:
            print(f"✗ Welcome endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Make sure the server is running:")
        print("  web-automation-server --config web-automation.conf")
        return False
    
    # Test session creation with a simple URL
    test_url = "https://httpbin.org/forms/post"  # Simple test form
    session_data = {
        "url": test_url
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/session", json=session_data)
        if response.status_code == 200:
            session_info = response.json()
            session_id = session_info['session_id']
            print(f"✓ Session created: {session_id}")
        else:
            print(f"✗ Session creation failed: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"✗ Session creation error: {e}")
        return False
    
    # Wait for session to start
    print("Waiting for session to start...")
    time.sleep(5)
    
    # Check session status
    try:
        response = requests.get(f"{base_url}/api/v1/session/{session_id}")
        if response.status_code == 200:
            status_data = response.json()
            print(f"✓ Session status: {status_data['status']}")
            if 'current_url' in status_data:
                print(f"  Current URL: {status_data['current_url']}")
        else:
            print(f"✗ Session status check failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Session status error: {e}")
    
    # Test login functionality (even though this form might not work, it tests the API)
    login_data = {
        "username": "testuser",
        "password": "testpass"
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/session/{session_id}/login", json=login_data)
        if response.status_code == 200:
            login_result = response.json()
            print(f"✓ Login API works: attempted={login_result['login_attempted']}")
        else:
            print(f"✗ Login API failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Login API error: {e}")
    
    # Test script execution
    script_data = {
        "script": "return document.title;"
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/session/{session_id}/execute", json=script_data)
        if response.status_code == 200:
            script_result = response.json()
            print(f"✓ Script execution works: result={script_result['result']}")
        else:
            print(f"✗ Script execution failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Script execution error: {e}")
    
    # Test session listing
    try:
        response = requests.get(f"{base_url}/api/v1/sessions")
        if response.status_code == 200:
            sessions_data = response.json()
            print(f"✓ Session listing works: {sessions_data['count']} sessions")
        else:
            print(f"✗ Session listing failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Session listing error: {e}")
    
    # Clean up - delete session
    try:
        response = requests.delete(f"{base_url}/api/v1/session/{session_id}")
        if response.status_code == 200:
            print(f"✓ Session deleted successfully")
        else:
            print(f"✗ Session deletion failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Session deletion error: {e}")
    
    print("\nTest completed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python test_web_automation.py")
        print("Make sure the web automation server is running first:")
        print("  web-automation-server --config web-automation.conf")
        sys.exit(0)
    
    test_web_automation_server()