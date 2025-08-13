#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to manage web automation sessions.
"""

import logging
import os
from threading import Event
from pyvirtualdisplay import Display

from .Config import config
from .WebNavigator import WebNavigator


class SeleniumHelper:
    """
    Helper class to start a browser and execute scripts in it using WebDriver.
    Simplified version without BiDi logging support.
    """

    def __init__(self, parentLogger, acceptInsecureCerts):
        self._parentLogger = parentLogger
        self._logger = parentLogger.getChild('SeleniumHelper')
        self._acceptInsecureCerts = acceptInsecureCerts
        self.driver = None
        self._logger.debug(f"SeleniumHelper initialized with acceptInsecureCerts={acceptInsecureCerts}")

    def __del__(self):
        self._logger.debug("SeleniumHelper destructor called")
        if self.driver:
            self._logger.debug("Quitting browser driver in destructor")
            try:
                self.driver.quit()
                self._logger.debug("Browser driver quit successfully")
            except Exception as e:
                self._logger.warning(f"Exception during driver quit: {e}")

    def startChrome(self, width, height, env, driverPath, browserPath):
        self._logger.debug(f"Starting Chrome: width={width}, height={height}, env={env}, driverPath={driverPath}, browserPath={browserPath}")
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver

        options = ChromeOptions()
        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument(f'--window-size={width},{height}')
        options.add_argument('--disable-infobars')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        service = ChromeService(env=env)
        if driverPath:
            service.executable_path = driverPath
            self._logger.debug(f"Set Chrome driverPath: {driverPath}")

        if browserPath:
            options.binary_location = browserPath
            self._logger.debug(f"Set Chrome binary_location: {browserPath}")

        self.driver = ChromeDriver(options=options, service=service)
        self.driver.set_window_size(width, height)
        self._logger.debug("Chrome browser started and window size set")

    def startFirefox(self, width, height, env, driverPath, browserPath):
        self._logger.debug(f"Starting Firefox: width={width}, height={height}, env={env}, driverPath={driverPath}, browserPath={browserPath}")
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver

        options = FirefoxOptions()
        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)
        
        options.add_argument('--width=' + str(width))
        options.add_argument('--height=' + str(height))
        options.set_preference('dom.webnotifications.enabled', False)
        options.set_preference('media.navigator.permission.disabled', True)

        service = FirefoxService(env=env)
        if driverPath:
            service.executable_path = driverPath
            self._logger.debug(f"Set Firefox driverPath: {driverPath}")

        if browserPath:
            options.binary_location = browserPath
            self._logger.debug(f"Set Firefox binary_location: {browserPath}")

        self.driver = FirefoxDriver(options=options, service=service)
        self.driver.set_window_size(width, height)
        self._logger.debug("Firefox browser started and window size set")

    def execute(self, script):
        self._logger.debug(f"Executing script: {script[:100]}...")
        result = self.driver.execute_script(script)
        self._logger.debug(f"Script executed, result: {result}")
        return result


class WebAutomationService:
    """
    Class to set up and manage web automation sessions.
    
    This service creates a virtual display and browser instance for automated
    web navigation and login operations.
    """

    def __init__(self, sessionId):
        self._logger = logging.getLogger(f"{__name__}-{sessionId}")
        self.sessionId = sessionId
        self._started = Event()
        self._stopped = Event()
        self._display = None
        self._seleniumHelper = None
        self._webNavigator = None
        self._logger.debug(f"WebAutomationService initialized for sessionId={sessionId}")

    def __del__(self):
        self._logger.debug("WebAutomationService destructor called")
        self._stopHelpers()

    def start(self, url, username=None, password=None):
        self._logger.debug(f"Starting web automation session for url={url}, username={username}")
        try:
            self._logger.debug(f"Step: Get video size from config")
            width = config.getBackendVideoWidth("default") or 1920
            height = config.getBackendVideoHeight("default") or 1080
            self._logger.debug(f"Video size: width={width}, height={height}")

            self._logger.debug(f"Step: Create virtual display")
            self._display = Display(size=(width, height), manage_global_env=False)
            self._display.start()
            self._logger.debug("Virtual display started")

            if self._stopped.is_set():
                self._logger.debug("Session was stopped before display start")
                raise Exception("Display started after session was stopped")

            env = self._display.env()
            self._logger.debug(f"Step: Get browser config")
            browser = config.getBrowserForRecording() or 'firefox'
            driverPath = config.getDriverPathForRecording()
            browserPath = config.getBrowserPathForRecording()
            self._logger.debug(f"Browser: {browser}, driverPath: {driverPath}, browserPath: {browserPath}")

            self._logger.debug(f"Step: Initialize SeleniumHelper")
            acceptInsecureCerts = config.getBackendSkipVerify("default") or False
            self._logger.debug(f"acceptInsecureCerts: {acceptInsecureCerts}")
            self._seleniumHelper = SeleniumHelper(self._logger, acceptInsecureCerts)

            self._logger.debug(f"Step: Start browser")
            if browser == 'chrome':
                self._logger.debug(f"Starting Chrome with width={width}, height={height}, env={env}, driverPath={driverPath}, browserPath={browserPath}")
                self._seleniumHelper.startChrome(width, height, env, driverPath, browserPath)
                self._logger.debug("Chrome started")
            elif browser == 'firefox':
                self._logger.debug(f"Starting Firefox with width={width}, height={height}, env={env}, driverPath={driverPath}, browserPath={browserPath}")
                self._seleniumHelper.startFirefox(width, height, env, driverPath, browserPath)
                self._logger.debug("Firefox started")
            else:
                self._logger.error(f"Invalid browser: {browser}")
                raise Exception(f'Invalid browser: {browser}')

            if self._stopped.is_set():
                self._logger.debug("Session was stopped before browser start")
                raise Exception("Browser started after session was stopped")

            self._logger.debug("Step: Create WebNavigator")
            self._webNavigator = WebNavigator(self._seleniumHelper, self._logger)

            self._logger.debug(f"Step: Navigate to URL: {url}")
            self._webNavigator.navigateToUrl(url)
            self._logger.debug(f"Navigation to {url} complete")

            if username and password:
                self._logger.debug(f"Step: Perform login with username={username}")
                loginSuccess = self._webNavigator.performLogin(username, password)
                if loginSuccess:
                    self._logger.info("Login attempted successfully")
                else:
                    self._logger.warning("Login attempt failed or no login form found")
            else:
                self._logger.debug("No login credentials provided, skipping login step")

            self._started.set()
            self._logger.info(f"Web automation session started successfully for URL: {url}")

        except Exception as e:
            self._logger.error(f"Exception during session start: {e}")
            self._stopHelpers()
            raise

    def stop(self):
        self._logger.debug("Stopping web automation session")
        self._stopped.set()
        self._stopHelpers()
        self._logger.info("Web automation session stopped")

    def getStatus(self):
        self._logger.debug("Getting session status")
        if not self._started.is_set():
            self._logger.debug("Session not started")
            return {"status": "not_started"}
        
        if self._stopped.is_set():
            self._logger.debug("Session stopped")
            return {"status": "stopped"}

        try:
            current_url = self._webNavigator.getCurrentUrl() if self._webNavigator else None
            page_title = self._webNavigator.getPageTitle() if self._webNavigator else None
            self._logger.debug(f"Session running: current_url={current_url}, page_title={page_title}")
            return {
                "status": "running",
                "current_url": current_url,
                "page_title": page_title,
                "session_id": self.sessionId
            }
        except Exception as e:
            self._logger.error(f"Error getting session status: {e}")
            return {"status": "error"}

    def takeScreenshot(self, filename=None):
        self._logger.debug(f"Taking screenshot, filename={filename}")
        if self._webNavigator:
            result = self._webNavigator.takeScreenshot(filename)
            self._logger.debug("Screenshot taken")
            return result
        self._logger.warning("No WebNavigator available for screenshot")
        return None

    def executeScript(self, script):
        self._logger.debug(f"Executing script: {script[:100]}...")
        if self._webNavigator:
            result = self._webNavigator.executeScript(script)
            self._logger.debug(f"Script executed, result: {result}")
            return result
        self._logger.warning("No WebNavigator available for script execution")
        return None

    def navigateToUrl(self, url):
        self._logger.debug(f"Navigating to URL: {url}")
        if self._webNavigator:
            self._webNavigator.navigateToUrl(url)
            self._logger.debug("Navigation complete")
        else:
            self._logger.warning("No WebNavigator available for navigation")

    def performLogin(self, username, password):
        self._logger.debug(f"Performing login with username={username}")
        if self._webNavigator:
            result = self._webNavigator.performLogin(username, password)
            self._logger.debug(f"Login result: {result}")
            return result
        self._logger.warning("No WebNavigator available for login")
        return False

    def _stopHelpers(self):
        self._logger.debug("Stopping helper components")
        if self._seleniumHelper:
            self._logger.debug("Stopping browser")
            try:
                if self._seleniumHelper.driver:
                    self._seleniumHelper.driver.quit()
                    self._logger.debug("Browser stopped successfully")
            except Exception as e:
                self._logger.exception(f"Error when stopping browser: {e}")
            finally:
                self._seleniumHelper = None

        if self._display:
            self._logger.debug("Stopping display")
            try:
                self._display.stop()
                self._logger.debug("Display stopped successfully")
            except Exception as e:
                self._logger.exception(f"Error when stopping display: {e}")
            finally:
                self._display = None