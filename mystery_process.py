import json, os, requests, subprocess, time, re, asyncio
from gtts import gTTS
import edge_tts

GROQ_KEY = os.environ['GROQ_API_KEY']
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))
CATEGORY = os.environ.get('CATEGORY', 'mystery')
VOICE_NAME = os.environ.get('VOICE_NAME', 'en-GB-RyanNeural')
PIXABAY_KEY = os.environ.get('PIXABAY_API_KEY', '')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


def get_audio_duration(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                            path], capture_output=True, text=True)
    try:
        return float(probe.stdout.strip())
    except:
        return 10.0


def groq_call(prompt, max_tokens=2000, temp=0.3, json_mode=False):
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {'Authorization': 'Bearer ' + GROQ_KEY, 'Content-Type': 'application/json'}
    payload = {
        'model': 'openai/gpt-oss-120b',
        'messages': [
            {'role': 'system', 'content': 'You are a helpful assistant. ALWAYS respond with valid JSON only. No markdown, no explanation, just the JSON object.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': temp,
        'max_tokens': max_tokens
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            result = r.json()
            if 'choices' in result:
                content = result['choices'][0]['message']['content']
                if content and len(content.strip()) > 5:
                    return content
                else:
                    print('Groq empty content')
                    time.sleep(3)
            else:
                print('Groq response: ' + str(result)[:200])
                if 'rate limit' in str(result).lower():
                    time.sleep(60)
                else:
                    time.sleep(5)
        except Exception as e:
            print('Groq error: ' + str(e))
            time.sleep(10)
    return None


def parse_json_safe(text):
    if not text:
        return None
    try:
        clean = text.strip()
        if clean.startswith('```'):
            clean = clean.split('```')[1]
            if clean.startswith('json'):
                clean = clean[4:]
        clean = clean.strip()
        start = clean.find('{')
        end = clean.rfind('}')
        if start >= 0 and end > start:
            clean = clean[start:end+1]
        return json.loads(clean)
    except Exception as e:
        print('JSON parse error: ' + str(e))
        return None


def save_to_supabase(chat_id, file_id, title, description, tags, short_number, content_type='mystery', script='', voice_style=''):
    url = SUPABASE_URL + '/rest/v1/pending_shorts'
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': 'Bearer ' + SUPABASE_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    data = {
        'chat_id': chat_id,
        'file_id': file_id,
        'title': title,
        'description': description,
        'tags': tags,
        'status': 'pending',
        'short_number': short_number,
        'upload_status': 'pending',
        'content_type': content_type,
        'script': script,
        'voice_style': voice_style
    }
    try:
        r = requests.post(url, headers=headers, json=data, timeout=30)
        result = r.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('id')
        else:
            print('Supabase save error: ' + str(result)[:200])
    except Exception as e:
        print('Supabase exception: ' + str(e))
    return None


print('MYSTERY SHORTS GENERATOR')
print('Category: ' + CATEGORY)
print('Voice: ' + VOICE_NAME)


print('STEP 1: Generate Mystery Topics')
category_topics = {
    'aliens': 'alien encounter, UFO sighting, area 51, extraterrestrial',
    'ghosts': 'haunted house, ghost sighting, poltergeist, paranormal activity',
    'ships': 'ghost ship, missing ship, bermuda triangle, lost at sea',
    'abandoned': 'abandoned places, ghost town, abandoned hospital, mysterious ruins',
    'cursed': 'cursed object, cursed artifact, cursed painting, cursed doll'
}

topics_prompt = 'Generate ' + str(NUM_SHORTS) + ' mystery story topics.\n'
topics_prompt += 'Category: ' + CATEGORY + '\n'
topics_prompt += 'Keywords: ' + category_topics.get(CATEGORY, 'mystery, unsolved') + '\n'
topics_prompt += 'Each topic must be SPECIFIC (real event/place), UNSOLVED, SHOCKING.\n'
topics_prompt += 'Return JSON: {"topics": [{"topic": "name", "hook": "grabber"}]}'

result = groq_call(topics_prompt, max_tokens=800, temp=0.7, json_mode=True)
topics = []
if result:
    data = parse_json_safe(result)
    if data:
        topics = data.get('topics', [])
        print('Got ' + str(len(topics)) + ' topics')

if not topics:
    topics = [
        {'topic': 'The Mary Celeste Ghost Ship', 'hook': 'A ship found empty in 1872'},
        {'topic': 'The Dyatlov Pass Incident', 'hook': '9 hikers died mysteriously'},
        {'topic': 'The Bermuda Triangle', 'hook': 'Ships and planes vanish here'}
    ][:NUM_SHORTS]


def gen_mystery_script(topic, hook, duration_sec):
    word_count = int(duration_sec * 2.7)
    prompt = 'Write a ' + str(duration_sec) + '-second mystery narration (about ' + str(word_count) + ' words).\n'
    prompt += 'Topic: ' + topic + '\n'
    prompt += 'Hook: ' + hook + '\n'
    prompt += 'Structure: Hook (3s) + Setup (12s) + Mystery (15s) + Twist (10s) + CTA (5s).\n'
    prompt += 'Deep dramatic tone. Short punchy sentences. End with "Follow for more mysteries!".\n'
    prompt += 'Return JSON: {"script": "narration text here", "visual_keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"]}'

    result = groq_call(prompt, max_tokens=1000, temp=0.8, json_mode=True)
    if result:
        data = parse_json_safe(result)
        if data and data.get('script'):
            return data

    return {
        'script': hook + '. ' + topic + ' remains one of history\'s greatest mysteries. Follow for more mysteries!',
        'visual_keywords': ['mystery', 'dark', 'ocean', 'fog', 'shadow']
    }


def gen_yt_metadata(topic, script):
    prompt = 'Generate YouTube Shorts metadata for a mystery short.\n'
    prompt += 'Topic: ' + topic + '\n'
    prompt += 'Script: ' + script[:400] + '\n'
    prompt += 'Rules:\n'
    prompt += '- Title: Specific topic name + end with "#Shorts #Viral #MrBeast #Trending"\n'
    prompt += '- Description: 2 lines about mystery + blank + 15-20 hashtags (include #MrBeast #Shorts #Viral #Trending #YouTubeShorts #Mystery #Unsolved)\n'
    prompt += '- Tags: minimum 15 specific tags\n'
    prompt += 'Return JSON: {"title": "...", "description": "...", "tags": ["tag1", "tag2"]}'

    result = groq_call(prompt, max_tokens=900, temp=0.5, json_mode=True)
    if result:
        parsed = parse_json_safe(result)
        if parsed:
            title = parsed.get('title', topic)
            required = ['#Shorts', '#Viral', '#MrBeast', '#Trending']
            title_hashtags = re.findall(r'#\w+', title)
            for ht in required:
                if ht.lower() not in [t.lower() for t in title_hashtags]:
                    title = title.rstrip() + ' ' + ht

            desc = parsed.get('description', '')
            desc_hashtags = re.findall(r'#\w+', desc)
            if len(desc_hashtags) < 15:
                base = ['#MrBeast', '#Shorts', '#Viral', '#Trending', '#YouTubeShorts',
                        '#ViralClip', '#USA', '#MustWatch', '#Explore', '#ShortsFeed',
                        '#FYP', '#ViralVideo', '#TrendingNow', '#ExploreMore', '#Amazing',
                        '#Mystery', '#Unsolved', '#Unexplained']
                for bh in base:
                    if bh.lower() not in [h.lower() for h in desc_hashtags]:
                        desc += '\n' + bh
                        desc_hashtags.append(bh)
                        if len(desc_hashtags) >= 15:
                            break

            tags = parsed.get('tags', [])
            if len(tags) < 15:
                base_tags = ['mystery', 'unsolved', 'unexplained', 'shorts', 'viral',
                             'mrbeast', 'trending', 'youtube shorts', 'must watch', 'history',
                             'documentary', 'creepy', 'paranormal', 'haunted', 'ghost']
                for bt in base_tags:
                    if bt not in tags and len(tags) < 15:
                        tags.append(bt)

            return {'title': title, 'description': desc, 'tags': tags}

    return {
        'title': topic + ' #Shorts #Viral #MrBeast #Trending',
        'description': topic + ' remains one of history\'s greatest unsolved mysteries!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing #Mystery #Unsolved',
        'tags': ['mystery', 'unsolved', 'unexplained', 'shorts', 'viral', 'mrbeast', 'trending', 'youtube shorts', 'must watch', 'history', 'documentary', 'creepy', 'paranormal', 'haunted', 'ghost']
    }


def download_pixabay_videos(keywords, num_videos=3):
    if not PIXABAY_KEY:
        print('No Pixabay key')
        return []

    videos = []
    for kw in keywords[:num_videos]:
        try:
            url = 'https://pixabay.com/api/videos/'
            params = {'key': PIXABAY_KEY, 'q': kw, 'per_page': 3, 'safesearch': 'true', 'video_type': 'film'}
            r = requests.get(url, params=params, timeout=30)
            data = r.json()
            if 'hits' in data and len(data['hits']) > 0:
                hit = data['hits'][0]
                vid_url = hit['videos']['medium']['url']
                videos.append({'keyword': kw, 'url': vid_url})
                print('Found: ' + kw)
            time.sleep(0.5)
        except Exception as e:
            print('Pixabay error ' + kw + ': ' + str(e))
    return videos


def download_video_file(url, output_path):
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                return True
    except Exception as e:
        print('Download error: ' + str(e))
    return False


def gen_voice(script, output_path):
    try:
        async def _gen():
            communicate = edge_tts.Communicate(script, VOICE_NAME)
            await communicate.save(output_path)
        asyncio.run(_gen())
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print('Edge TTS success')
            return True
    except Exception as e:
        print('Edge TTS failed: ' + str(e))

    try:
        tts = gTTS(text=script, lang='en', slow=False)
        tts.save(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print('gTTS success')
            return True
    except Exception as e:
        print('gTTS failed: ' + str(e))
    return False


def split_script_to_segments(script, num_segments=5):
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    if not sentences:
        return [script]
    segments = []
    per_segment = max(1, len(sentences) // num_segments)
    for i in range(0, len(sentences), per_segment):
        seg = ' '.join(sentences[i:i+per_segment]).strip()
        if seg:
            segments.append(seg)
    while len(segments) < num_segments and segments:
        segments.append(segments[-1])
    return segments[:num_segments]


def ass_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return '%d:%02d:%05.2f' % (hrs, mins, secs)


def wrap_text(text, max_chars=20):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars:
            current = (current + " " + w).strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = lines[-2:]
    return '\\N'.join(lines)


def build_mystery_ass(segments, total_duration):
    lines = []
    lines.append('[Script Info]')
    lines.append('ScriptType: v4.00+')
    lines.append('PlayResX: 720')
    lines.append('PlayResY: 1280')
    lines.append('WrapStyle: 0')
    lines.append('ScaledBorderAndShadow: yes')
    lines.append('')
    lines.append('[V4+ Styles]')
    lines.append('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding')
    lines.append('Style: Caption,Arial,85,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,3,2,40,40,200,1')
    lines.append('')
    lines.append('[Events]')
    lines.append('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text')

    words_per_segment = [len(s.split()) for s in segments]
    total_words = sum(words_per_segment)
    if total_words == 0:
        total_words = 1

    current_time = 0
    for i, seg in enumerate(segments):
        seg_dur = (words_per_segment[i] / total_words) * total_duration
        words = seg.split()
        if words:
            word_dur = seg_dur / len(words)
            growing = []
            for j, w in enumerate(words):
                growing.append(w)
                s = current_time + (j * word_dur)
                e = current_time + ((j + 1) * word_dur)
                if e <= s:
                    e = s + 0.15
                text = wrap_text(' '.join(growing))
                lines.append('Dialogue: 0,%s,%s,Caption,,0,0,0,,%s' % (ass_time(s), ass_time(e), text))
        current_time += seg_dur

    return '\n'.join(lines)


print('STEP 2: Generating script')
first_topic = topics[0] if topics else {'topic': 'The Mary Celeste', 'hook': 'A ship found empty'}

script_data = gen_mystery_script(first_topic['topic'], first_topic['hook'], DURATION)
script = script_data.get('script', '')
visual_keywords = script_data.get('visual_keywords', ['mystery', 'dark', 'ocean'])
print('Script: ' + script[:150])

print('STEP 3: Generating voice')
voice_path = 'voice.mp3'
if not gen_voice(script, voice_path):
    subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-t', str(DURATION), '-q:a', '9', '-acodec', 'libmp3lame', voice_path])

voice_duration = get_audio_duration(voice_path)
print('Voice duration: %0.2f seconds' % voice_duration)

print('STEP 4: Downloading videos')
videos = download_pixabay_videos(visual_keywords, 3)
print('Downloaded ' + str(len(videos)) + ' videos')

video_files = []
for i, v in enumerate(videos):
    path = 'bg_%d.mp4' % i
    if download_video_file(v['url'], path):
        video_files.append(path)
        print('Saved: ' + path)

if not video_files:
    print('No videos - fallback black background')
    subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'color=c=0x000000:s=720x1280:d=' + str(voice_duration + 2) + ':r=30',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', 'bg_fallback.mp4'])
    video_files = ['bg_fallback.mp4']

print('STEP 5: Building captions')
segments = split_script_to_segments(script, 5)
ass_path = 'captions.ass'
with open(ass_path, 'w', encoding='utf-8') as f:
    f.write(build_mystery_ass(segments, voice_duration))

print('Captions ready')
print('STEP 6: Rendering video...')
out_path = 'mystery_short_0.mp4'

cine_filter = ("eq=contrast=1.15:saturation=1.25:brightness=0.02,"
               "unsharp=5:5:0.8:3:3:0.4,"
               "vignette=PI/5")

num_bg = len(video_files)
if num_bg == 1:
    vf = ("[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
          "crop=720:1280,"
          + cine_filter + ","
          "fps=30,setsar=1[vbg];"
          "[vbg]ass=" + ass_path + "[v]")
    subprocess.run([
        'ffmpeg', '-y', '-stream_loop', '-1', '-i', video_files[0],
        '-i', voice_path,
        '-filter_complex', vf,
        '-map', '[v]', '-map', '1:a',
        '-t', str(voice_duration + 0.5),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k', '-shortest',
        out_path
    ])
else:
    clip_paths = []
    per_clip = (voice_duration + 0.5) / num_bg
    for i, vf_path in enumerate(video_files):
        clip = 'clip_%d.mp4' % i
        cf = ("scale=720:1280:force_original_aspect_ratio=increase,"
              "crop=720:1280," + cine_filter + ",fps=30,setsar=1")
        subprocess.run([
            'ffmpeg', '-y', '-stream_loop', '-1', '-i', vf_path,
            '-t', str(per_clip), '-vf', cf,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '24', '-an', clip
        ], capture_output=True)
        if os.path.exists(clip):
            clip_paths.append(clip)

    if clip_paths:
        with open('concat_list.txt', 'w') as f:
            for cp in clip_paths:
                f.write("file '" + os.path.abspath(cp) + "'\n")
        subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat_list.txt',
                        '-c', 'copy', 'bg_concat.mp4'], capture_output=True)
        vf = "[0:v]ass=" + ass_path + "[v]"
        subprocess.run([
            'ffmpeg', '-y', '-i', 'bg_concat.mp4', '-i', voice_path,
            '-filter_complex', vf,
            '-map', '[v]', '-map', '1:a',
            '-t', str(voice_duration + 0.5),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
            '-c:a', 'aac', '-b:a', '128k', '-shortest',
            out_path
        ])
        for cp in clip_paths:
            try: os.remove(cp)
            except: pass
        try:
            os.remove('bg_concat.mp4')
            os.remove('concat_list.txt')
        except: pass

print('Rendered: ' + out_path)

print('STEP 7: Metadata')
meta = gen_yt_metadata(first_topic['topic'], script)
title = meta.get('title', first_topic['topic'])
description = meta.get('description', '')
tags = ', '.join(meta.get('tags', []))
print('Title: ' + title)

print('STEP 8: Sending to Telegram')
tg_response = subprocess.run([
    'curl', '-s', '-X', 'POST',
    'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
    '-F', 'chat_id=' + CHAT_ID,
    '-F', 'video=@' + out_path,
    '-F', 'caption=Mystery Short 1/' + str(NUM_SHORTS) + ' - ' + first_topic['topic']
], capture_output=True, text=True)

file_id = None
try:
    tg_json = json.loads(tg_response.stdout)
    if tg_json.get('ok'):
        file_id = tg_json['result']['video']['file_id']
        print('File ID: ' + file_id)
except Exception as e:
    print('Telegram error: ' + str(e))

if file_id:
    row_id = save_to_supabase(CHAT_ID, file_id, title, description, tags, 1,
                              content_type='mystery', script=script, voice_style=VOICE_NAME)
    print('Row ID: ' + str(row_id))

    if row_id:
        keyboard = json.dumps({
            'inline_keyboard': [
                [{'text': '✅ Upload', 'callback_data': 'approve_' + str(row_id)},
                 {'text': '📅 Schedule', 'callback_data': 'schedule_' + str(row_id)}],
                [{'text': '✏️ Custom', 'callback_data': 'custom_' + str(row_id)},
                 {'text': '❌ Skip', 'callback_data': 'skip_' + str(row_id)}]
            ]
        })
        approval_text = '📝 Mystery Short 1/' + str(NUM_SHORTS) + '\n\n'
        approval_text += '🎬 Topic: ' + first_topic['topic'] + '\n\n'
        approval_text += '📄 Title: ' + title + '\n\n'
        approval_text += '📝 Description: ' + description[:400] + '...\n\n'
        approval_text += '🏷️ Tags: ' + tags[:300] + '...\n\n'
        approval_text += 'Kya karna hai?'
        subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
            '--data-urlencode', 'chat_id=' + CHAT_ID,
            '--data-urlencode', 'text=' + approval_text,
            '--data-urlencode', 'reply_markup=' + keyboard
        ], capture_output=True, text=True)

