#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to handle web automation HTTP requests.
"""

import json
import logging
import uuid
from threading import Lock, Thread

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound

from nextcloud.talk import recording
from .Config import config
from .WebAutomationService import WebAutomationService

app = Flask(__name__)

# Dictionary to store active sessions
sessions = {}
sessionsLock = Lock()


@app.route("/api/v1/welcome", methods=["GET"])
def welcome():
    """
    Handles welcome requests.
    """
    return jsonify(
        version=recording.__version__,
        application="Web Automation Server",
        description="Simplified web automation server based on Nextcloud Talk Recording"
    )


@app.route("/api/v1/session", methods=["POST"])
def createSession():
    """
    Creates a new web automation session.
    
    Expected JSON payload:
    {
        "url": "https://example.com",
        "username": "optional_username",
        "password": "optional_password"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            raise BadRequest("JSON payload required")
        
        if 'url' not in data:
            raise BadRequest("URL is required")
        
        url = data['url']
        username = data.get('username')
        password = data.get('password')
        
        # Generate unique session ID
        sessionId = str(uuid.uuid4())
        
        # Create and start session
        service = WebAutomationService(sessionId)
        
        with sessionsLock:
            sessions[sessionId] = service
        
        # Start session in background thread
        def startSession():
            try:
                service.start(url, username, password)
            except Exception as e:
                app.logger.error(f"Failed to start session {sessionId}: {e}")
                with sessionsLock:
                    if sessionId in sessions:
                        sessions.pop(sessionId)
        
        thread = Thread(target=startSession, daemon=True)
        thread.start()
        
        return jsonify({
            "session_id": sessionId,
            "status": "starting",
            "url": url
        })
        
    except Exception as e:
        app.logger.error(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/session/<sessionId>", methods=["GET"])
def getSessionStatus(sessionId):
    """
    Get the status of a specific session.
    """
    with sessionsLock:
        if sessionId not in sessions:
            raise NotFound("Session not found")
        
        service = sessions[sessionId]
    
    status = service.getStatus()
    return jsonify(status)


@app.route("/api/v1/session/<sessionId>/navigate", methods=["POST"])
def navigateSession(sessionId):
    """
    Navigate to a new URL in an existing session.
    
    Expected JSON payload:
    {
        "url": "https://newexample.com"
    }
    """
    try:
        with sessionsLock:
            if sessionId not in sessions:
                raise NotFound("Session not found")
            
            service = sessions[sessionId]
        
        data = request.get_json()
        if not data or 'url' not in data:
            raise BadRequest("URL is required")
        
        url = data['url']
        service.navigateToUrl(url)
        
        return jsonify({
            "session_id": sessionId,
            "status": "navigated",
            "url": url
        })
        
    except Exception as e:
        app.logger.error(f"Error navigating session {sessionId}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/session/<sessionId>/login", methods=["POST"])
def loginSession(sessionId):
    """
    Perform login on the current page of an existing session.
    
    Expected JSON payload:
    {
        "username": "user@example.com",
        "password": "password123"
    }
    """
    try:
        with sessionsLock:
            if sessionId not in sessions:
                raise NotFound("Session not found")
            
            service = sessions[sessionId]
        
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            raise BadRequest("Username and password are required")
        
        username = data['username']
        password = data['password']
        
        success = service.performLogin(username, password)
        
        return jsonify({
            "session_id": sessionId,
            "login_attempted": success,
            "status": "completed"
        })
        
    except Exception as e:
        app.logger.error(f"Error during login for session {sessionId}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/session/<sessionId>/screenshot", methods=["GET"])
def takeScreenshot(sessionId):
    """
    Take a screenshot of the current page.
    """
    try:
        with sessionsLock:
            if sessionId not in sessions:
                raise NotFound("Session not found")
            
            service = sessions[sessionId]
        
        # Take screenshot and return as base64
        import base64
        screenshot_data = service.takeScreenshot()
        
        if screenshot_data:
            screenshot_b64 = base64.b64encode(screenshot_data).decode('utf-8')
            return jsonify({
                "session_id": sessionId,
                "screenshot": screenshot_b64,
                "format": "png"
            })
        else:
            return jsonify({"error": "Could not take screenshot"}), 500
        
    except Exception as e:
        app.logger.error(f"Error taking screenshot for session {sessionId}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/session/<sessionId>/execute", methods=["POST"])
def executeScript(sessionId):
    """
    Execute JavaScript on the current page.
    
    Expected JSON payload:
    {
        "script": "return document.title;"
    }
    """
    try:
        with sessionsLock:
            if sessionId not in sessions:
                raise NotFound("Session not found")
            
            service = sessions[sessionId]
        
        data = request.get_json()
        if not data or 'script' not in data:
            raise BadRequest("Script is required")
        
        script = data['script']
        result = service.executeScript(script)
        
        return jsonify({
            "session_id": sessionId,
            "result": result
        })
        
    except Exception as e:
        app.logger.error(f"Error executing script for session {sessionId}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/session/<sessionId>", methods=["DELETE"])
def deleteSession(sessionId):
    """
    Stop and delete a session.
    """
    try:
        with sessionsLock:
            if sessionId not in sessions:
                raise NotFound("Session not found")
            
            service = sessions.pop(sessionId)
        
        # Stop the service
        service.stop()
        
        return jsonify({
            "session_id": sessionId,
            "status": "stopped"
        })
        
    except Exception as e:
        app.logger.error(f"Error stopping session {sessionId}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/sessions", methods=["GET"])
def listSessions():
    """
    List all active sessions.
    """
    with sessionsLock:
        sessionList = []
        for sessionId, service in sessions.items():
            status = service.getStatus()
            sessionList.append({
                "session_id": sessionId,
                "status": status
            })
    
    return jsonify({
        "sessions": sessionList,
        "count": len(sessionList)
    })


# Cleanup function to stop all sessions on exit
import atexit

def _stopAllSessionsOnExit():
    with sessionsLock:
        sessionIds = list(sessions.keys())
        for sessionId in sessionIds:
            service = sessions.pop(sessionId)
            try:
                service.stop()
            except:
                pass

atexit.register(_stopAllSessionsOnExit)