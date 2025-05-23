#
# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#

"""
Module to send requests to the Nextcloud server.
"""

import hashlib
import hmac
import json
import logging
import os
from secrets import token_urlsafe

from requests import Request, Session
from requests_toolbelt import MultipartEncoder

from nextcloud.talk import recording
from .Config import config

logger = logging.getLogger(__name__)

def getRandomAndChecksum(backend, data):
    """
    Returns a random string and the checksum of the given data with that random.

    :param backend: the backend to send the data to.
    :param data: the data, as bytes.
    """
    secret = config.getBackendSecret(backend).encode()
    random = token_urlsafe(64)
    hmacValue = hmac.new(secret, random.encode() + data, hashlib.sha256)

    return random, hmacValue.hexdigest()

def doRequest(backend, request, retries=3):
    """
    Send the request to the backend.

    SSL verification will be skipped if configured.

    :param backend: the backend to send the request to.
    :param request: the request to send.
    :param retries: the number of times to retry in case of failure.
    """
    backendSkipVerify = config.getBackendSkipVerify(backend)

    try:
        session = Session()
        preparedRequest = session.prepare_request(request)
        response = session.send(preparedRequest, verify=not backendSkipVerify)
        response.raise_for_status()
    except Exception:
        if retries > 1:
            logger.exception("Failed to send message to backend, %d retries left!", retries)
            doRequest(backend, request, retries - 1)
        else:
            logger.exception("Failed to send message to backend, giving up!")
            raise

def backendRequest(backend, data):
    """
    Sends the data to the backend on the endpoint to receive notifications from
    the recording server.

    The data is automatically wrapped in a request for the appropriate URL and
    with the needed headers.

    :param backend: the backend to send the data to.
    :param data: the data to send.
    """
    url = backend.rstrip('/') + '/ocs/v2.php/apps/spreed/api/v1/recording/backend'

    data = json.dumps(data).encode()

    random, checksum = getRandomAndChecksum(backend, data)

    headers = {
        'Content-Type': 'application/json',
        'OCS-ApiRequest': 'true',
        'Talk-Recording-Random': random,
        'Talk-Recording-Checksum': checksum,
        'User-Agent': recording.USER_AGENT,
    }

    request = Request('POST', url, headers, data=data)

    doRequest(backend, request)

def started(backend, token, status, actorType, actorId):
    """
    Notifies the backend that the recording was started.

    :param backend: the backend of the conversation.
    :param token: the token of the conversation.
    :param actorType: the actor type of the Talk participant that started the
           recording.
    :param actorId: the actor id of the Talk participant that started the
           recording.
    """

    backendRequest(backend, {
        'type': 'started',
        'started': {
            'token': token,
            'status': status,
            'actor': {
                'type': actorType,
                'id': actorId,
            },
        },
    })

def stopped(backend, token, actorType, actorId):
    """
    Notifies the backend that the recording was stopped.

    :param backend: the backend of the conversation.
    :param token: the token of the conversation.
    :param actorType: the actor type of the Talk participant that stopped the
           recording.
    :param actorId: the actor id of the Talk participant that stopped the
           recording.
    """

    data = {
        'type': 'stopped',
        'stopped': {
            'token': token,
        },
    }

    if actorType is not None and actorId is not None:
        data['stopped']['actor'] = {
            'type': actorType,
            'id': actorId,
        }

    backendRequest(backend, data)

def failed(backend, token):
    """
    Notifies the backend that the recording failed.

    :param backend: the backend of the conversation.
    :param token: the token of the conversation.
    """

    data = {
        'type': 'failed',
        'failed': {
            'token': token,
        },
    }

    backendRequest(backend, data)

def uploadRecording(backend, token, fileName, owner):
    """
    Upload the recording specified by fileName.

    The name of the uploaded file is the basename of the original file.

    :param backend: the backend to upload the file to.
    :param token: the token of the conversation that was recorded.
    :param fileName: the recording file name.
    :param owner: the owner of the uploaded file.
    """

    logger.info("Upload recording %s to %s in %s as %s", fileName, backend, token, owner)

    url = backend.rstrip('/') + '/ocs/v2.php/apps/spreed/api/v1/recording/' + token + '/store'

    # Plain values become arguments, while tuples become files; the body used to
    # calculate the checksum is empty.
    data = {
        'owner': owner,
        # pylint: disable=consider-using-with
        'file': (os.path.basename(fileName), open(fileName, 'rb')),
    }

    multipartEncoder = MultipartEncoder(data)

    random, checksum = getRandomAndChecksum(backend, token.encode())

    headers = {
        'Content-Type': multipartEncoder.content_type,
        'OCS-ApiRequest': 'true',
        'Talk-Recording-Random': random,
        'Talk-Recording-Checksum': checksum,
        'User-Agent': recording.USER_AGENT,
    }

    uploadRequest = Request('POST', url, headers, data=multipartEncoder)

    doRequest(backend, uploadRequest)
