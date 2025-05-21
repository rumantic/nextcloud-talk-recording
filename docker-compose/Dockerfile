FROM ubuntu:20.04

# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get --assume-yes update
RUN apt-get --assume-yes upgrade

# Common dependencies
RUN apt-get --assume-yes install software-properties-common

# nextcloud-talk-recording dependencies
RUN apt-get --assume-yes install ffmpeg pulseaudio python3-pip xvfb

# v4l2loopback for virtual webcam (пункт 1)
RUN apt-get update && apt-get --assume-yes install --fix-missing v4l2loopback-dkms v4l2loopback-utils

RUN pip3 install --upgrade requests

# firefox
RUN apt-get --assume-yes install firefox firefox-geckodriver

RUN apt-get --assume-yes install wget
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chromium.deb
RUN apt-get --assume-yes install /tmp/chromium.deb
RUN rm /tmp/chromium.deb

# nextcloud-talk-recording config
RUN useradd --create-home recording
COPY server.conf /etc/nextcloud-talk-recording/server.conf
RUN sed --in-place 's/#listen =.*/listen = 0.0.0.0:1234/' /etc/nextcloud-talk-recording/server.conf

# Deploy recording server
RUN mkdir --parents /tmp/recording
COPY src /tmp/recording/
COPY pyproject.toml /tmp/recording/
RUN python3 -m pip install file:///tmp/recording/

# Cleanup
RUN apt-get clean && rm --recursive --force /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN rm --recursive --force /tmp/recording

# v4l2loopback setup (пункт 2)
RUN modprobe v4l2loopback devices=1 video_nr=2 card_label="VirtualCam" exclusive_caps=1 || true

#COPY docker-compose/start.sh /start.sh
#RUN chmod +x /start.sh

# Switch user and start the recording server
WORKDIR "/home/recording/"
USER "recording"

#CMD ["/start.sh"]
CMD ["python3", "-m", "nextcloud.talk.recording", "--config", "/etc/nextcloud-talk-recording/server.conf"]