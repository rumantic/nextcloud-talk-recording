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

    def __del__(self):
        if self.driver:
            # The session must be explicitly quit to remove the temporary files
            # created in "/tmp".
            try:
                self.driver.quit()
            except:
                pass

    def startChrome(self, width, height, env, driverPath, browserPath):
        """
        Starts a Chrome instance.

        :param width: the width of the browser window.
        :param height: the height of the browser window.
        :param env: the environment variables, including the display to start
                    the browser in.
        :param driverPath: the path to override the default chromedriver.
        :param browserPath: the path to override the default Google Chrome or
                            Chromium executable.
        """
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver

        options = ChromeOptions()
        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)
        
        # Basic Chrome options for automation
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

        if browserPath:
            options.binary_location = browserPath

        self.driver = ChromeDriver(options=options, service=service)
        self.driver.set_window_size(width, height)

    def startFirefox(self, width, height, env, driverPath, browserPath):
        """
        Starts a Firefox instance.

        :param width: the width of the browser window.
        :param height: the height of the browser window.
        :param env: the environment variables, including the display to start
                    the browser in.
        :param driverPath: the path to override the default geckodriver.
        :param browserPath: the path to override the default Firefox executable.
        """
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver

        options = FirefoxOptions()
        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)
        
        # Basic Firefox options for automation
        options.add_argument('--width=' + str(width))
        options.add_argument('--height=' + str(height))
        options.set_preference('dom.webnotifications.enabled', False)
        options.set_preference('media.navigator.permission.disabled', True)

        service = FirefoxService(env=env)
        if driverPath:
            service.executable_path = driverPath

        if browserPath:
            options.binary_location = browserPath

        self.driver = FirefoxDriver(options=options, service=service)
        self.driver.set_window_size(width, height)

    def execute(self, script):
        """
        Executes the given script synchronously.

        :param script: JavaScript code to execute.
        :return: the value returned by the script, or None
        """
        return self.driver.execute_script(script)


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

    def __del__(self):
        self._stopHelpers()

    def start(self, url, username=None, password=None):
        """
        Starts the web automation session.

        :param url: the URL to navigate to.
        :param username: optional username for login.
        :param password: optional password for login.
        :raise Exception: if the session could not be started.
        """
        try:
            width = config.getBackendVideoWidth("default") or 1920
            height = config.getBackendVideoHeight("default") or 1080

            # Create virtual display
            self._display = Display(size=(width, height), manage_global_env=False)
            self._display.start()

            if self._stopped.is_set():
                raise Exception("Display started after session was stopped")

            env = self._display.env()
            browser = config.getBrowserForRecording() or 'firefox'
            driverPath = config.getDriverPathForRecording()
            browserPath = config.getBrowserPathForRecording()

            # Initialize Selenium helper
            acceptInsecureCerts = config.getBackendSkipVerify("default") or False
            self._seleniumHelper = SeleniumHelper(self._logger, acceptInsecureCerts)

            # Start browser
            if browser == 'chrome':
                self._seleniumHelper.startChrome(width, height, env, driverPath, browserPath)
            elif browser == 'firefox':
                self._seleniumHelper.startFirefox(width, height, env, driverPath, browserPath)
            else:
                raise Exception(f'Invalid browser: {browser}')

            if self._stopped.is_set():
                raise Exception("Browser started after session was stopped")

            # Create web navigator
            self._webNavigator = WebNavigator(self._seleniumHelper, self._logger)

            # Navigate to URL
            self._webNavigator.navigateToUrl(url)

            # Perform login if credentials provided
            if username and password:
                loginSuccess = self._webNavigator.performLogin(username, password)
                if loginSuccess:
                    self._logger.info("Login attempted successfully")
                else:
                    self._logger.warning("Login attempt failed or no login form found")

            self._started.set()
            self._logger.info(f"Web automation session started successfully for URL: {url}")

        except Exception:
            self._stopHelpers()
            raise

    def stop(self):
        """
        Stops the web automation session.
        """
        self._stopped.set()
        self._stopHelpers()
        self._logger.info("Web automation session stopped")

    def getStatus(self):
        """
        Get the current status of the session.

        :return: dictionary with session status information.
        """
        if not self._started.is_set():
            return {"status": "not_started"}
        
        if self._stopped.is_set():
            return {"status": "stopped"}

        try:
            current_url = self._webNavigator.getCurrentUrl() if self._webNavigator else None
            page_title = self._webNavigator.getPageTitle() if self._webNavigator else None
            
            return {
                "status": "running",
                "current_url": current_url,
                "page_title": page_title,
                "session_id": self.sessionId
            }
        except:
            return {"status": "error"}

    def takeScreenshot(self, filename=None):
        """
        Take a screenshot of the current page.

        :param filename: optional filename to save the screenshot to.
        :return: screenshot data or filename.
        """
        if self._webNavigator:
            return self._webNavigator.takeScreenshot(filename)
        return None

    def executeScript(self, script):
        """
        Execute JavaScript on the current page.

        :param script: JavaScript code to execute.
        :return: the result of the script execution.
        """
        if self._webNavigator:
            return self._webNavigator.executeScript(script)
        return None

    def navigateToUrl(self, url):
        """
        Navigate to a new URL.

        :param url: the URL to navigate to.
        """
        if self._webNavigator:
            self._webNavigator.navigateToUrl(url)

    def performLogin(self, username, password):
        """
        Perform login on the current page.

        :param username: the username to use for login.
        :param password: the password to use for login.
        :return: True if login was attempted, False otherwise.
        """
        if self._webNavigator:
            return self._webNavigator.performLogin(username, password)
        return False

    def _stopHelpers(self):
        """
        Stop all helper components.
        """
        if self._seleniumHelper:
            self._logger.debug("Stopping browser")
            try:
                if self._seleniumHelper.driver:
                    self._seleniumHelper.driver.quit()
            except:
                self._logger.exception("Error when stopping browser")
            finally:
                self._seleniumHelper = None

        if self._display:
            self._logger.debug("Stopping display")
            try:
                self._display.stop()
            except:
                self._logger.exception("Error when stopping display")
            finally:
                self._display = None