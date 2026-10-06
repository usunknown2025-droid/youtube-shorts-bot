import json, os, requests, subprocess, time, re
from faster_whisper import WhisperModel
from gtts import gTTS

GROQ_KEY = os.environ['GROQ_API_KEY']
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))

YT_CLIENT_ID = os.environ.get('YT_CLIENT_ID', '').strip()
YT_CLIENT_SECRET = os.environ.get('YT_CLIENT_SECRET', '').strip()
YT_REFRESH_TOKEN = os.environ.get('YT_REFRESH_TOKEN', '').strip()


def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return '%02d:%02d:%02d,%03d' % (hrs, mins, secs, ms)


def contains_non_english(text):
    for ch in text:
        if ord(ch) > 0x0FFF:
            return True
    return False


def groq_call(prompt, max_tokens=2000, temp=0.3, json_mode=False):
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {'Authorization': 'Bearer ' + GROQ_KEY, 'Content-Type': 'application/json'}
    payload = {
        'model': 'openai/gpt-oss-20b',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temp,
        'max_tokens': max_tokens
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            result = r.json()
            if 'choices' in result:
                return result['choices'][0]['message']['content']
            else:
                print('Groq response: ' + str(result)[:200])
                time.sleep(5)
        except Exception as e:
            print('Groq error: ' + str(e))
            time.sleep(5)
    return None


# ---------- YouTube Upload Functions ----------
def get_youtube_access_token():
    url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': YT_CLIENT_ID,
        'client_secret': YT_CLIENT_SECRET,
        'refresh_token': YT_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    print('YT_CLIENT_ID starts: ' + YT_CLIENT_ID[:20] if YT_CLIENT_ID else 'YT_CLIENT_ID empty')
    print('YT_CLIENT_SECRET starts: ' + YT_CLIENT_SECRET[:10] if YT_CLIENT_SECRET else 'YT_CLIENT_SECRET empty')
    try:
        r = requests.post(url, data=data, timeout=30)
        result = r.json()
        if 'access_token' in result:
            print('YouTube: Access token obtained')
            return result['access_token']
        else:
            print('Token error: ' + str(result))
    except Exception as e:
        print('Token exception: ' + str(e))
    return None


def generate_yt_metadata(commentary):
    prompt = 'You are a YouTube Shorts SEO expert. Generate metadata for this Short.\n\n'
    prompt += 'Context: ' + commentary[:500] + '\n\n'
    prompt += 'Return JSON with keys:\n'
    prompt += '- "title": catchy Shorts title (max 90 chars, English, 1-2 emojis)\n'
    prompt += '- "description": 2-3 line English description with hashtags\n'
    prompt += '- "tags": array of 10-15 English tags\n\n'
    prompt += 'JSON only.'

    result = groq_call(prompt, max_tokens=500, temp=0.7, json_mode=True)
    if result:
        try:
            return json.loads(result)
        except Exception as e:
            print('Metadata parse error: ' + str(e))

    return {
        'title': 'Viral Moment You Must See! 🔥',
        'description': 'Watch this amazing viral moment! Subscribe for more.\n\n#Shorts #Viral #Trending',
        'tags': ['shorts', 'viral', 'trending', 'amazing', 'usa']
    }


def upload_to_youtube(video_path, title, description, tags):
    access_token = get_youtube_access_token()
    if not access_token:
        print('YouTube: No access token')
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

    try:
        with open(video_path, 'rb') as f:
            files = {
                'metadata': ('metadata.json', json.dumps(metadata), 'application/json'),
                'video': (os.path.basename(video_path), f, 'video/mp4')
            }
            r = requests.post(url, headers=headers, files=files, timeout=300)
        result = r.json()
        if 'id' in result:
            print('YouTube upload success: https://youtu.be/' + result['id'])
            return result['id']
        else:
            print('YouTube upload error: ' + str(result)[:500])
    except Exception as e:
        print('YouTube exception: ' + str(e))
    return None


# ---------- STEP 1: Transcribe ----------
print('\n=== STEP 1: Whisper Transcription ===')
model = WhisperModel('tiny', device='cpu', compute_type='int8')
segments, _ = model.transcribe('audio.wav', task='translate', word_timestamps=True)
transcript_lines = []
seg_data = []
total_words = 0
for s in segments:
    transcript_lines.append('%0.1f-%0.1f: %s' % (s.start, s.end, s.text))
    seg_words = []
    if s.words:
        for w in s.words:
            seg_words.append({'start': w.start, 'end': w.end, 'word': w.word})
            total_words += 1
    seg_data.append({'start': s.start, 'end': s.end, 'text': s.text.strip(), 'words': seg_words})

full_transcript = '\n'.join(transcript_lines)
print('Transcript ready with ' + str(total_words) + ' words')


# ---------- STEP 2: Find viral moments (CHUNKED) ----------
print('\n=== STEP 2: Find Viral Moments (chunked) ===')

# Split transcript into chunks of ~3000 chars
lines = transcript_lines
chunk_size = 3000
chunks = []
current = ''
for line in lines:
    if len(current) + len(line) > chunk_size:
        if current:
            chunks.append(current)
        current = line + '\n'
    else:
        current += line + '\n'
if current:
    chunks.append(current)

print('Split transcript into ' + str(len(chunks)) + ' chunks')

all_moments = []
per_chunk = max(1, (NUM_SHORTS + len(chunks) - 1) // len(chunks))

for i, chunk in enumerate(chunks):
    prompt = 'Find ' + str(per_chunk) + ' most viral/interesting moments in this transcript chunk.\n'
    prompt += 'Each moment should be about ' + str(DURATION) + ' seconds long.\n\n'
    prompt += 'Return JSON: {"moments": [{"start": <sec>, "end": <sec>, "reason": "<why>"}]}\n\n'
    prompt += 'Transcript chunk:\n' + chunk

    result = groq_call(prompt, max_tokens=1500, temp=0.3, json_mode=True)
    if result:
        try:
            data = json.loads(result)
            ms = data.get('moments', [])
            print('Chunk ' + str(i+1) + ': got ' + str(len(ms)) + ' moments')
            all_moments.extend(ms)
        except Exception as e:
            print('Chunk ' + str(i+1) + ' parse error: ' + str(e))
    time.sleep(10)

# Remove overlapping moments and keep only NUM_SHORTS
all_moments.sort(key=lambda x: x.get('start', 0))
filtered = []
for m in all_moments:
    overlap = False
    for f in filtered:
        if not (m['end'] <= f['start'] or m['start'] >= f['end']):
            overlap = True
            break
    if not overlap:
        filtered.append(m)
    if len(filtered) >= NUM_SHORTS:
        break

moments = filtered[:NUM_SHORTS]

if not moments:
    print('Fallback used')
    moments = [{'start': 0, 'end': DURATION, 'reason': 'fallback'}]

print('Final: Got ' + str(len(moments)) + ' moments')


# ---------- STEP 3: Commentary ----------
def gen_commentary(moment_text):
    prompt = 'Write a short, engaging ENGLISH commentary (max 40 words) for this video segment.\n'
    prompt += 'PURE ENGLISH only. No Hindi, no other scripts.\n'
    prompt += 'Just the commentary, no labels.\n\n'
    prompt += 'Segment: ' + moment_text[:1000]
    for attempt in range(3):
        result = groq_call(prompt, max_tokens=150, temp=0.7)
        if result:
            t = result.strip()
            if not contains_non_english(t):
                return t
    return 'Check out this amazing moment!'


# ---------- STEP 4: TTS ----------
def gen_tts(text, path):
    for attempt in range(3):
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(path)
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                return True
        except Exception as e:
            print('TTS error: ' + str(e))
            time.sleep(3)
    return False


# ---------- STEP 5: SRT ----------
def build_srt(start, end, moment_segs):
    srt_lines = []
    idx = 1
    for seg in moment_segs:
        words = seg.get('words', [])
        if not words:
            continue
        growing = []
        for i, w in enumerate(words):
            growing.append(w['word'].strip())
            s = max(w['start'] - start, 0)
            if i + 1 < len(words):
                e = words[i + 1]['start'] - start
            else:
                e = w['end'] - start
            if e <= s:
                e = s + 0.3
            text = ' '.join(growing)
            srt_lines.append(str(idx) + '\n' + format_time(s) + ' --> ' + format_time(e) + '\n' + text + '\n')
            idx += 1
    return '\n'.join(srt_lines)


# ---------- STEP 6: Process each moment ----------
for idx, moment in enumerate(moments):
    print('\n========== SHORT ' + str(idx + 1) + '/' + str(len(moments)) + ' ==========')
    start = float(moment['start'])
    end = float(moment['end'])
    duration = end - start

    moment_segs = []
    for seg in seg_data:
        if seg['end'] < start or seg['start'] > end:
            continue
        new_seg = {
            'start': max(seg['start'], start) - start,
            'end': min(seg['end'], end) - start,
            'text': seg['text'],
            'words': []
        }
        for w in seg.get('words', []):
            if w['end'] < start or w['start'] > end:
                continue
            new_seg['words'].append({
                'start': max(w['start'], start) - start,
                'end': min(w['end'], end) - start,
                'word': w['word']
            })
        if new_seg['end'] > new_seg['start']:
            moment_segs.append(new_seg)

    if not moment_segs:
        continue

    moment_text = ' '.join([s['text'] for s in moment_segs])

    print('Generating commentary...')
    commentary = gen_commentary(moment_text)
    commentary = re.sub(r'["\'\n\r]', ' ', commentary).strip()[:300]
    print('Commentary: ' + commentary)

    tts_path = 'tts_%d.mp3' % idx
    if not gen_tts(commentary, tts_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', '30', '-q:a', '9', '-acodec', 'libmp3lame', tts_path])

    srt_path = 'subs_%d.srt' % idx
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(build_srt(0, duration, moment_segs))

    out_path = 'shorts_%d.mp4' % idx
    vf = "[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,subtitles=" + srt_path + ":force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=50'[v];[0:a]volume=0.2[bg];[1:a]volume=1.0[ai];[bg][ai]amix=inputs=2:duration=first[aout]"

    print('Rendering Short...')
    subprocess.run([
        'ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
        '-i', 'video.mp4', '-i', tts_path,
        '-filter_complex', vf,
        '-map', '[v]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
        '-c:a', 'aac', '-b:a', '128k',
        out_path
    ])

    print('Sending to Telegram...')
    subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
        '-F', 'chat_id=' + CHAT_ID,
        '-F', 'video=@' + out_path,
        '-F', 'caption=Short ' + str(idx + 1) + '/' + str(len(moments))
    ])
    time.sleep(2)

    print('Generating YouTube metadata...')
    meta = generate_yt_metadata(commentary)
    print('Title: ' + meta.get('title', ''))

    print('Uploading to YouTube...')
    yt_id = upload_to_youtube(
        out_path,
        meta.get('title', 'Viral Short'),
        meta.get('description', ''),
        meta.get('tags', [])
    )

    if yt_id:
        subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
            '-d', 'chat_id=' + CHAT_ID,
            '-d', 'text=YouTube: https://youtu.be/' + yt_id
        ])
    else:
        subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
            '-d', 'chat_id=' + CHAT_ID,
            '-d', 'text=YouTube upload failed for Short ' + str(idx + 1)
        ])

    try:
        os.remove(tts_path)
        os.remove(srt_path)
    except:
        pass

print('\nAll done!')
