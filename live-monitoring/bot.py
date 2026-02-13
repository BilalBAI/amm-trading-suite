import os
import json
import requests
# placeholder Telegram bot send
TELEGRAM_BOT_TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN','')
CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID','')

def send(msg):
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        print('Telegram not configured')
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode':'Markdown'}
    try:
        r = requests.post(url, data=data)
        print(r.text)
    except Exception as e:
        print(e)

if __name__=='__main__':
    send('Live monitor started')
