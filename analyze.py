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
        'max_tokens': 1500
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
print('=== YOUTUBE CHANNEL ANALYSIS STARTED ===')

access_token = get_access_token()
if not access_token:
    send_telegram('Channel analysis failed: access token error')
    exit(1)

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d')

print('Fetching recent videos...')
videos = get_channel_videos(access_token, 20)
if not videos:
    send_telegram('No videos found on channel')
    exit(1)

video_ids = [v['video_id'] for v in videos]
print('Fetching stats for ' + str(len(video_ids)) + ' videos...')
videos_with_stats = get_video_stats(access_token, video_ids)

print('Fetching analytics data...')
analytics = get_analytics_data(access_token, start_date, end_date)

print('Fetching traffic sources...')
traffic = get_traffic_sources(access_token, start_date, end_date)

# Build report
report = 'YOUTUBE CHANNEL ANALYSIS\n'
report += '=' * 40 + '\n\n'
report += 'Period: Last 28 days\n'
report += 'Total videos analyzed: ' + str(len(videos_with_stats)) + '\n\n'

total_views = sum(v['views'] for v in videos_with_stats)
total_likes = sum(v['likes'] for v in videos_with_stats)
report += 'Total views: ' + str(total_views) + '\n'
report += 'Total likes: ' + str(total_likes) + '\n\n'

# Top videos
sorted_videos = sorted(videos_with_stats, key=lambda x: x['views'], reverse=True)
report += 'TOP 5 VIDEOS:\n'
for i, v in enumerate(sorted_videos[:5]):
    report += str(i + 1) + '. "' + v['title'][:60] + '"\n'
    report += '   Views: ' + str(v['views']) + ' | Likes: ' + str(v['likes']) + '\n'

report += '\nBOTTOM 5 VIDEOS:\n'
for i, v in enumerate(sorted_videos[-5:]):
    report += str(i + 1) + '. "' + v['title'][:60] + '"\n'
    report += '   Views: ' + str(v['views']) + ' | Likes: ' + str(v['likes']) + '\n'

# Analytics
if analytics:
    report += '\nANALYTICS (Last 28 days):\n'
    total_analytics_views = sum(a.get('views', 0) for a in analytics)
    report += 'Total views: ' + str(total_analytics_views) + '\n'
    
    if analytics:
        avg_retention = sum(a.get('averageViewPercentage', 0) for a in analytics) / len(analytics)
        report += 'Average retention: ' + str(round(avg_retention, 1)) + '%\n'
        
        avg_duration = sum(a.get('averageViewDuration', 0) for a in analytics) / len(analytics)
        report += 'Average view duration: ' + str(round(avg_duration, 1)) + 's\n'
        
        total_subs = sum(a.get('subscribersGained', 0) for a in analytics)
        report += 'Subscribers gained: ' + str(total_subs) + '\n'

# Traffic
if traffic:
    report += '\nTRAFFIC SOURCES:\n'
    for t in traffic[:5]:
        report += '- ' + str(t.get('insightTrafficSourceType', 'Unknown')) + ': ' + str(t.get('views', 0)) + ' views\n'

# AI Analysis
print('Running Groq analysis...')
prompt = 'You are a YouTube Shorts analytics expert. Analyze this channel data and give SPECIFIC, ACTIONABLE advice.\n\n'
prompt += 'CHANNEL DATA (last 28 days):\n'
prompt += report + '\n\n'
prompt += 'Videos data:\n'
for v in sorted_videos[:10]:
    prompt += '- "' + v['title'][:50] + '": ' + str(v['views']) + ' views, ' + str(v['likes']) + ' likes\n'
prompt += '\nTraffic data:\n'
for t in traffic[:5]:
    prompt += '- ' + str(t.get('insightTrafficSourceType', 'Unknown')) + ': ' + str(t.get('views', 0)) + '\n'

prompt += '\n\nProvide analysis in this EXACT format (keep it SHORT and SPECIFIC):\n\n'
prompt += 'STRENGTHS (What is working):\n'
prompt += '- [3 specific things that are good]\n\n'
prompt += 'WEAKNESSES (What needs fixing):\n'
prompt += '- [3 specific problems found in the data]\n\n'
prompt += 'ACTION PLAN (Next 5 videos):\n'
prompt += '1. [Specific title/format suggestion]\n'
prompt += '2. [Specific title/format suggestion]\n'
prompt += '3. [Specific title/format suggestion]\n\n'
prompt += 'Tags to use: [8-10 specific tags based on what works]\n\n'
prompt += 'Keep total response under 500 words. Be VERY specific, not generic.'

ai_analysis = groq_analyze(prompt)

# Send final report
final_report = 'CHANNEL ANALYSIS REPORT\n'
final_report += '=' * 30 + '\n\n'
final_report += report[:1500] + '\n\n'

if ai_analysis:
    final_report += 'AI ANALYSIS:\n'
    final_report += '=' * 30 + '\n\n'
    final_report += ai_analysis
else:
    final_report += 'AI analysis failed. Check raw data above.'

send_telegram(final_report)

print('=== ANALYSIS COMPLETE ===')
