import json
import os
import requests
import time
from datetime import datetime, timedelta

YT_CLIENT_ID = os.environ.get('YT_ANALYTICS_CLIENT_ID', '')
YT_CLIENT_SECRET = os.environ.get('YT_ANALYTICS_CLIENT_SECRET', '')
YT_REFRESH_TOKEN = os.environ.get('YT_ANALYTICS_REFRESH_TOKEN', '')
YT_CHANNEL_ID = os.environ.get('YT_CHANNEL_ID', '')

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')


def get_access_token():
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


def get_channel_videos(access_token, max_results=50):
    url = 'https://www.googleapis.com/youtube/v3/search'
    params = {
        'part': 'id,snippet',
        'channelId': YT_CHANNEL_ID,
        'maxResults': max_results,
        'order': 'date',
        'type': 'video'
    }
    headers = {'Authorization': 'Bearer ' + access_token}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    result = r.json()
    videos = []
    if 'items' in result:
        for item in result['items']:
            videos.append({
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'published': item['snippet']['publishedAt']
            })
    return videos


def get_video_stats(access_token, video_ids):
    url = 'https://www.googleapis.com/youtube/v3/videos'
    ids_str = ','.join(video_ids)
    params = {'part': 'statistics,snippet,contentDetails', 'id': ids_str}
    headers = {'Authorization': 'Bearer ' + access_token}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    result = r.json()
    videos = []
    if 'items' in result:
        for item in result['items']:
            stats = item['statistics']
            videos.append({
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'tags': item['snippet'].get('tags', []),
                'description': item['snippet'].get('description', '')[:200],
                'published': item['snippet']['publishedAt'],
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'duration': item['contentDetails']['duration']
            })
    return videos


def get_analytics_data(access_token, start_date, end_date):
    url = 'https://youtubeanalytics.googleapis.com/v2/reports'
    params = {
        'ids': 'channel==MINE',
        'startDate': start_date,
        'endDate': end_date,
        'metrics': 'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,comments,shares',
        'dimensions': 'video',
        'sort': '-views',
        'maxResults': 25
    }
    headers = {'Authorization': 'Bearer ' + access_token}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    result = r.json()
    if 'rows' not in result:
        print('Analytics error: ' + str(result)[:300])
        return []
    
    columns = [h['name'] for h in result.get('columnHeaders', [])]
    rows = []
    for row in result['rows']:
        data = dict(zip(columns, row))
        rows.append(data)
    return rows


def get_traffic_sources(access_token, start_date, end_date):
    url = 'https://youtubeanalytics.googleapis.com/v2/reports'
    params = {
        'ids': 'channel==MINE',
        'startDate': start_date,
        'endDate': end_date,
        'metrics': 'views,estimatedMinutesWatched',
        'dimensions': 'insightTrafficSourceType',
        'sort': '-views',
        'maxResults': 10
    }
    headers = {'Authorization': 'Bearer ' + access_token}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    result = r.json()
    if 'rows' not in result:
        return []
    columns = [h['name'] for h in result.get('columnHeaders', [])]
    rows = []
    for row in result['rows']:
        data = dict(zip(columns, row))
        rows.append(data)
    return rows


