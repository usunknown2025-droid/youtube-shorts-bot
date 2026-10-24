import os
import requests
import json
import sys

# Environment Variables
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
CHANNEL_ID = os.environ.get('YT_CHANNEL_ID', '')

YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '')
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '')
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '')

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing, skipping message.")
        return
    max_len = 4000
    if len(text) > max_len:
        for i in range(0, len(text), max_len):
            requests.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                data={'chat_id': CHAT_ID, 'text': text[i:i+max_len]},
                timeout=30
            )
    else:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=30
        )

def get_access_token():
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("❌ Missing YT_CLIENT_ID, YT_CLIENT_SECRET, or YT_REFRESH_TOKEN")
        return None
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': YT_CLIENT_ID,
        'client_secret': YT_CLIENT_SECRET,
        'refresh_token': YT_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    print("Fetching YouTube Access Token...")
    r = requests.post(url, data=data, timeout=30)
    res = r.json()
    if 'access_token' in res:
        print("✅ Access Token received.")
        return res['access_token']
    else:
        print("❌ OAuth Token Error:", res)
        return None

def get_channel_videos(access_token):
    if not CHANNEL_ID:
        print("❌ Missing YT_CHANNEL_ID")
        return []
    url = f'https://www.googleapis.com/youtube/v3/search?channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=10&type=video'
    headers = {'Authorization': f'Bearer {access_token}'}
    print("Fetching recent videos...")
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    
    if 'items' not in data:
        print("❌ Error fetching videos:", data)
        return []
    print(f"✅ Found {len(data['items'])} videos.")
    return data['items']

def get_video_stats(video_ids, access_token):
    ids_str = ','.join(video_ids)
    url = f'https://www.googleapis.com/youtube/v3/videos?id={ids_str}&part=statistics,snippet'
    headers = {'Authorization': f'Bearer {access_token}'}
    print("Fetching video stats...")
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    
    if 'items' not in data:
        print("❌ Error fetching stats:", data)
        return []
        
    stats = []
    for item in data['items']:
        title = item['snippet']['title']
        views = item['statistics'].get('viewCount', '0')
        likes = item['statistics'].get('likeCount', '0')
        comments = item['statistics'].get('commentCount', '0')
        stats.append(f"Title: {title} | Views: {views} | Likes: {likes} | Comments: {comments}")
    print(f"✅ Stats fetched for {len(stats)} videos.")
    return stats

def analyze_with_ai(video_data):
    if not GROQ_API_KEY:
        print("❌ Missing GROQ_API_KEY")
        return "AI analysis skipped."
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""
    You are an expert YouTube Shorts Growth Strategist for a 'Miniature Repair' channel.
    Here is the data of the last 10 Shorts uploaded on the channel:
    
    {chr(10).join(video_data)}
    
    Please analyze this data and give a very practical, actionable report in HINDI (Hinglish).
    Format the response in these 4 sections:
    
    1. 📊 **Channel Analysis (Abhi tak ka Result):** Overall performance kaisa hai? Kaunsi video chali aur kaunsi nahi?
    2. ⚠️ **Kamiya (Weaknesses):** Views/Likes kam aane ke kya reasons ho sakte hain? Titles, Thumbnails ya Content, kahan sudhar chahiye?
    3. 🚀 **Viral Strategy (Kese Aage Badhe):** Competitors kya kar rahe hain jo humein bhi karna chahiye? Views badhane ke liye kya trick lagayein?
    4. 💡 **Agle 5 Topics:** Aise 5 next topics suggest karo jo is niche mein aage viral ho sakte hain.
    
    Keep it highly motivational, straight-forward, and use emojis. Do not write a boring essay.
    """
    
    data = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    print("Calling Groq AI for analysis...")
    r = requests.post(url, headers=headers, json=data, timeout=60)
    result = r.json()
    
    if 'choices' in result:
        print("✅ AI analysis successful.")
        return result['choices'][0]['message']['content']
    else:
        print("❌ Groq Error:", result)
        return "❌ AI analysis fail ho gaya."

def main():
    print("=== Starting Analysis ===")
    
    access_token = get_access_token()
    if not access_token:
        send_telegram_message("❌ YouTube Token fail ho gaya. GitHub logs check karo.")
        return

    videos = get_channel_videos(access_token)
    if not videos:
        send_telegram_message("❌ Channel se videos fetch nahi ho payi.")
        return
        
    video_ids = [v['id']['videoId'] for v in videos]
    
    video_stats = get_video_stats(video_ids, access_token)
    if not video_stats:
        send_telegram_message("❌ Video statistics fetch nahi ho payi.")
        return
        
    send_telegram_message("🧠 AI tumhare channel ka analysis kar raha hai, please wait 10-20 seconds...")
    
    report = analyze_with_ai(video_stats)
    
    final_message = f"📈 **CHANNEL ANALYSIS REPORT** 📈\n\n{report}"
    send_telegram_message(final_message)
    print("=== Analysis Complete ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        sys.exit(1)
