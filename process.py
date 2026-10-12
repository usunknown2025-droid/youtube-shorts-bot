import json, os, requests, subprocess, time, re
from faster_whisper import WhisperModel
from gtts import gTTS

GROQ_KEY = os.environ['GROQ_API_KEY']
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))

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


def save_to_supabase(chat_id, file_id, title, description, tags, short_number, thumbnail_urls=''):
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
        'thumbnail_urls': thumbnail_urls
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


print('STEP 1: Whisper Transcription')
model = WhisperModel('tiny', device='cpu', compute_type='int8')
segments, _ = model.transcribe('audio.wav', task='translate', word_timestamps=True)
seg_data = []
total_words = 0
for s in segments:
    seg_words = []
    if s.words:
        for w in s.words:
            seg_words.append({'start': w.start, 'end': w.end, 'word': w.word})
            total_words += 1
    seg_data.append({'start': s.start, 'end': s.end, 'text': s.text.strip(), 'words': seg_words})

print('Transcript ready with ' + str(total_words) + ' words')
video_total_duration = seg_data[-1]['end'] if seg_data else 60
print('Video total duration: %0.1f seconds' % video_total_duration)


print('STEP 2: Find Viral Moments')
max_possible = int(video_total_duration // DURATION)
target_moments = min(NUM_SHORTS, max_possible)

combined_text = ' '.join([s['text'] for s in seg_data])
if len(combined_text) > 4000:
    combined_text = combined_text[:4000] + '...'

prompt = 'Find ' + str(target_moments) + ' viral moments (~' + str(DURATION) + 's each, no overlap) from this transcript.\n\n'
prompt += 'Return ONLY valid JSON, no markdown:\n'
prompt += '{"moments": [{"start": 12.5, "end": 57.5, "reason": "why viral"}]}\n\n'
prompt += 'TRANSCRIPT:\n' + combined_text

result = groq_call(prompt, max_tokens=1500, temp=0.3, json_mode=True)

all_moments = []
if result:
    try:
        clean = result.strip()
        if clean.startswith('```'):
            clean = clean.split('```')[1]
            if clean.startswith('json'):
                clean = clean[4:]
        clean = clean.strip()
        data = json.loads(clean)
        all_moments = data.get('moments', [])
        print('Groq returned ' + str(len(all_moments)) + ' moments')
    except Exception as e:
        print('JSON parse error: ' + str(e))

if len(all_moments) < target_moments:
    existing_starts = set(int(m.get('start', 0)) for m in all_moments)
    for i in range(target_moments):
        candidate_start = int(i * (video_total_duration - DURATION) / max(1, target_moments - 1)) if target_moments > 1 else 0
        candidate_end = candidate_start + DURATION
        if candidate_start in existing_starts:
            continue
        overlap = False
        for m in all_moments:
            ms = float(m.get('start', 0))
            me = float(m.get('end', 0))
            if not (candidate_end <= ms or candidate_start >= me):
                overlap = True
                break
        if not overlap:
            all_moments.append({'start': candidate_start, 'end': candidate_end, 'reason': 'fallback'})
        if len(all_moments) >= target_moments:
            break

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
    if len(filtered) >= target_moments:
        break

moments = filtered[:target_moments]
if not moments:
    moments = [{'start': 0, 'end': DURATION, 'reason': 'fallback'}]
print('Final: Got ' + str(len(moments)) + ' moments')


def gen_commentary(moment_text):
    prompt = 'Write short ENGLISH commentary (max 35 words) for this video segment.\n\n'
    prompt += 'RULES:\n'
    prompt += '1. PURE ENGLISH only - no Hindi, no other scripts\n'
    prompt += '2. Describe the SPECIFIC action happening in the video\n'
    prompt += '3. End with a CALL TO ACTION like "Comment what you think!" or "Follow for more!"\n'
    prompt += '4. Keep it under 35 words total\n'
    prompt += '5. Just the commentary, no labels\n\n'
    prompt += 'Segment: ' + moment_text[:800]
    for attempt in range(3):
        result = groq_call(prompt, max_tokens=180, temp=0.7)
        if result:
            t = result.strip()
            if not contains_non_english(t):
                return t
        time.sleep(10)
    return 'Check out this amazing moment! Comment what you think!'


def gen_yt_metadata(moment_text, commentary):
    prompt = 'Generate YouTube Shorts metadata for this video. This is for SEO - make it findable in search.\n\n'
    prompt += 'TRANSCRIPT: ' + moment_text[:800] + '\n\n'
    prompt += 'COMMENTARY: ' + commentary[:300] + '\n\n'
    prompt += 'CRITICAL SEO RULES:\n'
    prompt += '1. TITLE: Must include 2-3 HIGH-SEARCH KEYWORDS that people actually search for\n'
    prompt += '   - Example: "Kenya Water Well", "Clean Water Project", "Rural Engineering"\n'
    prompt += '   - NOT generic words like "Amazing", "Incredible", "Viral" alone\n'
    prompt += '   - Must be specific to the actual content\n'
    prompt += '2. DESCRIPTION: 2-3 lines with SEO keywords + 3-5 relevant hashtags\n'
    prompt += '   - First line must have main keyword\n'
    prompt += '   - End with 3-5 hashtags like #KenyaWater #CleanWater #Shorts\n'
    prompt += '3. TAGS: 12-15 specific tags (mix of high-search and long-tail)\n'
    prompt += '   - Include: topic keywords, location, action words, category\n'
    prompt += '   - Example: "kenya water well", "clean drinking water", "rural engineering", "humanitarian project", "water well construction", "african development"\n\n'
    prompt += 'Return ONLY JSON:\n'
    prompt += '{"title": "...", "description": "...", "tags": ["tag1", "tag2"]}'
    result = groq_call(prompt, max_tokens=600, temp=0.4, json_mode=True)
    if result:
        try:
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            clean = clean.strip()
            return json.loads(clean)
        except Exception as e:
            print('Metadata parse error: ' + str(e))
    return {
        'title': 'Viral Moment You Must See!',
        'description': 'Watch this amazing viral moment!\n\n#Shorts #Viral',
        'tags': ['shorts', 'viral', 'trending']
    }


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


def ass_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return '%d:%02d:%05.2f' % (hrs, mins, secs)


def wrap_caption(text, max_chars=18):
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


def build_combined_ass(commentary, tts_dur, moment_segs, actual_tts_dur=None):
    if actual_tts_dur is None:
        actual_tts_dur = tts_dur
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
    lines.append('Style: Commentary,Arial,45,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,3,8,30,30,700,1')
    lines.append('Style: Caption,Arial,80,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,3,2,30,30,270,1')
    lines.append('')
    lines.append('[Events]')
    lines.append('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text')

    words = commentary.split()
    if words:
        word_dur = actual_tts_dur / float(len(words))
        growing = []
        for i, w in enumerate(words):
            growing.append(w)
            s = i * word_dur
            e = (i + 1) * word_dur
            if e <= s:
                e = s + 0.2
            text = wrap_caption(' '.join(growing), 25)
            lines.append('Dialogue: 0,%s,%s,Commentary,,0,0,0,,%s' % (ass_time(s), ass_time(e), text))

    for seg in moment_segs:
        seg_words = seg.get('words', [])
        if not seg_words:
            seg_text = seg.get('text', '').strip()
            if seg_text:
                s = seg.get('start', 0) + tts_dur
                e = seg.get('end', 0) + tts_dur
                if e > s:
                    wrapped = wrap_caption(seg_text)
                    lines.append('Dialogue: 0,%s,%s,Caption,,0,0,0,,%s' % (ass_time(s), ass_time(e), wrapped))
            continue
        growing = []
        for i, w in enumerate(seg_words):
            growing.append(w['word'].strip())
            s = w['start'] + tts_dur
            if i + 1 < len(seg_words):
                e = seg_words[i + 1]['start'] + tts_dur
            else:
                e = w['end'] + tts_dur
            if e <= s:
                e = s + 0.3
            text = wrap_caption(' '.join(growing))
            lines.append('Dialogue: 0,%s,%s,Caption,,0,0,0,,%s' % (ass_time(s), ass_time(e), text))

    return '\n'.join(lines)


def build_hook_text(title):
    stop_words = ['the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'to', 'for', 'is', 'was', 'with', 'at', 'by']
    words = title.split()
    important_words = [w for w in words if w.lower() not in stop_words]
    hook_words = important_words[:3]
    hook_text = ' '.join(hook_words).upper()
    hook_text = re.sub(r'[^A-Z0-9 !?]', '', hook_text)
    if len(hook_text) > 25:
        hook_text = hook_text[:25].strip()
    if not hook_text:
        hook_text = 'WATCH THIS'
    return hook_text


for idx, moment in enumerate(moments):
    print('SHORT ' + str(idx + 1) + '/' + str(len(moments)))
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
    print('Moment text: ' + moment_text[:150])

    commentary = gen_commentary(moment_text)
    commentary = re.sub(r'["\'\n\r]', ' ', commentary).strip()[:300]
    print('Commentary: ' + commentary)

    print('Generating metadata with SEO...')
    meta = gen_yt_metadata(moment_text, commentary)
    title = meta.get('title', 'Viral Moment')
    description = meta.get('description', '')
    tags = ', '.join(meta.get('tags', []))
    print('Title: ' + title)
    print('Tags: ' + tags[:200])

    tts_path = 'tts_%d.mp3' % idx
    if not gen_tts(commentary, tts_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', '30', '-q:a', '9', '-acodec', 'libmp3lame', tts_path])

    actual_tts_dur = get_audio_duration(tts_path)
    tts_dur = actual_tts_dur + 0.4

    ass_path = 'subs_%d.ass' % idx
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(build_combined_ass(commentary, tts_dur, moment_segs, actual_tts_dur))

    print('Extracting hook frame...')
    hook_frame = 'hook_%d.jpg' % idx
    hook_offset = min(2.0, duration * 0.3)
    hook_time = start + hook_offset
    subprocess.run([
        'ffmpeg', '-y', '-ss', str(hook_time), '-i', 'video.mp4',
        '-vframes', '1', '-vf', 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1',
        '-q:v', '2', hook_frame
    ], capture_output=True)

    hook_text = build_hook_text(title)
    print('Hook text: ' + hook_text)

    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

    print('Rendering video...')
    out_path = 'shorts_%d.mp4' % idx
    vf = ("[2:v]fps=30,scale=720:1280,setsar=1,"
          "drawtext=text='" + hook_text + "':"
          "fontcolor=Yellow:fontsize=58:"
          "borderw=6:bordercolor=Black:"
          "box=1:boxcolor=Black@0.6:boxborderw=15:"
          "x=(w-text_w)/2:y=h*0.12:"
          "fontfile=" + font_path + "[hookvid];"
          "[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,setsar=1,fps=30[v0];"
          "[hookvid][v0]concat=n=2:v=1:a=0[vcat];"
          "[vcat]ass=" + ass_path + "[v]")
    af = ("[1:a]volume=1.0[tts];"
          "[0:a]volume=0.2[orig];"
          "[tts][orig]concat=n=2:v=0:a=1[aout]")

    subprocess.run([
        'ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
        '-i', 'video.mp4', '-i', tts_path,
        '-loop', '1', '-t', str(tts_dur), '-i', hook_frame,
        '-filter_complex', vf + ';' + af,
        '-map', '[v]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
        '-c:a', 'aac', '-b:a', '128k',
        out_path
    ])

    try:
        os.remove(hook_frame)
    except:
        pass

    print('Sending video to Telegram...')
    tg_response = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
        '-F', 'chat_id=' + CHAT_ID,
        '-F', 'video=@' + out_path,
        '-F', 'caption=Short ' + str(idx + 1) + '/' + str(len(moments))
    ], capture_output=True, text=True)

    file_id = None
    try:
        tg_json = json.loads(tg_response.stdout)
        if tg_json.get('ok'):
            file_id = tg_json['result']['video']['file_id']
            print('Video File ID: ' + file_id)
    except Exception as e:
        print('Telegram parse error: ' + str(e))

    if not file_id:
        print('File ID not received, skipping')
        continue

    print('Saving to Supabase...')
    row_id = save_to_supabase(CHAT_ID, file_id, title, description, tags, idx + 1, '')
    print('Supabase row ID: ' + str(row_id))

    if not row_id:
        continue

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

    approval_text = '📝 *Short ' + str(idx + 1) + '/' + str(len(moments)) + '*\n\n'
    approval_text += '📄 Title: ' + title + '\n\n'
    approval_text += '📝 Description: ' + description + '\n\n'
    approval_text += '🏷️ Tags: ' + tags[:150] + '...\n\n'
    approval_text += 'Kya karna hai?'

    subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        '-d', 'chat_id=' + CHAT_ID,
        '-d', 'text=' + approval_text,
        '-d', 'parse_mode=Markdown',
        '-d', 'reply_markup=' + keyboard
    ])

    prompt_text = '🎨 CHATGPT THUMBNAIL PROMPT for Short ' + str(idx + 1) + '\n\n'
    prompt_text += 'Copy this and paste in ChatGPT:\n\n'
    prompt_text += 'You are a MrBeast-style YouTube Shorts thumbnail designer. Generate 6 DIFFERENT thumbnails for:\n\n'
    prompt_text += 'VIDEO TOPIC: ' + title + '\n\n'
    prompt_text += 'RULES:\n'
    prompt_text += '1. Real human face with SHOCKED or EXCITED expression\n'
    prompt_text += '2. BIG BOLD YELLOW text with THICK BLACK OUTLINE (2-3 words)\n'
    prompt_text += '3. Large EMOJI in corner (shocked face, fire, money, lightning)\n'
    prompt_text += '4. RED CIRCLE or RED ARROW pointing to key detail\n'
    prompt_text += '5. HIGH CONTRAST, saturated vibrant colors\n'
    prompt_text += '6. Text readable on mobile, max 4 words\n'
    prompt_text += '7. Format: 9:16 vertical (720x1280)\n\n'
    prompt_text += 'GENERATE THESE 6 STYLES:\n\n'
    prompt_text += 'STYLE 1 - Face + Big Text + Emoji\n'
    prompt_text += 'STYLE 2 - Action Frame + Red Circle\n'
    prompt_text += 'STYLE 3 - Face + Text + Red Arrow\n'
    prompt_text += 'STYLE 4 - Text-Heavy + Small Face\n'
    prompt_text += 'STYLE 5 - Before/After Split\n'
    prompt_text += 'STYLE 6 - Dramatic Zoom + Text\n\n'
    prompt_text += 'For each: generate image, label "Style 1", "Style 2" etc.\n'
    prompt_text += 'Output all 6 images so I can compare and choose.'

    subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        '-d', 'chat_id=' + CHAT_ID,
        '-d', 'text=' + prompt_text
    ])

    time.sleep(3)

    try:
        os.remove(tts_path)
        os.remove(ass_path)
    except:
        pass

print('All shorts generated and sent for approval!')