def groq_analyze(prompt):
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {'Authorization': 'Bearer ' + GROQ_KEY, 'Content-Type': 'application/json'}
    payload = {
        'model': 'openai/gpt-oss-120b',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.5,
        'max_tokens': 2000
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        result = r.json()
        if 'choices' in result:
            return result['choices'][0]['message']['content']
    except Exception as e:
        print('Groq error: ' + str(e))
    return None


def send_telegram(text):
    url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage'
    max_len = 4000
    if len(text) <= max_len:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': text}, timeout=30)
    else:
        chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
        for chunk in chunks:
            requests.post(url, data={'chat_id': CHAT_ID, 'text': chunk}, timeout=30)
            time.sleep(1)


# ---------- MAIN ----------
print('=== CHANNEL ANALYSIS STARTED ===')

access_token = get_access_token()
if not access_token:
    send_telegram('Bhai, channel analysis fail ho gaya - access token error')
    exit(1)

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d')

print('Recent videos fetch kar raha hoon...')
videos = get_channel_videos(access_token, 20)
if not videos:
    send_telegram('Bhai, channel pe koi video nahi mili')
    exit(1)

video_ids = [v['video_id'] for v in videos]
print('Video stats fetch kar raha hoon...')
videos_with_stats = get_video_stats(access_token, video_ids)

print('Analytics data fetch kar raha hoon...')
analytics = get_analytics_data(access_token, start_date, end_date)

print('Traffic sources fetch kar raha hoon...')
traffic = get_traffic_sources(access_token, start_date, end_date)

# Build raw data for AI
raw_data = 'CHANNEL DATA (Last 28 days):\n\n'
raw_data += 'Total videos: ' + str(len(videos_with_stats)) + '\n'
total_views = sum(v['views'] for v in videos_with_stats)
total_likes = sum(v['likes'] for v in videos_with_stats)
total_comments = sum(v['comments'] for v in videos_with_stats)
raw_data += 'Total views: ' + str(total_views) + '\n'
raw_data += 'Total likes: ' + str(total_likes) + '\n'
raw_data += 'Total comments: ' + str(total_comments) + '\n\n'

# All videos sorted
sorted_videos = sorted(videos_with_stats, key=lambda x: x['views'], reverse=True)

raw_data += 'TOP 5 VIDEOS:\n'
for i, v in enumerate(sorted_videos[:5]):
    raw_data += str(i + 1) + '. "' + v['title'] + '" - ' + str(v['views']) + ' views, ' + str(v['likes']) + ' likes, ' + str(v['comments']) + ' comments\n'

raw_data += '\nBOTTOM 5 VIDEOS:\n'
for i, v in enumerate(sorted_videos[-5:]):
    raw_data += str(i + 1) + '. "' + v['title'] + '" - ' + str(v['views']) + ' views, ' + str(v['likes']) + ' likes\n'

if analytics:
    raw_data += '\nANALYTICS SUMMARY:\n'
    total_analytics_views = sum(a.get('views', 0) for a in analytics)
    raw_data += 'Total views (28 days): ' + str(total_analytics_views) + '\n'
    
    avg_retention = sum(a.get('averageViewPercentage', 0) for a in analytics) / len(analytics)
    raw_data += 'Average retention: ' + str(round(avg_retention, 1)) + '%\n'
    
    avg_duration = sum(a.get('averageViewDuration', 0) for a in analytics) / len(analytics)
    raw_data += 'Average view duration: ' + str(round(avg_duration, 1)) + 's\n'
    
    total_subs = sum(a.get('subscribersGained', 0) for a in analytics)
    raw_data += 'Subscribers gained: ' + str(total_subs) + '\n\n'
    
    raw_data += 'VIDEO-WISE RETENTION:\n'
    for a in analytics[:10]:
        vid_id = a.get('video', '')
        matching_video = next((v for v in sorted_videos if v['video_id'] == vid_id), None)
        title = matching_video['title'][:40] if matching_video else vid_id[:10]
        retention = a.get('averageViewPercentage', 0)
        views = a.get('views', 0)
        raw_data += '- "' + title + '": ' + str(views) + ' views, ' + str(round(retention, 1)) + '% retention\n'

if traffic:
    raw_data += '\nTRAFFIC SOURCES:\n'
    for t in traffic[:8]:
        source = t.get('insightTrafficSourceType', 'Unknown')
        views = t.get('views', 0)
        raw_data += '- ' + str(source) + ': ' + str(views) + ' views\n'

# AI Analysis in Hindi
print('Groq se Hindi analysis karwa raha hoon...')

prompt = 'Tu ek YouTube Shorts expert hai jo Hinglish (Hindi + English mix) mein baat karta hai, jaise ek bhai apne dost se baat karta hai.\n\n'
prompt += 'Neeche ek YouTube channel ka pura data hai. Tujhe is channel ka analysis karna hai Hinglish mein.\n\n'
prompt += raw_data + '\n\n'
prompt += 'IMPORTANT RULES:\n'
prompt += '1. Pura response Hinglish mein likhna (Hindi words Roman script mein, technical words English mein)\n'
prompt += '2. Bahut specific rehna, generic advice nahi dena\n'
prompt += '3. Emojis use karna for readability\n'
prompt += '4. Direct "tu" use karna, "aap" nahi\n'
prompt += '5. Under 800 words rakhna\n\n'
prompt += 'Is format mein response dena:\n\n'
prompt += 'BHAI, CHANNEL KA REPORT:\n'
prompt += '[2-3 line summary - channel ki overall situation kya hai]\n\n'
prompt += 'KYA ACHA CHAL RAHA HAI:\n'
prompt += '- [3 specific points jo achhe hain data se]\n\n'
prompt += 'KYA PROBLEM HAI:\n'
prompt += '- [3 specific problems jo data mein dikh rahe hain]\n\n'
prompt += 'FIX KYA KARNA HAI:\n'
prompt += '1. [Specific step 1]\n'
prompt += '2. [Specific step 2]\n'
prompt += '3. [Specific step 3]\n\n'
prompt += 'NEXT VIDEO KAISE BANAYE:\n'
prompt += '- Title idea: [specific title]\n'
prompt += '- Tags: [8-10 specific tags]\n'
prompt += '- Duration: [kitne second]\n'
prompt += '- Hook: [pehle 3 second mein kya dikhana]\n'

ai_analysis = groq_analyze(prompt)

# Build final Hindi report
final_report = 'CHANNEL ANALYSIS REPORT\n'
final_report += '=' * 30 + '\n\n'
final_report += 'Period: Last 28 days\n'
final_report += 'Total videos: ' + str(len(videos_with_stats)) + '\n'
final_report += 'Total views: ' + str(total_views) + '\n'
final_report += 'Total likes: ' + str(total_likes) + '\n\n'

final_report += 'TOP 5 VIDEOS:\n'
for i, v in enumerate(sorted_videos[:5]):
    final_report += str(i + 1) + '. "' + v['title'][:50] + '"\n'
    final_report += '   ' + str(v['views']) + ' views | ' + str(v['likes']) + ' likes\n'

if analytics:
    avg_retention = sum(a.get('averageViewPercentage', 0) for a in analytics) / len(analytics)
    final_report += '\nAverage retention: ' + str(round(avg_retention, 1)) + '%\n'
    
    if traffic:
        final_report += '\nTRAFFIC SOURCES:\n'
        for t in traffic[:5]:
            final_report += '- ' + str(t.get('insightTrafficSourceType', 'Unknown')) + ': ' + str(t.get('views', 0)) + '\n'

final_report += '\n' + '=' * 30 + '\n\n'

if ai_analysis:
    final_report += ai_analysis
else:
    final_report += 'Bhai, AI analysis fail ho gaya. Upar wala raw data dekh le.'

send_telegram(final_report)

print('=== ANALYSIS COMPLETE ===')
