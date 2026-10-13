import json, os, requests, subprocess, time, re, asyncio
from gtts import gTTS
import edge_tts

GROQ_KEY = os.environ['GROQ_API_KEY']
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))
CATEGORY = os.environ.get('CATEGORY', 'mystery')
VOICE_NAME = os.environ.get('VOICE_NAME', 'en-US-ChristopherNeural')
PIXABAY_KEY = os.environ.get('PIXABAY_API_KEY', '')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


def contains_non_english(text):
    for ch in text:
        if ord(ch) > 0x0FFF:
            return True
    return False


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
        'messages': [{'role': 'user', 'content': prompt}],
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
                return result['choices'][0]['message']['content']
            else:
                print('Groq response: ' + str(result)[:300])
                if 'rate limit' in str(result).lower() or 'rate_limit' in str(result).lower():
                    time.sleep(60)
                else:
                    time.sleep(5)
        except Exception as e:
            print('Groq error: ' + str(e))
            time.sleep(10)
    return None


def save_to_supabase(chat_id, file_id, title, description, tags, short_number, thumbnail_urls='', content_type='mystery', script='', voice_style=''):
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
        'thumbnail_urls': thumbnail_urls,
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
            print('Supabase save error: ' + str(result)[:300])
    except Exception as e:
        print('Supabase exception: ' + str(e))
    return None


print('MYSTERY SHORTS GENERATOR')
print('Category: ' + CATEGORY)
print('Voice: ' + VOICE_NAME)
print('Duration: ' + str(DURATION) + 's')
print('Num shorts: ' + str(NUM_SHORTS))


print('STEP 1: Generate Mystery Topics')
category_topics = {
    'aliens': ['alien encounter', 'UFO sighting', 'area 51', 'extraterrestrial'],
    'ghosts': ['haunted house', 'ghost sighting', 'poltergeist', 'paranormal activity'],
    'ships': ['ghost ship', 'missing ship', 'bermuda triangle', 'lost at sea'],
    'abandoned': ['abandoned places', 'ghost town', 'abandoned hospital', 'mysterious ruins'],
    'cursed': ['cursed object', 'cursed artifact', 'cursed painting', 'cursed doll']
}

topics_prompt = 'Generate ' + str(NUM_SHORTS) + ' DIFFERENT mystery story topics for a YouTube Shorts channel.\n\n'
topics_prompt += 'Category: ' + CATEGORY + '\n'
topics_prompt += 'Related keywords: ' + ', '.join(category_topics.get(CATEGORY, ['mystery', 'unsolved', 'unexplained'])) + '\n\n'
topics_prompt += 'REQUIREMENTS:\n'
topics_prompt += '1. Each topic must be SPECIFIC (a real event, place, or object)\n'
topics_prompt += '2. Each topic must be UNSOLVED or MYSTERIOUS\n'
topics_prompt += '3. Each topic must have a SHOCKING angle\n'
topics_prompt += '4. NO overlapping topics\n'
topics_prompt += '5. Topics should be TRUE events (not fiction)\n\n'
topics_prompt += 'Return ONLY valid JSON:\n'
topics_prompt += '{"topics": [{"topic": "specific topic name", "hook": "one-line attention grabber"}]}'

result = groq_call(topics_prompt, max_tokens=800, temp=0.7, json_mode=True)

topics = []
if result:
    try:
        clean = result.strip()
        if clean.startswith('```'):
            clean = clean.split('```')[1]
            if clean.startswith('json'):
                clean = clean[4:]
        clean = clean.strip()
        data = json.loads(clean)
        topics = data.get('topics', [])
        print('Got ' + str(len(topics)) + ' topics')
    except Exception as e:
        print('Topics parse error: ' + str(e))

if not topics:
    topics = [
        {'topic': 'The Mary Celeste Ghost Ship', 'hook': 'A ship found empty in 1872'},
        {'topic': 'The Dyatlov Pass Incident', 'hook': '9 hikers died mysteriously'},
        {'topic': 'The Bermuda Triangle', 'hook': 'Ships and planes vanish here'}
    ][:NUM_SHORTS]


