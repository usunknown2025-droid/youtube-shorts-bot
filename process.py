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
                print('Groq response: ' + str(result)[:300])
        except Exception as e:
            print('Groq error: ' + str(e))
            time.sleep(5)
    return None


def save_to_supabase(chat_id, file_id, title, description, tags):
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
        'status': 'pending'
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

print('Transcript ready with ' + str(total_words) + ' words')
video_total_duration = seg_data[-1]['end'] if seg_data else 60
print('Video total duration: %0.1f seconds' % video_total_duration)


# ---------- STEP 2: Find viral moments ----------
print('\n=== STEP 2: Find Viral Moments ===')
max_possible = int(video_total_duration // DURATION)
print('Max possible non-overlapping moments: ' + str(max_possible))
target_moments = min(NUM_SHORTS, max_possible)

prompt = 'You are analyzing a YouTube video transcript. Your job is to find viral moments.\n\n'
prompt += 'REQUIREMENTS:\n'
prompt += '- Find exactly ' + str(target_moments) + ' moments\n'
prompt += '- Each moment should be approximately ' + str(DURATION) + ' seconds long\n'
prompt += '- Moments MUST NOT overlap with each other\n'
prompt += '- Spread them across the whole video, not clustered together\n\n'
prompt += 'OUTPUT FORMAT (strict JSON):\n'
prompt += '{"moments": [{"start": 12.5, "end": 57.5, "reason": "interesting moment"}]}\n\n'
prompt += 'IMPORTANT: Return exactly ' + str(target_moments) + ' moments in the array.\n'
prompt += 'Do NOT return empty array. If unsure, pick evenly distributed timestamps.\n\n'
prompt += 'FULL TRANSCRIPT:\n'
for s in seg_data:
    prompt += '%0.1f-%0.1f: %s\n' % (s['start'], s['end'], s['text'])

result = groq_call(prompt, max_tokens=2500, temp=0.3, json_mode=True)

all_moments = []
if result:
    try:
        data = json.loads(result)
        all_moments = data.get('moments', [])
        print('Groq returned ' + str(len(all_moments)) + ' moments')
    except Exception as e:
        print('JSON parse error: ' + str(e))
        print('Raw: ' + result[:500])

if len(all_moments) < target_moments:
    print('Adding evenly distributed moments as fallback...')
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
            all_moments.append({
                'start': candidate_start,
                'end': candidate_end,
                'reason': 'fallback moment'
            })
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
    print('Fallback used')
    moments = [{'start': 0, 'end': DURATION, 'reason': 'fallback'}]

print('Final: Got ' + str(len(moments)) + ' moments (requested: ' + str(NUM_SHORTS) + ')')


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


def gen_yt_metadata(commentary):
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


# ---------- STEP 5: Combined ASS (commentary middle + captions bottom) ----------
def ass_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return '%d:%02d:%05.2f' % (hrs, mins, secs)


def build_combined_ass(commentary, tts_dur, moment_segs):
    """Single ASS file with two styles: Commentary (middle) + Caption (bottom)"""
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
    # Commentary style: Alignment=5 (middle-center), yellow, size 26
    lines.append('Style: Commentary,Arial,26,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,5,30,30,0,1')
    # Caption style: Alignment=2 (bottom-center), bigger (30), higher up (MarginV=100)
    lines.append('Style: Caption,Arial,30,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,30,30,100,1')
    lines.append('')
    lines.append('[Events]')
    lines.append('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text')

    # Part A: Commentary word-by-word (on black screen)
    words = commentary.split()
    if words:
        word_dur = tts_dur / float(len(words))
        growing = []
        for i, w in enumerate(words):
            growing.append(w)
            s = i * word_dur
            e = (i + 1) * word_dur
            if e <= s:
                e = s + 0.2
            text = ' '.join(growing)
            lines.append('Dialogue: 0,%s,%s,Commentary,,0,0,0,,%s' % (ass_time(s), ass_time(e), text))

    # Part B: Video captions word-by-word (on video after black screen)
    for seg in moment_segs:
        seg_words = seg.get('words', [])
        if not seg_words:
            seg_text = seg.get('text', '').strip()
            if seg_text:
                s = seg.get('start', 0) + tts_dur
                e = seg.get('end', 0) + tts_dur
                if e > s:
                    lines.append('Dialogue: 0,%s,%s,Caption,,0,0,0,,%s' % (ass_time(s), ass_time(e), seg_text))
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
            text = ' '.join(growing)
            lines.append('Dialogue: 0,%s,%s,Caption,,0,0,0,,%s' % (ass_time(s), ass_time(e), text))

    return '\n'.join(lines)


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
    commentary = gen_commentary(moment_text)
    commentary = re.sub(r'["\'\n\r]', ' ', commentary).strip()[:300]
    print('Commentary: ' + commentary)

    tts_path = 'tts_%d.mp3' % idx
    if not gen_tts(commentary, tts_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', '30', '-q:a', '9', '-acodec', 'libmp3lame', tts_path])

    tts_dur = get_audio_duration(tts_path) + 0.4
    print('TTS duration: %0.2f seconds' % tts_dur)

    ass_path = 'subs_%d.ass' % idx
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(build_combined_ass(commentary, tts_dur, moment_segs))

    out_path = 'shorts_%d.mp4' % idx

    vf = ("color=black:s=720x1280:d=" + str(tts_dur) + ":r=30[black];"
          "[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,setsar=1,fps=30[v0];"
          "[black][v0]concat=n=2:v=1:a=0[vcat];"
          "[vcat]ass=" + ass_path + "[v]")

    af = ("[1:a]volume=1.0[tts];"
          "[0:a]volume=0.2[orig];"
          "[tts][orig]concat=n=2:v=0:a=1[aout]")

    print('Rendering Short...')
    subprocess.run([
        'ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
        '-i', 'video.mp4', '-i', tts_path,
        '-filter_complex', vf + ';' + af,
        '-map', '[v]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
        '-c:a', 'aac', '-b:a', '128k',
        out_path
    ])

    print('Sending to Telegram...')
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
            print('File ID: ' + file_id)
    except Exception as e:
        print('Telegram parse error: ' + str(e))

    if not file_id:
        print('Failed to get file_id, skipping Supabase save')
        continue

    print('Generating YouTube metadata...')
    meta = gen_yt_metadata(commentary)
    title = meta.get('title', 'Viral Short')
    description = meta.get('description', '')
    tags = ', '.join(meta.get('tags', []))

    print('Saving to Supabase...')
    row_id = save_to_supabase(CHAT_ID, file_id, title, description, tags)
    print('Supabase row ID: ' + str(row_id))

    if row_id:
        approval_text = '📝 Title: ' + title + '\n\n'
        approval_text += '📄 Description: ' + description[:200] + '...\n\n'
        approval_text += '🏷️ Tags: ' + tags[:200] + '\n\n'
        approval_text += 'Kya karna hai?'

        keyboard = json.dumps({
            'inline_keyboard': [[
                {'text': '✅ Upload', 'callback_data': 'approve_' + str(row_id)},
                {'text': '✏️ Custom', 'callback_data': 'custom_' + str(row_id)},
                {'text': '❌ Skip', 'callback_data': 'skip_' + str(row_id)}
            ]]
        })

        subprocess.run([
            'curl', '-s', '-X', 'POST',
            'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
            '-d', 'chat_id=' + CHAT_ID,
            '-d', 'text=' + approval_text,
            '-d', 'reply_markup=' + keyboard
        ])

    time.sleep(3)

    try:
        os.remove(tts_path)
        os.remove(ass_path)
    except:
        pass

print('\nAll shorts generated and sent for approval!')
