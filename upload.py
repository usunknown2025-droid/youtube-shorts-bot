import os
import requests
import json
from datetime import datetime, timedelta

BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
FILE_ID = os.environ['FILE_ID']
TITLE = os.environ['TITLE']
DESCRIPTION = os.environ.get('DESCRIPTION', '')
TAGS_STR = os.environ.get('TAGS', '')
TAGS = [t.strip() for t in TAGS_STR.split(',') if t.strip()]
SCHEDULE_TIME = os.environ.get('SCHEDULE_TIME', '').strip() 

YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '').strip()
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '').strip()
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '').strip()

def send_message(text):
    requests.post(
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        data={'chat_id': CHAT_ID, 'text': text},
        timeout=30
    )

def get_youtube_access_token():
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': YT_CLIENT_ID,
        'client_secret': YT_CLIENT_SECRET,
        'refresh_token': YT_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    r = requests.post(url, data=data, timeout=30)
    result = r.json()
    if 'access_token' in result:
        return result['access_token']
    print('Token error: ' + str(result))
    return None

def download_from_telegram(file_id, path):
    url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/getFile'
    r = requests.get(url, params={'file_id': file_id}, timeout=30)
    result = r.json()
    if not result.get('ok'):
        print('getFile error: ' + str(result))
        return False
    file_path = result['result']['file_path']
    download_url = 'https://api.telegram.org/file/bot' + BOT_TOKEN + '/' + file_path
    r2 = requests.get(download_url, timeout=120)
    with open(path, 'wb') as f:
        f.write(r2.content)
    return True

def upload_to_youtube(video_path, title, description, tags):
    access_token = get_youtube_access_token()
    if not access_token:
        return None

    url = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status'
    headers = {'Authorization': 'Bearer ' + access_token}

    status_body = {
    'privacyStatus': 'private', # 🚨 FIX: Schedule karne ke liye private hona zaroori hai
    'selfDeclaredMadeForKids': False,
    'containsSyntheticMedia': True
    }

    if SCHEDULE_TIME:
        try:
            # 🚨 FIX: Time parsing handles milliseconds (.000Z)
            clean_time = SCHEDULE_TIME.replace('Z', '+00:00')
            dt = datetime.fromisoformat(clean_time)
            publish_time = dt + timedelta(minutes=5)
            
            # YouTube API format: YYYY-MM-DDThh:mm:ss.sZ
            publish_at_str = publish_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            status_body['publishAt'] = publish_at_str
            print(f'Video will be published at: {publish_at_str}')
        except Exception as e:
            print(f'Time parsing error: {e}. Video will remain unlisted.')

    metadata = {
        'snippet': {
            'title': title[:100],
            'description': description[:5000],
            'tags': tags[:15],
            'categoryId': '24' 
        },
        'status': status_body
    }

    with open(video_path, 'rb') as f:
        files = {
            'metadata': ('metadata.json', json.dumps(metadata), 'application/json'),
            'video': (os.path.basename(video_path), f, 'video/mp4')
        }
        r = requests.post(url, headers=headers, files=files, timeout=300)
    result = r.json()
    if 'id' in result:
        return result['id']
    print('YouTube upload error: ' + str(result)[:500])
    return None

print('=== Starting Upload Process ===')
send_message('⏳ Video download ho rahi hai, please wait...')

video_path = 'upload_video.mp4'
if not download_from_telegram(FILE_ID, video_path):
    send_message('❌ Video download fail ho gaya.')
    exit(1)

send_message('⏳ Video YouTube par upload ho rahi hai...')
yt_id = upload_to_youtube(video_path, TITLE, DESCRIPTION, TAGS)

if yt_id:
    link = 'https://youtu.be/' + yt_id
    print('Upload Success: ' + link)
    send_message(f'✅ Video YouTube par upload ho gayi hai!\n\nTitle: {TITLE}\nLink: {link}\n\n⏳ Ye abhi Unlisted hai. YouTube Studio se edit karlo, 5 minute baad ye apne aap Public ho jayegi!')
else:
    send_message('❌ YouTube upload fail ho gaya. GitHub logs check karo.')

print('=== Done ===')