def gen_mystery_script(topic, hook, duration_sec):
    word_count = int(duration_sec * 2.7)
    prompt = 'Write a YouTube Shorts mystery narration script.\n\n'
    prompt += 'TOPIC: ' + topic + '\n'
    prompt += 'HOOK: ' + hook + '\n'
    prompt += 'TARGET DURATION: ' + str(duration_sec) + ' seconds (about ' + str(word_count) + ' words)\n\n'
    prompt += 'STRUCTURE (STRICT):\n'
    prompt += '1. HOOK (3 seconds): Shocking opening line that grabs attention immediately\n'
    prompt += '2. SETUP (12 seconds): When and where it happened, who was involved\n'
    prompt += '3. MYSTERY (15 seconds): What exactly is unexplained\n'
    prompt += '4. TWIST (10 seconds): Competing theories or strange detail\n'
    prompt += '5. CTA (5 seconds): "Follow for more mysteries!" or similar\n\n'
    prompt += 'RULES:\n'
    prompt += '1. PURE ENGLISH only\n'
    prompt += '2. Deep, dramatic, mysterious tone\n'
    prompt += '3. NO fluff - every word matters\n'
    prompt += '4. NO hashtags in the script\n'
    prompt += '5. NO stage directions - just the words to be spoken\n'
    prompt += '6. Write in short punchy sentences\n\n'
    prompt += 'Return ONLY valid JSON:\n'
    prompt += '{"script": "full narration here", "visual_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]}'
    
    result = groq_call(prompt, max_tokens=1000, temp=0.8, json_mode=True)
    if result:
        try:
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            clean = clean.strip()
            data = json.loads(clean)
            return data
        except Exception as e:
            print('Script parse error: ' + str(e))
    
    return {
        'script': hook + '. ' + topic + ' remains one of history\'s greatest mysteries. Follow for more mysteries!',
        'visual_keywords': ['mystery', 'dark', 'ocean', 'fog', 'shadow']
    }


def gen_yt_metadata(topic, script):
    prompt = 'Generate YouTube Shorts metadata for a mystery short.\n\n'
    prompt += 'TOPIC: ' + topic + '\n'
    prompt += 'SCRIPT: ' + script[:600] + '\n\n'
    prompt += 'STRICT RULES:\n\n'
    prompt += 'TITLE:\n'
    prompt += '- Must start with the SPECIFIC mystery topic name\n'
    prompt += '- Must end with EXACTLY: #Shorts #Viral #MrBeast #Trending\n'
    prompt += '- Under 100 chars total\n'
    prompt += '- Example: "The Mary Celeste Ghost Ship Mystery #Shorts #Viral #MrBeast #Trending"\n\n'
    prompt += 'DESCRIPTION:\n'
    prompt += '- Line 1: Specific sentence about the mystery\n'
    prompt += '- Line 2: What makes it unexplained\n'
    prompt += '- Line 3: CTA "Watch till the end!"\n'
    prompt += '- Then blank line\n'
    prompt += '- Then 15-20 hashtags\n'
    prompt += '- Include: #MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing\n'
    prompt += '- PLUS 3-5 mystery-specific tags like #Mystery #Unsolved #GhostShip\n\n'
    prompt += 'TAGS:\n'
    prompt += '- Minimum 15 tags\n'
    prompt += '- Specific to the mystery content\n\n'
    prompt += 'Return ONLY valid JSON:\n'
    prompt += '{"title": "...", "description": "...", "tags": ["tag1", "tag2"]}'
    
    result = groq_call(prompt, max_tokens=900, temp=0.5, json_mode=True)
    if result:
        try:
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            clean = clean.strip()
            parsed = json.loads(clean)
            
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
            if len(tags) < 12:
                base_tags = ['mystery', 'unsolved', 'unexplained', 'shorts', 'viral',
                             'mrbeast', 'trending', 'youtube shorts', 'must watch']
                for bt in base_tags:
                    if bt not in tags:
                        tags.append(bt)
            
            return {'title': title, 'description': desc, 'tags': tags}
        except Exception as e:
            print('Metadata parse error: ' + str(e))
    
    return {
        'title': topic + ' #Shorts #Viral #MrBeast #Trending',
        'description': topic + ' remains one of history\'s greatest unsolved mysteries!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing #Mystery #Unsolved',
        'tags': ['mystery', 'unsolved', 'unexplained', 'shorts', 'viral', 'mrbeast', 'trending', 'youtube shorts', 'must watch', 'history', 'documentary', 'creepy']
    }


