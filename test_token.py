import os, requests

CLIENT_ID = os.environ['YT_CLIENT_ID_2']
CLIENT_SECRET = os.environ['YT_CLIENT_SECRET_2']
REFRESH_TOKEN = os.environ['YT_REFRESH_TOKEN_2']
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

url = 'https://oauth2.googleapis.com/token'
data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
r = requests.post(url, data=data).json()

if 'access_token' not in r:
    msg = "❌ Error: Access Token fail ho gaya. Details: " + str(r)
    requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', data={'chat_id': CHAT_ID, 'text': msg})
    exit(1)

access_token = r['access_token']
headers = {'Authorization': 'Bearer ' + access_token}
c_url = 'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true'
c_res = requests.get(c_url, headers=headers).json()

if 'items' in c_res and len(c_res['items']) > 0:
    ch_name = c_res['items'][0]['snippet']['title']
    msg = f"✅ Token Sahi Hai!\n\nYe token is channel ka hai: {ch_name}"
else:
    msg = "❌ Token ban gaya par channel info nahi mili. Error: " + str(c_res)

requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', data={'chat_id': CHAT_ID, 'text': msg})
