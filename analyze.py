import os
import requests
import json
import sys
import re

# Environment Variables
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
CHANNEL_ID = os.environ.get('YT_CHANNEL_ID', '')

YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '')
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '')
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

def get_used_topics():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = requests.get(
            SUPABASE_URL + '/rest/v1/suggested_topics',
            headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY},
            params={'select': 'topic', 'order': 'created_at.desc', 'limit': '30'},
            timeout=30
        ).json()
        if isinstance(r, list):
            return [item.get('topic', '') for item in r if item.get('topic')]
    except Exception as e:
        print("Supabase fetch error:", e)
    return []

def save_topics(topics):
    if not SUPABASE_URL or not SUPABASE_KEY or not topics:
        return
    rows = [{'topic': t} for t in topics]
    try:
        requests.post(
            SUPABASE_URL + '/rest/v1/suggested_topics',
            headers={'apikey': SUPABASE_KEY, 'Authorization': 'Bearer ' + SUPABASE_KEY, 'Content-Type': 'application/json'},
            json=rows,
            timeout=30
        )
        print(f"Saved {len(topics)} new topics to history.")
    except Exception as e:
        print("Supabase save error:", e)

def extract_topics(report):
    topics = []
    in_section = False
    for line in report.split('\n'):
        if 'Next 5 Topics' in line:
            in_section = True
            continue
        if in_section:
            line = line.strip()
            if line.startswith('- '):
                topics.append(line[2:].strip())
            elif re.match(r'^\d+\.', line):
                topics.append(re.sub(r'^\d+\.\s*', '', line).strip())
            if len(topics) == 5:
                break
    return topics

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Telegram credentials missing.")
        return
    print("📤 Sending message to Telegram...")
    max_len = 4000
    if len(text) > max_len:
        for i in range(0, len(text), max_len):
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', data={'chat_id': CHAT_ID, 'text': text[i:i+max_len], 'parse_mode': 'Markdown'}, timeout=30)
    else:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage', data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=30)

def get_access_token():
    url = 'https://oauth2.googleapis.com/token'
    data = {'client_id': YT_CLIENT_ID, 'client_secret': YT_CLIENT_SECRET, 'refresh_token': YT_REFRESH_TOKEN, 'grant_type': 'refresh_token'}
    r = requests.post(url, data=data, timeout=30)
    return r.json().get('access_token')

def get_channel_videos(access_token):
    url = f'https://www.googleapis.com/youtube/v3/search?channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=10&type=video'
    r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, timeout=30)
    data = r.json()
    return data.get('items', [])

def get_video_stats(video_ids, access_token):
    ids_str = ','.join(video_ids)
    url = f'https://www.googleapis.com/youtube/v3/videos?id={ids_str}&part=statistics,snippet'
    r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, timeout=30)
    data = r.json()
    stats = []
    if 'items' in data:
        for item in data['items']:
            title = item['snippet']['title']
            views = item['statistics'].get('viewCount', '0')
            likes = item['statistics'].get('likeCount', '0')
            comments = item['statistics'].get('commentCount', '0')
            stats.append(f"Video: {title} | Views: {views} | Likes: {likes} | Comments: {comments}")
    return stats

def analyze_with_ai(video_data, used_topics):
    if not GROQ_API_KEY: return "AI analysis skipped."
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
    
    # 🚨 Naya Prompt: Puraane topics pass kar rahe hain
    used_list = "\n".join(used_topics) if used_topics else "None"
    
    prompt = f"""
    You are an expert YouTube Shorts Growth Strategist. Look at the data of the last 10 Shorts:
    
    {chr(10).join(video_data)}
    
    IMPORTANT: Do NOT repeat the same boring report. Write a fresh, highly actionable analysis in Hinglish.
    
    Here are the topics we have ALREADY COVERED or SUGGESTED in the past. DO NOT REPEAT THESE TOPICS:
    {used_list}
    
    Format the response in these 4 sections:
    
    1. 📊 **Aaj Ka Reality Check:** (1-2 lines on current performance based on the numbers)
    2. 🔍 **Naya Experiment:** (Give 1 specific, unique thing to try today.)
    3. 🎨 **Thumbnail/Title Ka Naya Style:** (Give 1 fresh idea)
    4. 💡 **Next 5 Topics:** (Suggest 5 NEW topics. Put each topic on a new line starting with '- ')
    
    Keep it highly motivational and use emojis.
    """
    
    data = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8}
    r = requests.post(url, headers=headers, json=data, timeout=60)
    result = r.json()
    
    if 'choices' in result:
        return result['choices'][0]['message']['content']
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
        
    video_stats = get_video_stats([v['id']['videoId'] for v in videos], access_token)
    
    # 🚨 Supabase se puraane topics laao
    used_topics = get_used_topics()
    print(f"Found {len(used_topics)} used topics in DB.")
    
    send_telegram_message("🧠 AI tumhare channel ka analysis kar raha hai (with memory)...")
    
    report = analyze_with_ai(video_stats, used_topics)
    
    # 🚨 Naye topics extract karke save karo
    new_topics = extract_topics(report)
    if new_topics:
        save_topics(new_topics)
    
    final_message = f"📈 **CHANNEL ANALYSIS REPORT** 📈\n\n{report}"
    send_telegram_message(final_message)
    print("=== Analysis Complete ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        sys.exit(1)