def download_pixabay_videos(keywords, num_videos=5):
    if not PIXABAY_KEY:
        print('No Pixabay key - skipping video download')
        return []
    
    videos = []
    for kw in keywords[:num_videos]:
        try:
            url = 'https://pixabay.com/api/videos/'
            params = {
                'key': PIXABAY_KEY,
                'q': kw,
                'per_page': 5,
                'safesearch': 'true',
                'video_type': 'film'
            }
            r = requests.get(url, params=params, timeout=30)
            data = r.json()
            
            if 'hits' in data and len(data['hits']) > 0:
                for hit in data['hits'][:2]:
                    vid_url = hit['videos']['medium']['url']
                    videos.append({'keyword': kw, 'url': vid_url})
                print('Found videos for: ' + kw)
            time.sleep(0.5)
        except Exception as e:
            print('Pixabay error for ' + kw + ': ' + str(e))
    
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
    async def _gen():
        communicate = edge_tts.Communicate(script, VOICE_NAME)
        await communicate.save(output_path)
    
    try:
        asyncio.run(_gen())
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception as e:
        print('Edge TTS error: ' + str(e))
    
    try:
        tts = gTTS(text=script, lang='en', slow=False)
        tts.save(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception as e:
        print('gTTS fallback error: ' + str(e))
    
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


print('STEP 2: Generating script for first topic')
first_topic = topics[0] if topics else {'topic': 'The Mary Celeste', 'hook': 'A ship found empty'}

script_data = gen_mystery_script(first_topic['topic'], first_topic['hook'], DURATION)
script = script_data.get('script', '')
visual_keywords = script_data.get('visual_keywords', ['mystery', 'dark', 'ocean'])

print('Script generated: ' + script[:150])
print('Visual keywords: ' + ', '.join(visual_keywords))

print('STEP 3: Generating voice')
voice_path = 'voice.mp3'
if not gen_voice(script, voice_path):
    print('Voice generation failed')
    subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-t', str(DURATION), '-q:a', '9', '-acodec', 'libmp3lame', voice_path])

voice_duration = get_audio_duration(voice_path)
print('Voice duration: %0.2f seconds' % voice_duration)

print('STEP 4: Downloading background videos')
videos = download_pixabay_videos(visual_keywords, len(visual_keywords))
print('Downloaded ' + str(len(videos)) + ' videos')

video_files = []
for i, v in enumerate(videos):
    path = 'bg_%d.mp4' % i
    if download_video_file(v['url'], path):
        video_files.append(path)
        print('Saved: ' + path)

if not video_files:
    print('No videos downloaded - using fallback background')
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

num_bg = len(video_files)
if num_bg == 1:
    bg_input = video_files[0]
    vf = ("[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
          "crop=720:1280,"
          "fps=30,"
          "setsar=1[vbg];"
          "[vbg]ass=" + ass_path + "[v]")
    subprocess.run([
        'ffmpeg', '-y', '-stream_loop', '-1', '-i', bg_input,
        '-i', voice_path,
        '-filter_complex', vf,
        '-map', '[v]', '-map', '1:a',
        '-t', str(voice_duration + 0.5),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
        '-c:a', 'aac', '-b:a', '128k', '-shortest',
        out_path
    ])
else:
    clip_paths = []
    per_clip = (voice_duration + 0.5) / num_bg
    
    for i, vf_path in enumerate(video_files):
        clip = 'clip_%d.mp4' % i
        clip_filter = (
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280,"
            "fps=30,"
            "setsar=1"
        )
        subprocess.run([
            'ffmpeg', '-y', '-stream_loop', '-1', '-i', vf_path,
            '-t', str(per_clip),
            '-vf', clip_filter,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
            '-an',
            clip
        ], capture_output=True)
        if os.path.exists(clip):
            clip_paths.append(clip)
    
    if clip_paths:
        with open('concat_list.txt', 'w') as f:
            for cp in clip_paths:
                f.write("file '" + os.path.abspath(cp) + "'\n")
        
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat_list.txt',
            '-c', 'copy', 'bg_concat.mp4'
        ], capture_output=True)
        
        vf = "[0:v]ass=" + ass_path + "[v]"
        subprocess.run([
            'ffmpeg', '-y', '-i', 'bg_concat.mp4', '-i', voice_path,
            '-filter_complex', vf,
            '-map', '[v]', '-map', '1:a',
            '-t', str(voice_duration + 0.5),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
            '-c:a', 'aac', '-b:a', '128k', '-shortest',
            out_path
        ])
        
        for cp in clip_paths:
            try:
                os.remove(cp)
            except:
                pass
        try:
            os.remove('bg_concat.mp4')
            os.remove('concat_list.txt')
        except:
            pass

