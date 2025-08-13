#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to navigate to websites and perform login automation.
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class WebNavigator:
    """
    Class to handle web navigation and login automation using browser automation.

    This class provides functionality to navigate to URLs and perform automated
    login using username and password credentials.
    """

    def __init__(self, seleniumHelper, parentLogger):
        """
        Initialize the web navigator with selenium helper.

        :param seleniumHelper: the SeleniumHelper instance to use for browser automation.
        :param parentLogger: the parent logger to get a child from.
        """
        self.seleniumHelper = seleniumHelper
        self._logger = parentLogger.getChild('WebNavigator')

    def navigateToUrl(self, url):
        """
        Navigate to the specified URL.

        :param url: the URL to navigate to.
        """
        self._logger.info("Navigating to URL: %s", url)
        self.seleniumHelper.driver.get(url)

        # Wait for page to load
        WebDriverWait(self.seleniumHelper.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        self._logger.info("Page loaded successfully")

    def performLogin(self, username, password):
        """
        Attempt to perform login on the current page using common login form patterns.

        :param username: the username to use for login.
        :param password: the password to use for login.
        :return: True if login was attempted, False if no login form was found.
        """
        self._logger.info("Attempting to perform login for user: %s", username)

        try:
            # Common username field selectors
            usernameSelectors = [
                "input[name='username']",
                "input[name='email']",
                "input[name='user']",
                "input[name='login']",
                "input[id='username']",
                "input[id='email']",
                "input[id='user']",
                "input[id='login']",
                "input[type='email']",
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]",
                "input[placeholder*='логин' i]",
                "input[placeholder*='пользовател' i]"
            ]

            # Common password field selectors
            passwordSelectors = [
                "input[name='password']",
                "input[name='pass']",
                "input[id='password']",
                "input[id='pass']",
                "input[type='password']",
                "input[placeholder*='password' i]",
                "input[placeholder*='пароль' i]"
            ]

            # Try to find username field
            usernameField = self._findElement(usernameSelectors, "username")
            if not usernameField:
                return False

            # Try to find password field
            passwordField = self._findElement(passwordSelectors, "password")
            if not passwordField:
                return False

            # Fill in credentials
            self._logger.debug("Filling username field")
            usernameField.clear()
            usernameField.send_keys(username)

            self._logger.debug("Filling password field")
            passwordField.clear()
            passwordField.send_keys(password)

            # Try to submit the form
            if not self._submitForm(passwordField):
                return False

            self._logger.info("Login form submitted successfully")

            # Wait a bit for login to process
            time.sleep(3)

            return True

        except Exception as e:
            self._logger.error("Error during login attempt: %s", e)
            return False

    def _findElement(self, selectors, fieldType):
        """
        Try to find an element using multiple selectors.

        :param selectors: list of CSS selectors to try.
        :param fieldType: type of field for logging purposes.
        :return: the found element or None.
        """
        for selector in selectors:
            try:
                element = WebDriverWait(self.seleniumHelper.driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                self._logger.debug("Found %s field with selector: %s", fieldType, selector)
                return element
            except TimeoutException:
                continue

        self._logger.warning("No %s field found", fieldType)
        return None

    def _submitForm(self, passwordField):
        """
        Try to submit the login form using various methods.

        :param passwordField: the password field element to submit from.
        :return: True if submission was attempted, False otherwise.
        """
        # Try to find and click submit button
        submitSelectors = [
            "input[type='submit']",
            "button[type='submit']",
            "button[name='login']",
            "button[id='login']",
            "button[class*='login' i]",
            "button[class*='signin' i]",
            "button[class*='submit' i]",
            "input[value*='login' i]",
            "input[value*='signin' i]",
            "input[value*='войти' i]",
            "form input[type='submit']",
            "form button[type='submit']"
        ]

        # Try text-based button search
        submitButton = self._findSubmitButtonByText()
        if submitButton:
            return True

        # Try CSS selectors
        for selector in submitSelectors:
            try:
                submitButton = WebDriverWait(self.seleniumHelper.driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                self._logger.debug("Found submit button with selector: %s", selector)
                submitButton.click()
                return True
            except TimeoutException:
                continue

        # Try submitting the form containing the password field
        try:
            self._logger.debug("Trying to submit form via Enter key")
            from selenium.webdriver.common.keys import Keys
            passwordField.send_keys(Keys.RETURN)
            return True
        except Exception as e:
            self._logger.warning("Failed to submit form: %s", e)
            return False

    def _findSubmitButtonByText(self):
        """
        Find submit button by text content using JavaScript.

        :return: True if button was found and clicked, False otherwise.
        """
        try:
            submitButton = self.seleniumHelper.execute("""
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].textContent.toLowerCase();
                    if (text.includes('login') || text.includes('sign in') || text.includes('войти')) {
                        return buttons[i];
                    }
                }
                return null;
            """)
            if submitButton:
                # Click using JavaScript
                self.seleniumHelper.execute("arguments[0].click();", submitButton)
                return True
        except Exception:
            pass
        return False

    def getCurrentUrl(self):
        """
        Get the current URL of the browser.

        :return: the current URL as a string.
        """
        return self.seleniumHelper.driver.current_url

    def getPageTitle(self):
        """
        Get the title of the current page.

        :return: the page title as a string.
        """
        return self.seleniumHelper.driver.title

    def takeScreenshot(self, filename=None):
        """
        Take a screenshot of the current page.

        :param filename: optional filename to save the screenshot to.
        :return: the screenshot data as PNG bytes or filename if saved.
        """
        if filename:
            return self.seleniumHelper.driver.save_screenshot(filename)

        return self.seleniumHelper.driver.get_screenshot_as_png()

    def waitForElement(self, selector, timeout=10):
        """
        Wait for an element to be present on the page.

        :param selector: CSS selector for the element to wait for.
        :param timeout: timeout in seconds to wait for the element.
        :return: True if element was found, False otherwise.
        """
        try:
            WebDriverWait(self.seleniumHelper.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False

    def executeScript(self, script):
        """
        Execute JavaScript on the current page.

        :param script: JavaScript code to execute.
        :return: the result of the script execution.
        """
        return self.seleniumHelper.execute(script)