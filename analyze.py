import os
import requests
import json

# Environment Variables
GROQ_API_KEY = os.environ['GROQ_API_KEY']
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['CHAT_ID']
YT_API_KEY = os.environ['YT_API_KEY'] # Standard API Key (not OAuth)
CHANNEL_ID = os.environ['YT_CHANNEL_ID']

def send_telegram_message(text):
    # Telegram message limit is 4096 chars, so we split if needed
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

def get_channel_videos():
    # Search for recent videos in the channel
    url = f'https://www.googleapis.com/youtube/v3/search?key={YT_API_KEY}&channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=10&type=video'
    r = requests.get(url, timeout=30)
    data = r.json()
    
    if 'items' not in data:
        print("Error fetching videos:", data)
        return []
        
    return data['items']

def get_video_stats(video_ids):
    ids_str = ','.join(video_ids)
    url = f'https://www.googleapis.com/youtube/v3/videos?key={YT_API_KEY}&id={ids_str}&part=statistics,snippet'
    r = requests.get(url, timeout=30)
    data = r.json()
    
    if 'items' not in data:
        return []
        
    stats = []
    for item in data['items']:
        title = item['snippet']['title']
        views = item['statistics'].get('viewCount', '0')
        likes = item['statistics'].get('likeCount', '0')
        comments = item['statistics'].get('commentCount', '0')
        stats.append(f"Title: {title} | Views: {views} | Likes: {likes} | Comments: {comments}")
        
    return stats

def analyze_with_ai(video_data):
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
    3. 🚀 **Viral Strategy (Kese Aage Badhe):** Competitors (jaise Miniature repair channels) kya kar rahe hain jo humein bhi karna chahiye? Views badhane ke liye kya trick lagayein?
    4. 💡 **Agle 5 Topics:** Aise 5 next topics suggest karo jo is niche mein aage viral ho sakte hain.
    
    Keep it highly motivational, straight-forward, and use emojis. Do not write a boring essay.
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
        print("Groq Error:", result)
        return "❌ AI analysis fail ho gaya. GitHub logs check karo."

def main():
    print("Fetching recent videos...")
    videos = get_channel_videos()
    if not videos:
        send_telegram_message("❌ Channel se videos fetch nahi ho payi. Channel ID ya API Key check karo.")
        return
        
    video_ids = [v['id']['videoId'] for v in videos]
    
    print("Fetching video stats...")
    video_stats = get_video_stats(video_ids)
    
    if not video_stats:
        send_telegram_message("❌ Video statistics fetch nahi ho payi.")
        return
        
    send_telegram_message("🧠 AI tumhare channel ka analysis kar raha hai, please wait 10-20 seconds...")
    
    print("Analyzing with AI...")
    report = analyze_with_ai(video_stats)
    
    final_message = f"📈 **CHANNEL ANALYSIS REPORT** 📈\n\n{report}"
    send_telegram_message(final_message)
    print("Done!")

if __name__ == "__main__":
    main()
