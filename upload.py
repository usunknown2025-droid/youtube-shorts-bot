import os
import requests
import json
from datetime import datetime, timedelta
import subprocess

BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
FILE_ID = os.environ['FILE_ID']
TITLE = os.environ['TITLE']
DESCRIPTION = os.environ.get('DESCRIPTION', '')
TAGS_STR = os.environ.get('TAGS', '')
TAGS = [t.strip() for t in TAGS_STR.split(',') if t.strip()]
SCHEDULE_TIME = os.environ.get('SCHEDULE_TIME', '').strip() 
CHANNEL = os.environ.get('CHANNEL', '1').strip()

# 🚨 CHANNEL KE HISAAB SE TOKEN SELECT KARO
if CHANNEL == '2':
    YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID_2', '').strip()
    YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET_2', '').strip()
    YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN_2', '').strip()
    print("🚀 Uploading to Channel 2")
else:
    YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '').strip()
    YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '').strip()
    YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '').strip()
    print("🚀 Uploading to Channel 1")

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

    # 🚨 DEFAULT: 3 MINUTE BAAD PUBLIC HOGA
    publish_time = datetime.utcnow() + timedelta(minutes=3)
    
    # Agar user ne schedule time diya hai, toh usko use karo
    if SCHEDULE_TIME:
        try:
            clean_time = SCHEDULE_TIME.replace('Z', '+00:00')
            publish_time = datetime.fromisoformat(clean_time)
            print(f"Using scheduled time: {publish_time}")
        except Exception as e:
            print(f'Schedule time parse error: {e}. Using default 3 mins.')

    # Format: 2026-10-29T18:00:00Z
    publish_at_str = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    status_body = {
        'privacyStatus': 'private', # Private rahega tab tak
        'publishAt': publish_at_str, # Ye time aate hi khud public ho jayega
        'selfDeclaredMadeForKids': False,
        'containsSyntheticMedia': True
    }
    print(f"Video will auto-publish at: {publish_at_str}")

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

send_message('⏳ Video mein Like & Subscribe animation add ki ja rahi hai...')
final_video_path = 'final_video.mp4'

result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path], capture_output=True, text=True)
try:
    duration = float(result.stdout.strip())
except:
    duration = 10.0

start_time = max(0, duration - 2.0)

ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,120,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{start_time},{duration},Default,,0,0,0,,LIKE & SUBSCRIBE
"""

with open('subs.ass', 'w') as f:
    f.write(ass_content)

subprocess.run(['ffmpeg', '-y', '-i', video_path, '-vf', 'ass=subs.ass', '-c:a', 'copy', final_video_path], capture_output=True)

send_message(f'⏳ Video {CHANNEL} par upload ho rahi hai...')
yt_id = upload_to_youtube(final_video_path, TITLE, DESCRIPTION, TAGS)

if yt_id:
    link = 'https://youtu.be/' + yt_id
    print('Upload Success: ' + link)
    send_message(f'✅ Video YouTube par upload ho gayi hai!\n\nTitle: {TITLE}\nLink: {link}\n\n⏳ Ye abhi Private hai. YouTube khud isko 3 minute baad Public kar dega (ya aapke diye hue time par).')
else:
    send_message('❌ YouTube upload fail ho gaya. GitHub logs check karo.')

print('=== Done ===')