print('Video rendered: ' + out_path)

print('STEP 7: Generating metadata')
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
        print('Video File ID: ' + file_id)
    else:
        print('Telegram error: ' + str(tg_json)[:300])
except Exception as e:
    print('Telegram parse error: ' + str(e))

if file_id:
    print('STEP 9: Saving to Supabase')
    row_id = save_to_supabase(
        CHAT_ID, file_id, title, description, tags, 1, '',
        content_type='mystery',
        script=script,
        voice_style=VOICE_NAME
    )
    print('Supabase row ID: ' + str(row_id))
    
    if row_id:
        keyboard = json.dumps({
            'inline_keyboard': [
                [
                    {'text': '✅ Upload', 'callback_data': 'approve_' + str(row_id)},
                    {'text': '📅 Schedule', 'callback_data': 'schedule_' + str(row_id)}
                ],
                [
                    {'text': '✏️ Custom', 'callback_data': 'custom_' + str(row_id)},
                    {'text': '❌ Skip', 'callback_data': 'skip_' + str(row_id)}
                ]
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
    
    topic_data = topics[idx]
    print('Processing short ' + str(idx + 1) + '/' + str(NUM_SHORTS) + ': ' + topic_data['topic'])
    
    script_data = gen_mystery_script(topic_data['topic'], topic_data['hook'], DURATION)
    script = script_data.get('script', '')
    visual_keywords = script_data.get('visual_keywords', ['mystery', 'dark'])
    
    voice_path = 'voice_%d.mp3' % idx
    if not gen_voice(script, voice_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', str(DURATION), '-q:a', '9', '-acodec', 'libmp3lame', voice_path])
    
    voice_duration = get_audio_duration(voice_path)
    
    videos = download_pixabay_videos(visual_keywords, len(visual_keywords))
    video_files = []
    for vi, v in enumerate(videos):
        path = 'bg_%d_%d.mp4' % (idx, vi)
        if download_video_file(v['url'], path):
            video_files.append(path)
    
    if not video_files:
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'color=c=0x000000:s=720x1280:d=' + str(voice_duration + 2) + ':r=30',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', 'bg_fallback_%d.mp4' % idx])
        video_files = ['bg_fallback_%d.mp4' % idx]
    
    segments = split_script_to_segments(script, 5)
    ass_path = 'captions_%d.ass' % idx
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(build_mystery_ass(segments, voice_duration))
    
    out_path = 'mystery_short_%d.mp4' % idx
    
    if len(video_files) == 1:
        vf = ("[0:v]scale=720:1280:force_original_aspect_ratio=increase,"
              "crop=720:1280,"
              "fps=30,"
              "setsar=1[vbg];"
              "[vbg]ass=" + ass_path + "[v]")
        subprocess.run([
            'ffmpeg', '-y', '-stream_loop', '-1', '-i', video_files[0],
            '-i', voice_path,
            '-filter_complex', vf,
            '-map', '[v]', '-map', '1:a',
            '-t', str(voice_duration + 0.5),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
            '-c:a', 'aac', '-b:a', '128k', '-shortest',
            out_path
        ])
    else:
        clip_paths = []
        per_clip = (voice_duration + 0.5) / len(video_files)
        for ci, vfp in enumerate(video_files):
            clip = 'clip_%d_%d.mp4' % (idx, ci)
            cf = ("scale=720:1280:force_original_aspect_ratio=increase,"
                  "crop=720:1280,"
                  "fps=30,"
                  "setsar=1")
            subprocess.run([
                'ffmpeg', '-y', '-stream_loop', '-1', '-i', vfp,
                '-t', str(per_clip), '-vf', cf,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '26', '-an', clip
            ], capture_output=True)
            if os.path.exists(clip):
                clip_paths.append(clip)
        
        if clip_paths:
            with open('concat_%d.txt' % idx, 'w') as f:
                for cp in clip_paths:
                    f.write("file '" + os.path.abspath(cp) + "'\n")
            subprocess.run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat_%d.txt' % idx,
                '-c', 'copy', 'bg_concat_%d.mp4' % idx
            ], capture_output=True)
            
            vf = "[0:v]ass=" + ass_path + "[v]"
            subprocess.run([
                'ffmpeg', '-y', '-i', 'bg_concat_%d.mp4' % idx, '-i', voice_path,
                '-filter_complex', vf,
                '-map', '[v]', '-map', '1:a',
                '-t', str(voice_duration + 0.5),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
                '-c:a', 'aac', '-b:a', '128k', '-shortest',
                out_path
            ])
            
            for cp in clip_paths:
                try:
                    os.remove(cp)
                except:
                    pass
            try:
                os.remove('bg_concat_%d.mp4' % idx)
                os.remove('concat_%d.txt' % idx)
            except:
                pass
    
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
            print('Video File ID: ' + file_id)
    except Exception as e:
        print('Telegram parse error: ' + str(e))
    
    if file_id:
        row_id = save_to_supabase(
            CHAT_ID, file_id, title, description, tags, idx + 1, '',
            content_type='mystery',
            script=script,
            voice_style=VOICE_NAME
        )
        print('Supabase row ID: ' + str(row_id))
        
        if row_id:
            keyboard = json.dumps({
                'inline_keyboard': [
                    [
                        {'text': '✅ Upload', 'callback_data': 'approve_' + str(row_id)},
                        {'text': '📅 Schedule', 'callback_data': 'schedule_' + str(row_id)}
                    ],
                    [
                        {'text': '✏️ Custom', 'callback_data': 'custom_' + str(row_id)},
                        {'text': '❌ Skip', 'callback_data': 'skip_' + str(row_id)}
                    ]
                ]
            })
            
            approval_text = '📝 Mystery Short ' + str(idx + 1) + '/' + str(NUM_SHORTS) + '\n\n'
            approval_text += '🎬 Topic: ' + topic_data['topic'] + '\n\n'
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
    
    time.sleep(2)
    
    try:
        os.remove(voice_path)
        os.remove(ass_path)
    except:
        pass

for vf_path in video_files:
    try:
        os.remove(vf_path)
    except:
        pass
try:
    os.remove(voice_path)
    os.remove(ass_path)
except:
    pass

print('All mystery shorts generated!')
