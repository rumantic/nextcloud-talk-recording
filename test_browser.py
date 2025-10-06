#!/usr/bin/env python3
"""
Simple test to verify browser automation components work.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import logging
from nextcloud.talk.recording.WebAutomationService import WebAutomationService

def test_browser_automation():
    print("Testing browser automation components...")
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        # Create a service
        service = WebAutomationService("test-session")
        print("✓ Service created")
        
        # Try to start it with a simple URL
        print("Starting browser session...")
        service.start("https://httpbin.org/")
        print("✓ Session started")
        
        # Check status
        status = service.getStatus()
        print(f"✓ Status: {status}")
        
        # Stop the service
        service.stop()
        print("✓ Service stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_browser_automation()
    sys.exit(0 if success else 1)