for idx in range(1, NUM_SHORTS):
    if idx >= len(topics):
        break
    try:
        topic_data = topics[idx]
        print('Short ' + str(idx + 1) + ': ' + topic_data['topic'])

        script_data = gen_mystery_script(topic_data['topic'], topic_data['hook'], DURATION)
        script = script_data.get('script', '')
        visual_keywords = script_data.get('visual_keywords', ['mystery', 'dark'])

        voice_path = 'voice_%d.mp3' % idx
        if not gen_voice(script, voice_path):
            subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                            '-t', str(DURATION), '-q:a', '9', '-acodec', 'libmp3lame', voice_path])
        voice_duration = get_audio_duration(voice_path)

        videos = download_pixabay_videos(visual_keywords, 3)
        video_files = []
        for vi, v in enumerate(videos):
            path = 'bg_%d_%d.mp4' % (idx, vi)
            if download_video_file(v['url'], path):
                video_files.append(path)

        if not video_files:
            subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'color=c=0x000000:s=720x1280:d=' + str(voice_duration + 2) + ':r=30',
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', 'bg_fb_%d.mp4' % idx])
            video_files = ['bg_fb_%d.mp4' % idx]

        segments = split_script_to_segments(script, 5)
        ass_path = 'captions_%d.ass' % idx
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(build_mystery_ass(segments, voice_duration))

        out_path = 'mystery_short_%d.mp4' % idx

        if len(video_files) == 1:
            vf = ("[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
                  "crop=720:1280," + cine_filter + ",fps=30,setsar=1[vbg];"
                  "[vbg]ass=" + ass_path + "[v]")
            subprocess.run([
                'ffmpeg', '-y', '-stream_loop', '-1', '-i', video_files[0],
                '-i', voice_path, '-filter_complex', vf,
                '-map', '[v]', '-map', '1:a',
                '-t', str(voice_duration + 0.5),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
                '-c:a', 'aac', '-b:a', '128k', '-shortest', out_path
            ])
        else:
            clip_paths = []
            per_clip = (voice_duration + 0.5) / len(video_files)
            for ci, vfp in enumerate(video_files):
                clip = 'clip_%d_%d.mp4' % (idx, ci)
                cf = ("scale=720:1280:force_original_aspect_ratio=increase,"
                      "crop=720:1280," + cine_filter + ",fps=30,setsar=1")
                subprocess.run(['ffmpeg', '-y', '-stream_loop', '-1', '-i', vfp,
                                '-t', str(per_clip), '-vf', cf,
                                '-c:v', 'libx264', '-preset', 'fast', '-crf', '24', '-an', clip],
                               capture_output=True)
                if os.path.exists(clip):
                    clip_paths.append(clip)
            if clip_paths:
                with open('cc_%d.txt' % idx, 'w') as f:
                    for cp in clip_paths:
                        f.write("file '" + os.path.abspath(cp) + "'\n")
                subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'cc_%d.txt' % idx,
                                '-c', 'copy', 'bgc_%d.mp4' % idx], capture_output=True)
                vf = "[0:v]ass=" + ass_path + "[v]"
                subprocess.run(['ffmpeg', '-y', '-i', 'bgc_%d.mp4' % idx, '-i', voice_path,
                                '-filter_complex', vf,
                                '-map', '[v]', '-map', '1:a',
                                '-t', str(voice_duration + 0.5),
                                '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
                                '-c:a', 'aac', '-b:a', '128k', '-shortest', out_path])
                for cp in clip_paths:
                    try: os.remove(cp)
                    except: pass
                try:
                    os.remove('bgc_%d.mp4' % idx)
                    os.remove('cc_%d.txt' % idx)
                except: pass

        meta = gen_yt_metadata(topic_data['topic'], script)
        title = meta.get('title', topic_data['topic'])
        description = meta.get('description', '')
        tags = ', '.join(meta.get('tags', []))

        tg_response = subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
            '-F', 'chat_id=' + CHAT_ID,
            '-F', 'video=@' + out_path,
            '-F', 'caption=Mystery Short ' + str(idx + 1) + '/' + str(NUM_SHORTS) + ' - ' + topic_data['topic']
        ], capture_output=True, text=True)

        file_id = None
        try:
            tg_json = json.loads(tg_response.stdout)
            if tg_json.get('ok'):
                file_id = tg_json['result']['video']['file_id']
        except: pass

        if file_id:
            row_id = save_to_supabase(CHAT_ID, file_id, title, description, tags, idx + 1,
                                      content_type='mystery', script=script, voice_style=VOICE_NAME)
            if row_id:
                keyboard = json.dumps({
                    'inline_keyboard': [
                        [{'text': '✅ Upload', 'callback_data': 'approve_' + str(row_id)},
                         {'text': '📅 Schedule', 'callback_data': 'schedule_' + str(row_id)}],
                        [{'text': '✏️ Custom', 'callback_data': 'custom_' + str(row_id)},
                         {'text': '❌ Skip', 'callback_data': 'skip_' + str(row_id)}]
                    ]
                })
                approval_text = '📝 Mystery Short ' + str(idx + 1) + '/' + str(NUM_SHORTS) + '\n\n'
                approval_text += '🎬 Topic: ' + topic_data['topic'] + '\n\n'
                approval_text += '📄 Title: ' + title + '\n\n'
                approval_text += '📝 Description: ' + description[:400] + '...\n\n'
                approval_text += '🏷️ Tags: ' + tags[:300] + '...\n\n'
                approval_text += 'Kya karna hai?'
                subprocess.run(['curl', '-s', '-X', 'POST',
                                'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
                                '--data-urlencode', 'chat_id=' + CHAT_ID,
                                '--data-urlencode', 'text=' + approval_text,
                                '--data-urlencode', 'reply_markup=' + keyboard], capture_output=True, text=True)

        time.sleep(2)
        try:
            os.remove(voice_path)
            os.remove(ass_path)
        except: pass
        for vf_path in video_files:
            try: os.remove(vf_path)
            except: pass
    except Exception as e:
        print('Short ' + str(idx + 1) + ' failed: ' + str(e))
        continue

print('All mystery shorts generated!')
