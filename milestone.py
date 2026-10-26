import os
import requests
from datetime import datetime

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '') # Not used but good to have
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
CHANNEL_ID = os.environ.get('YT_CHANNEL_ID', '')
YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '')
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '')
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '')

def send_message(text):
    requests.post(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
        timeout=30
    )

def get_access_token():
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': YT_CLIENT_ID,
        'client_secret': YT_CLIENT_SECRET,
        'refresh_token': YT_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    r = requests.post(url, data=data, timeout=30)
    return r.json().get('access_token')

def check_milestones():
    access_token = get_access_token()
    if not access_token:
        print("Token fail")
        return

    # Fetch last 10 videos
    url = f'https://www.googleapis.com/youtube/v3/search?channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=10&type=video'
    headers = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()

    if 'items' not in data:
        print("No videos found")
        return

    video_ids = [v['id']['videoId'] for v in data['items']]
    ids_str = ','.join(video_ids)

    # Get stats for those videos
    url_stats = f'https://www.googleapis.com/youtube/v3/videos?id={ids_str}&part=statistics,snippet'
    r_stats = requests.get(url_stats, headers=headers, timeout=30)
    stats_data = r_stats.json()

    if 'items' not in stats_data:
        return

    # Milestones to check
    milestones = [100, 1000, 10000, 100000]

    for video in stats_data['items']:
        title = video['snippet']['title']
        views = int(video['statistics'].get('viewCount', 0))
        
        # Check if it crossed a milestone exactly today (we check if views are within a small range above the milestone)
        # For example, if views are 100-105, it means it just crossed 100.
        for m in milestones:
            if m <= views <= (m + 50):  # 50 views buffer
                # To avoid spamming, you can implement a database check here. 
                # For now, we will just send the alert.
                msg = f"🎉 *MILESTONE ACHIEVED!* 🎉\n\n"
                msg += f"Video: *{title}*\n"
                msg += f"Views: *{views}*\n\n"
                
                if m == 100:
                    msg += "🔥 Hamare channel ne apna pehla 100 views cross kar liya! Shuruaat ho gayi hai!"
                elif m == 1000:
                    msg += "🚀 1,000 Views! YouTube algorithm ne humein notice karna shuru kar diya hai. Keep going!"
                elif m == 10000:
                    msg += "👑 10,000 Views! We are going viral. Ye sab aapki mehnat ka result hai!"
                elif m == 100000:
                    msg += "💎 100K Views! Ekdum Blockbuster! Aapne history bana di."
                
                send_message(msg)
                print(f"Milestone {m} sent for {title}")

print("=== Checking Milestones ===")
check_milestones()
print("=== Done ===")
