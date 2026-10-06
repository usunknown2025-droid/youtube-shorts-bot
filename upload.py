import json, os, requests, time, subprocess

BOT_TOKEN = os.environ['BOT_TOKEN']
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_KEY']
YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '').strip()
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '').strip()
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '').strip()

ROW_ID = os.environ['ROW_ID']
CHAT_ID = os.environ['CHAT_ID']
CUSTOM_TITLE = os.environ.get('CUSTOM_TITLE', '').strip()
CUSTOM_DESCRIPTION = os.environ.get('CUSTOM_DESCRIPTION', '').strip()
CUSTOM_TAGS = os.environ.get('CUSTOM_TAGS', '').strip()


def get_row(row_id):
    url = SUPABASE_URL + '/rest/v1/pending_shorts?id=eq.' + str(row_id)
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': 'Bearer ' + SUPABASE_KEY
    }
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return None


def update_status(row_id, status):
    url = SUPABASE_URL + '/rest/v1/pending_shorts?id=eq.' + str(row_id)
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': 'Bearer ' + SUPABASE_KEY,
        'Content-Type': 'application/json'
    }
    requests.patch(url, headers=headers, json={'status': status}, timeout=30)


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

    metadata = {
        'snippet': {
            'title': title[:100],
            'description': description[:5000],
            'tags': tags[:15],
            'categoryId': '24'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
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


def send_message(text):
    requests.post(
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        data={'chat_id': CHAT_ID, 'text': text},
        timeout=30
    )


# ---------- MAIN ----------
print('=== Upload Started for Row ID: ' + ROW_ID + ' ===')

row = get_row(ROW_ID)
if not row:
    print('Row not found')
    send_message('❌ Row not found in database')
    exit(1)

file_id = row.get('file_id')
title = CUSTOM_TITLE if CUSTOM_TITLE else row.get('title', 'Viral Short')
description = CUSTOM_DESCRIPTION if CUSTOM_DESCRIPTION else row.get('description', '')
tags_str = CUSTOM_TAGS if CUSTOM_TAGS else row.get('tags', '')
tags = [t.strip() for t in tags_str.split(',') if t.strip()]

print('Title: ' + title)
print('Description: ' + description[:100])
print('Tags: ' + str(tags[:5]))

# Download video from Telegram
print('Downloading video from Telegram...')
video_path = 'upload_video.mp4'
if not download_from_telegram(file_id, video_path):
    send_message('❌ Failed to download video from Telegram')
    exit(1)

print('Downloaded. Size: ' + str(os.path.getsize(video_path)) + ' bytes')

# Upload to YouTube
print('Uploading to YouTube...')
yt_id = upload_to_youtube(video_path, title, description, tags)

if yt_id:
    print('Success: https://youtu.be/' + yt_id)
    update_status(ROW_ID, 'uploaded')
    send_message('✅ YouTube par upload ho gaya!\n\nTitle: ' + title + '\nLink: https://youtu.be/' + yt_id)
else:
    print('Upload failed')
    update_status(ROW_ID, 'failed')
    send_message('❌ YouTube upload fail ho gaya. Dobara try karo.')

print('=== Done ===')
