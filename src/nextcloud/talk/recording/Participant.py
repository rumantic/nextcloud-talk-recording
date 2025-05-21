#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to join a call with a browser.
"""

import hashlib
import hmac
import json
import re
import threading
from datetime import datetime
from secrets import token_urlsafe
from shutil import disk_usage
from time import sleep
import subprocess

import websocket
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver

from .Config import config

class BiDiLogsHelper:
    """
    Helper class to get browser logs using the BiDi protocol.

    A new thread is started by each object to receive the logs, so they can be
    printed in real time even if the main thread is waiting for some script to
    finish.
    """

    def __init__(self, driver, parentLogger):
        if not 'webSocketUrl' in driver.capabilities:
            raise Exception('webSocketUrl not found in capabilities')

        self._logger = parentLogger.getChild('BiDiLogsHelper')

        self.realtimeLogsEnabled = False
        self.pendingLogs = []
        self.logsLock = threading.Lock()

        # Web socket connection is rejected by Firefox with "Bad request" if
        # "Origin" header is present; logs show:
        # "The handshake request has incorrect Origin header".
        self.websocket = websocket.create_connection(driver.capabilities['webSocketUrl'], suppress_origin=True)

        self.websocket.send(json.dumps({
            'id': 1,
            'method': 'session.subscribe',
            'params': {
                'events': ['log.entryAdded'],
            },
        }))

        self.initialLogsLock = threading.Lock()
        # pylint: disable=consider-using-with
        self.initialLogsLock.acquire()

        self.loggingThread = threading.Thread(target=self._processLogEvents, daemon=True)
        self.loggingThread.start()

        # Do not return until the existing logs were fetched, except if it is
        # taking too long.
        # pylint: disable=consider-using-with
        self.initialLogsLock.acquire(timeout=10)

    def __del__(self):
        if self.websocket:
            self.websocket.close()

        if self.loggingThread:
            self.loggingThread.join()

    def _messageFromEvent(self, event):
        if not 'params' in event:
            return '???'

        method = ''
        if 'method' in event['params']:
            method = event['params']['method']
        elif 'level' in event['params']:
            method = event['params']['level'] if event['params']['level'] != 'warning' else 'warn'

        text = ''
        if 'text' in event['params']:
            text = event['params']['text']

        time = '??:??:??'
        if 'timestamp' in event['params']:
            timestamp = event['params']['timestamp']

            # JavaScript timestamps are millisecond based, Python timestamps
            # are second based.
            time = datetime.fromtimestamp(timestamp / 1000).strftime('%H:%M:%S')

        methodShort = '?'
        if method == 'error':
            methodShort = 'E'
        elif method == 'warn':
            methodShort = 'W'
        elif method == 'log':
            methodShort = 'L'
        elif method == 'info':
            methodShort = 'I'
        elif method == 'debug':
            methodShort = 'D'

        return time + ' ' + methodShort + ' ' + text

    def _processLogEvents(self):
        while True:
            try:
                event = json.loads(self.websocket.recv())
            except:
                self._logger.debug('BiDi WebSocket closed')
                return

            if 'id' in event and event['id'] == 1:
                self.initialLogsLock.release()
                continue

            if not 'method' in event or event['method'] != 'log.entryAdded':
                continue

            message = self._messageFromEvent(event)

            with self.logsLock:
                if self.realtimeLogsEnabled:
                    self._logger.debug(message)
                else:
                    self.pendingLogs.append(message)

    def clearLogs(self):
        """
        Clears, without printing, the logs received while realtime logs were not
        enabled.
        """

        with self.logsLock:
            self.pendingLogs = []

    def printLogs(self):
        """
        Prints the logs received while realtime logs were not enabled.

        The logs are cleared after printing them.
        """

        with self.logsLock:
            for log in self.pendingLogs:
                self._logger.debug(log)

            self.pendingLogs = []

    def setRealtimeLogsEnabled(self, realtimeLogsEnabled):
        """
        Enable or disable realtime logs.

        If logs are received while realtime logs are not enabled they can be
        printed using "printLogs()".
        """

        with self.logsLock:
            self.realtimeLogsEnabled = realtimeLogsEnabled


class SeleniumHelper:
    """
    Helper class to start a browser and execute scripts in it using WebDriver.

    The browser is expected to be available in the local system.
    """

    def __init__(self, parentLogger, acceptInsecureCerts):
        self._parentLogger = parentLogger
        self._logger = parentLogger.getChild('SeleniumHelper')

        self._acceptInsecureCerts = acceptInsecureCerts

        self.driver = None
        self.bidiLogsHelper = None

    def __del__(self):
        if self.driver:
            # The session must be explicitly quit to remove the temporary files
            # created in "/tmp".
            self.driver.quit()

    def startChrome(self, width, height, env, driverPath, browserPath):
        """
        Starts a Chrome instance.

        Will use Chromium if Google Chrome is not installed.

        :param width: the width of the browser window.
        :param height: the height of the browser window.
        :param env: the environment variables, including the display to start
                    the browser in.
        :param driverPath: the path to override the default chromedriver.
        :param browserPath: the path to override the default Google Chrome or
                            Chromium executable.
        """

        options = ChromeOptions()

        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)

        # "webSocketUrl" is needed for BiDi.
        options.set_capability('webSocketUrl', True)

        options.add_argument('--use-fake-ui-for-media-stream')

        # Allow to play media without user interaction.
        options.add_argument('--autoplay-policy=no-user-gesture-required')

        options.add_argument('--kiosk')
        options.add_argument(f'--window-size={width},{height}')
        options.add_argument('--disable-infobars')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Добавляем опцию для эмуляции вебкамеры через файл/устройство
        options.add_argument('--use-file-for-fake-video-capture=/dev/video2')        

        if disk_usage('/dev/shm').free < 2147483648:
            self._logger.info('Less than 2 GiB available in "/dev/shm", usage disabled')
            options.add_argument("--disable-dev-shm-usage")

        if disk_usage('/tmp').free < 134217728:
            self._logger.warning('Less than 128 MiB available in "/tmp", strange failures may occur')

        service = ChromeService(
            env=env,
            executable_path=driverPath,
        )

        if browserPath:
            options.binary_location = browserPath

        self.driver = ChromeDriver(
            options=options,
            service=service,
        )

        self.bidiLogsHelper = BiDiLogsHelper(self.driver, self._parentLogger)

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

        options = FirefoxOptions()

        options.set_capability('acceptInsecureCerts', self._acceptInsecureCerts)

        # "webSocketUrl" is needed for BiDi; this should be set already by
        # default, but just in case.
        options.set_capability('webSocketUrl', True)
        # In Firefox < 101 BiDi protocol was not enabled by default, although it
        # works fine for getting the logs with Firefox 99, so it is explicitly
        # enabled.
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1753997
        options.set_preference('remote.active-protocols', 3)

        options.set_preference('media.navigator.permission.disabled', True)

        # Allow to play media without user interaction.
        options.set_preference('media.autoplay.default', 0)

        options.add_argument('--kiosk')
        options.add_argument(f'--width={width}')
        options.add_argument(f'--height={height}')

        if disk_usage('/tmp').free < 134217728:
            self._logger.warning('Less than 128 MiB available in "/tmp", strange failures may occur')

        service = FirefoxService(
            env=env,
            executable_path=driverPath,
        )

        if browserPath:
            options.binary_location = browserPath

        self.driver = FirefoxDriver(
            options=options,
            service=service,
        )

        self.bidiLogsHelper = BiDiLogsHelper(self.driver, self._parentLogger)

    def clearLogs(self):
        """
        Clears browser logs not printed yet.

        This does not affect the logs in the browser itself, only the ones
        received by the SeleniumHelper.
        """

        if self.bidiLogsHelper:
            self.bidiLogsHelper.clearLogs()
            return

        self.driver.get_log('browser')

    def printLogs(self):
        """
        Prints browser logs received since last print.

        These logs do not include realtime logs, as they are printed as soon as
        they are received.
        """

        if self.bidiLogsHelper:
            self.bidiLogsHelper.printLogs()
            return

        for log in self.driver.get_log('browser'):
            self._logger.debug(log['message'])

    def execute(self, script):
        """
        Executes the given script.

        If the script contains asynchronous code "executeAsync()" should be used
        instead to properly wait until the asynchronous code finished before
        returning.

        Technically Chrome (unlike Firefox) works as expected with something
        like "execute('await someFunctionCall(); await anotherFunctionCall()'",
        but "executeAsync" has to be used instead for something like
        "someFunctionReturningAPromise().then(() => { more code })").

        If realtime logs are available logs are printed as soon as they are
        received. Otherwise they will be printed once the script has finished.

        The value returned by the script will be in turn returned by this
        function; the type will be respected and adjusted as needed (so a
        JavaScript string is returned as a Python string, but a JavaScript
        object is returned as a Python dict). If nothing is returned by the
        script None will be returned.

        :return: the value returned by the script, or None
        """

        # Real time logs are enabled while the command is being executed.
        if self.bidiLogsHelper:
            self.printLogs()
            self.bidiLogsHelper.setRealtimeLogsEnabled(True)

        result = self.driver.execute_script(script)

        if self.bidiLogsHelper:
            # Give it some time to receive the last real time logs before
            # disabling them again.
            sleep(0.5)

            self.bidiLogsHelper.setRealtimeLogsEnabled(False)

        self.printLogs()

        return result

    def executeAsync(self, script):
        """
        Executes the given script asynchronously.

        This function should be used to execute JavaScript code that needs to
        wait for a promise to be fulfilled, either explicitly or through "await"
        calls.

        The script needs to explicitly signal that the execution has finished by
        calling "returnResolve()" (with or without a parameter). If
        "returnResolve()" is not called (no matter if with or without a
        parameter) the function will automatically return once all the root
        statements of the script were executed (which works as expected if using
        "await" calls, but not if the script includes something like
        "someFunctionReturningAPromise().then(() => { more code })"; in that
        case the script should be written as
        "someFunctionReturningAPromise().then(() => { more code; returnResolve() })").

        Similarly, exceptions thrown by a root statement (including "await"
        calls) will be propagated to the Python function. However, this does not
        work if the script includes something like
        "someFunctionReturningAPromise().catch(exception => { more code; throw exception })";
        in that case the script should be written as
        "someFunctionReturningAPromise().catch(exception => { more code; returnReject(exception) })".

        If realtime logs are available logs are printed as soon as they are
        received. Otherwise they will be printed once the script has finished.

        The value returned by the script will be in turn returned by this
        function; the type will be respected and adjusted as needed (so a
        JavaScript string is returned as a Python string, but a JavaScript
        object is returned as a Python dict). If nothing is returned by the
        script None will be returned.

        Note that the value returned by the script must be explicitly specified
        by calling "returnResolve(XXX)"; it is not possible to use "return XXX".

        :return: the value returned by the script, or None
        """

        # Real time logs are enabled while the command is being executed.
        if self.bidiLogsHelper:
            self.printLogs()
            self.bidiLogsHelper.setRealtimeLogsEnabled(True)

        # Add an explicit return point at the end of the script if none is
        # given.
        if re.search('returnResolve\\(.*\\)', script) is None:
            script += '; returnResolve()'

        # await is not valid in the root context in Firefox, so the script to be
        # executed needs to be wrapped in an async function.
        # Asynchronous scripts need to explicitly signal that they are finished
        # by invoking the callback injected as the last argument with a promise
        # and resolving or rejecting the promise.
        # https://w3c.github.io/webdriver/#dfn-execute-async-script
        script = 'promise = new Promise(async(returnResolve, returnReject) => { try { ' + script + ' } catch (exception) { returnReject(exception) } }); arguments[arguments.length - 1](promise)'

        result = self.driver.execute_async_script(script)

        if self.bidiLogsHelper:
            # Give it some time to receive the last real time logs before
            # disabling them again.
            sleep(0.5)

            self.bidiLogsHelper.setRealtimeLogsEnabled(False)

        self.printLogs()

        return result


class Participant():
    """
    Wrapper for a real participant in Talk.

    This wrapper exposes functions to use a real participant in a browser.
    """

    def __init__(self, browser, nextcloudUrl, width, height, env, driverPath, browserPath, parentLogger):
        """
        Starts a real participant in the given Nextcloud URL using the given
        browser.

        :param browser: currently only "firefox" is supported.
        :param nextcloudUrl: the URL of the Nextcloud instance to start the real
            participant in.
        :param width: the width of the browser window.
        :param height: the height of the browser window.
        :param env: the environment variables, including the display to start
                    the browser in.
        :param driverPath: the path to override the default Selenium driver.
        :param browserPath: the path to override the default browser executable.
        :param parentLogger: the parent logger to get a child from.
        """

        # URL should not contain a trailing '/', as that could lead to a double
        # '/' which may prevent Talk UI from loading as expected.
        self.ffmpeg_proc = None
        self.nextcloudUrl = nextcloudUrl.rstrip('/')

        acceptInsecureCerts = config.getBackendSkipVerify(self.nextcloudUrl)

        self.seleniumHelper = SeleniumHelper(parentLogger, acceptInsecureCerts)

        if browser == 'chrome':
            self.seleniumHelper.startChrome(width, height, env, driverPath, browserPath)
        elif browser == 'firefox':
            self.seleniumHelper.startFirefox(width, height, env, driverPath, browserPath)
        else:
            raise Exception('Invalid browser: ' + browser)

    def joinCall(self, token, owner):
        """
        Joins the call in the room with the given token

        The participant will join as an internal client of the signaling server.

        :param token: the token of the room to join.
        """
        self.ffmpeg_proc = self.start_ffmpeg_stream(config.getStreamUrl())


        # self.seleniumHelper.driver.get(self.nextcloudUrl + '/index.php/call/' + token + '/recording')
        # self.seleniumHelper.driver.get(self.nextcloudUrl + '/index.php/call/' + token)
        self.seleniumHelper.driver.get(self.nextcloudUrl + '/loginAuth/' + owner + '/' + config.getBackendSecret(self.nextcloudUrl))
        self.seleniumHelper.driver.get(self.nextcloudUrl + '/index.php/call/' + token)

        # Тут сделать новое подключение к звонку

        # Ждем появления кнопки и кликаем по ней
        from time import sleep
        sleep(2)  # Лучше заменить на явное ожидание через Selenium, если потребуется

        self.seleniumHelper.execute("""
            var btn = document.getElementById('call_button');
            if (btn) {
                btn.click();
                console.log('Clicked join call button');
            } else {
                console.log('Join call button not found');
            }
        """)

        # Ждем появления второго диалога и снова кликаем по кнопке
        sleep(1)
        self.seleniumHelper.execute("""
            var close_sidebar_button = document.querySelector('.app-sidebar-header button');
            if (close_sidebar_button) {
                close_sidebar_button.click();
                console.log('Clicked close_sidebar_button');
            }
        """)



        self.seleniumHelper.execute("""
            var btn2 = document.querySelector('.recording-server button');
            if (btn2) {
                btn2.click();
                console.log('Clicked join call button (second)');
            } else {
                console.log('Join call button not found (second)');
            }
        """)

        self.seleniumHelper.execute(f'''
            console.log('test console.log1111111');
        ''')

        # OCA.Talk.signalingCallViewMode('{token}');

    def disconnect(self):
        """
        Disconnects from the signaling server.
        """
        self.ffmpeg_proc.terminate()
        self.ffmpeg_proc.wait()
        #self.seleniumHelper.execute('''
        #    OCA.Talk.signalingKill()
        #''')

    def start_ffmpeg_stream(self, stream_url):
        # Остановить предыдущий ffmpeg, если нужно (реализуйте сами)
        # Запустить новый ffmpeg для нового стрима
        cmd = [
            "ffmpeg",
            "-re",
            "-i", stream_url,
            "-vcodec", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-f", "v4l2",
            "/dev/video2"
        ]
        # subprocess.Popen запускает ffmpeg в фоне
        return subprocess.Popen(cmd)
