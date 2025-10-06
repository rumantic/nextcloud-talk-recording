#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to provide the command line interface for the web automation server.
"""

import argparse
import logging

from nextcloud.talk import recording
from .Config import config
from .WebAutomationServer import app


def main():
    """
    Runs the web automation server with the arguments given in the command line.
    """
    parser = argparse.ArgumentParser(
        description="Web Automation Server - Navigate to URLs and perform automated login"
    )
    parser.add_argument("-c", "--config", help="path to configuration file", default="server.conf")
    parser.add_argument("-v", "--version", help="show version and quit", action="store_true")
    parser.add_argument("--host", help="host to listen on", default="127.0.0.1")
    parser.add_argument("--port", help="port to listen on", type=int, default=8000)
    args = parser.parse_args()

    if args.version:
        print(f"Web Automation Server v{recording.__version__}")
        print("Based on Nextcloud Talk Recording Server")
        return

    # Load configuration if file exists
    try:
        config.load(args.config)
        logging.basicConfig(level=config.getLogLevel())
        
        # Try to get listen address from config, fall back to command line args
        try:
            listen = config.getListen()
            host, port = listen.split(':')
            host = host or args.host
            port = int(port) if port else args.port
        except:
            host = args.host
            port = args.port
            
    except FileNotFoundError:
        # If config file doesn't exist, use defaults
        print(f"Warning: Configuration file '{args.config}' not found, using defaults")
        logging.basicConfig(level=logging.INFO)
        host = args.host
        port = args.port

    print(f"Starting Web Automation Server on {host}:{port}")
    print("API endpoints:")
    print("  POST /api/v1/session - Create new session")
    print("  GET  /api/v1/session/<id> - Get session status")
    print("  POST /api/v1/session/<id>/navigate - Navigate to URL")
    print("  POST /api/v1/session/<id>/login - Perform login")
    print("  GET  /api/v1/session/<id>/screenshot - Take screenshot")
    print("  POST /api/v1/session/<id>/execute - Execute JavaScript")
    print("  DELETE /api/v1/session/<id> - Stop session")
    print("  GET  /api/v1/sessions - List all sessions")
    
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == '__main__':
    main()