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
    # Telegram limit is 4096, we split if needed
    max_len = 4000
    if len(text) > max_len:
        for i in range(0, len(text), max_len):
            requests.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                data={'chat_id': CHAT_ID, 'text': text[i:i+max_len], 'parse_mode': 'Markdown'},
                timeout=30
            )
    else:
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

def get_channel_videos(access_token):
    url = f'https://www.googleapis.com/youtube/v3/search?channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=10&type=video'
    headers = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    if 'items' not in data:
        print("❌ Error fetching videos:", data)
        return []
    return data['items']

def get_video_stats(video_ids, access_token):
    ids_str = ','.join(video_ids)
    url = f'https://www.googleapis.com/youtube/v3/videos?id={ids_str}&part=statistics,snippet'
    headers = {'Authorization': f'Bearer {access_token}'}
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    
    if 'items' not in data:
        return []
        
    stats = []
    for item in data['items']:
        title = item['snippet']['title']
        views = item['statistics'].get('viewCount', '0')
        likes = item['statistics'].get('likeCount', '0')
        comments = item['statistics'].get('commentCount', '0')
        stats.append(f"Video: {title} | Views: {views} | Likes: {likes} | Comments: {comments}")
    return stats

def analyze_with_ai(video_data):
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # 🚨 NAYA PROMPT: No Tables, Clean Format
    prompt = f"""
You are an expert YouTube Shorts Growth Strategist. Look at the data of the last 10 Shorts:

{chr(10).join(video_data)}

IMPORTANT: Do NOT repeat the same boring report every day. Write a fresh, highly actionable analysis in Hinglish.
Read the data carefully. If views are low, tell me a NEW trick. If a video did well, tell me how to double down on it.

Format the response in these 4 sections:

1. 📊 **Aaj Ka Reality Check:** (1-2 lines on current performance based on the numbers)
2. 🔍 **Naya Experiment (Jo aaj try karna hai):** (Give 1 specific, unique thing to try today. e.g., "Aaj ki video mein pehle 1 second ke liye screen flash karo")
3. 🎨 **Thumbnail/Title Ka Naya Style:** (Give 1 fresh idea for a title or thumbnail based on the data)
4. 💡 **Next 5 Topics:** (Suggest 5 next topics. Try to give topics that we haven't done yet, but are related to our niche)

Keep it highly motivational, straight-forward, and use emojis. Sound like a human coach.
"""
    
    data = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    r = requests.post(url, headers=headers, json=data, timeout=60)
    result = r.json()
    
    if 'choices' in result:
        return result['choices'][0]['message']['content']
    else:
        print("❌ Groq Error:", result)
        return "❌ AI analysis fail ho gaya."

def main():
    print("=== Starting Analysis ===")
    access_token = get_access_token()
    if not access_token:
        send_telegram_message("❌ YouTube Token fail ho gaya.")
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
    
    final_message = f"📈 *CHANNEL ANALYSIS REPORT* 📈\n\n{report}"
    send_telegram_message(final_message)
    print("=== Analysis Complete ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        sys.exit(1)
