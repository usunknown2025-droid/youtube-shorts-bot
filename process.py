import json, os, requests, subprocess, time, re
from faster_whisper import WhisperModel
from gtts import gTTS

GROQ_KEY = os.environ['GROQ_API_KEY']
VOICE = os.environ.get('VOICE_NAME', 'en-US-DavisNeural')
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))


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


def groq_call(prompt, max_tokens=2000, temp=0.3):
    url = 'https://api.groq.com/openai/v1/chat/completions'
    headers = {'Authorization': 'Bearer ' + GROQ_KEY, 'Content-Type': 'application/json'}
    payload = {
        'model': 'openai/gpt-oss-120b',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temp,
        'max_tokens': max_tokens
    }
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            print('Groq attempt ' + str(attempt + 1) + ', Status: ' + str(r.status_code))
            result = r.json()
            if 'choices' in result:
                return result['choices'][0]['message']['content']
            else:
                print('Response: ' + str(result))
                time.sleep(5)
        except Exception as e:
            print('Groq error: ' + str(e))
            time.sleep(5)
    return None


# ---------- STEP 1: Transcribe with word timestamps ----------
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

transcript = '\n'.join(transcript_lines)
print('Transcript ready with ' + str(total_words) + ' words')


# ---------- STEP 2: Find viral moments ----------
print('\n=== STEP 2: Find Viral Moments (Groq) ===')
prompt = 'You are a viral Shorts editor. Below is a timestamped English transcript of a YouTube video.\n\n'
prompt += 'Your task: Find the ' + str(NUM_SHORTS) + ' BEST viral-worthy segments, each about ' + str(DURATION) + ' seconds long.\n'
prompt += 'Each segment must be UNIQUE and NON-OVERLAPPING.\n'
prompt += 'Focus on moments where the speaker says something surprising, emotional, controversial, funny, or highly engaging.\n\n'
prompt += 'Reply ONLY in JSON format: {"moments": [{"start": <start_seconds>, "end": <end_seconds>, "reason": "<why viral>"}, ...]}\n\n'
prompt += 'Transcript:\n' + transcript

text = groq_call(prompt, max_tokens=2000, temp=0.3)
moments = []
if text:
    match = re.search(r'\{[\s\S]*"moments"[\s\S]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            moments = data.get('moments', [])
        except Exception as e:
            print('JSON parse error: ' + str(e))

if not moments:
    print('Fallback used')
    moments = [{'start': 0, 'end': DURATION, 'reason': 'fallback'}]

print('Got ' + str(len(moments)) + ' moments')


# ---------- STEP 3: Generate English commentary ----------
def gen_commentary(moment_text):
    prompt = 'You are an ENGLISH voiceover writer for YouTube Shorts.\n\n'
    prompt += 'Write a short, engaging ENGLISH commentary (maximum 40 words) for the video segment below.\n'
    prompt += 'The original video may be in Hindi or any other language, but YOUR OUTPUT MUST BE PURE ENGLISH.\n\n'
    prompt += 'STRICT RULES:\n'
    prompt += '1. ONLY English text - no Hindi, no Devanagari, no other scripts\n'
    prompt += '2. Do NOT write explanations, quotes, markdown, or labels\n'
    prompt += '3. Just the plain English commentary as a single paragraph\n'
    prompt += '4. Maximum 40 words\n'
    prompt += '5. Hook the viewer in the first 3 words\n\n'
    prompt += 'Segment transcript: ' + moment_text
    for attempt in range(3):
        result = groq_call(prompt, max_tokens=200, temp=0.7)
        if result:
            t = result.strip()
            if not contains_non_english(t):
                return t
            print('Non-English detected, retrying...')
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


# ---------- STEP 5: Build SRT ----------
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

    # Get segments inside this moment
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
        print('No segments in moment, skipping')
        continue

    # Generate AI commentary
    print('Generating commentary...')
    moment_text = ' '.join([s['text'] for s in moment_segs])
    commentary = gen_commentary(moment_text)
    commentary = re.sub(r'["\'\n\r]', ' ', commentary).strip()[:300]
    if not commentary:
        commentary = 'Check out this amazing moment!'
    print('Commentary: ' + commentary)

    # TTS for commentary
    tts_path = 'tts_%d.mp3' % idx
    print('Generating TTS...')
    if not gen_tts(commentary, tts_path):
        print('TTS failed - creating silence')
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', '30', '-q:a', '9', '-acodec', 'libmp3lame', tts_path])

    # Build SRT with English captions (from original speech)
    print('Building SRT...')
    srt_path = 'subs_%d.srt' % idx
    srt_content = build_srt(0, duration, moment_segs)
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    # Render: original video + original audio 20% + AI commentary 100% + captions
    print('Rendering Short...')
    out_path = 'shorts_%d.mp4' % idx
    vf = "[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,subtitles=" + srt_path + ":force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=50'[v];[0:a]volume=0.2[bg];[1:a]volume=1.0[ai];[bg][ai]amix=inputs=2:duration=first[aout]"

    subprocess.run([
        'ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
        '-i', 'video.mp4', '-i', tts_path,
        '-filter_complex', vf,
        '-map', '[v]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26',
        '-c:a', 'aac', '-b:a', '128k',
        out_path
    ])

    # Send to Telegram
    print('Sending Short ' + str(idx + 1) + ' to Telegram...')
    subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
        '-F', 'chat_id=' + CHAT_ID,
        '-F', 'video=@' + out_path,
        '-F', 'caption=Short ' + str(idx + 1) + '/' + str(len(moments)) + ' | AI Commentary + English Captions'
    ])
    time.sleep(3)

    try:
        os.remove(tts_path)
        os.remove(srt_path)
    except:
        pass

print('\nAll shorts generated and sent!')
