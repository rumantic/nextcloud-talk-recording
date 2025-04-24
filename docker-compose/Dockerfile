FROM ubuntu:20.04

# SPDX-FileCopyrightText: 2023 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get --assume-yes update
RUN apt-get --assume-yes upgrade

# Common dependencies
RUN apt-get --assume-yes install software-properties-common

# nextcloud-talk-recording dependencies
RUN apt-get --assume-yes install ffmpeg pulseaudio python3-pip xvfb
RUN pip3 install --upgrade requests

# firefox
RUN apt-get --assume-yes install firefox firefox-geckodriver

RUN apt-get --assume-yes install wget
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chromium.deb
RUN apt-get --assume-yes install /tmp/chromium.deb
RUN rm /tmp/chromium.deb

#COPY ./docker-compose/wrap_chromium_binary /opt/bin/wrap_chromium_binary
#RUN chmod +x /opt/bin/wrap_chromium_binary
#RUN /opt/bin/wrap_chromium_binary
#change

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

# Switch user and start the recording server
WORKDIR "/home/recording/"
USER "recording"
CMD ["python3", "-m", "nextcloud.talk.recording", "--config", "/etc/nextcloud-talk-recording/server.conf"]
