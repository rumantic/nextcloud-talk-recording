#!/bin/bash

# Получаем ссылку на стрим из server.conf
STREAM_URL=$(grep '^stream_url' /etc/nextcloud-talk-recording/server.conf | cut -d'=' -f2 | xargs)

# Запуск ffmpeg в фоне
ffmpeg -re -i "$STREAM_URL" -vcodec rawvideo -pix_fmt yuv420p -f v4l2 /dev/video2 &

# Запуск основного приложения
exec python3 -m nextcloud.talk.recording --config /etc/nextcloud-talk-recording/server.conf