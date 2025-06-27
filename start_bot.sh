#!/bin/bash

# Kill all existing tg_bot screen sessions first
screen -ls | grep tg_bot | awk '{print $1}' | while read session; do
    screen -S "${session}" -X quit
done

# Start a fresh one
screen -dmS tg_bot bash -c 'source /home/abutdtks/virtualenv/test.abutchikikz.online/3.11/bin/activate && cd /home/abutdtks/test.abutchikikz.online && python telegram_bot/bot_handler.py'
