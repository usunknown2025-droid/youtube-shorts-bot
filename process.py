import json, os, requests, subprocess, time, re
from faster_whisper import WhisperModel
from gtts import gTTS

GROQ_KEY = os.environ['GROQ_API_KEY']
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


def get_audio_duration(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                            path], capture_output=True, text=True)
    try:
        return float(probe.stdout.strip())
    except:
        return 0.0


# ---------- STEP 1: Transcribe with word timestamps ----------
print('\n=== STEP 1: Whisper Transcription (English translate) ===')
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


# ---------- STEP 3: Build English dub track for a moment ----------
def build_dub_track(moment_segments, moment_duration, output_path):
    """For each segment, generate English TTS, align to segment timing, mix into one track."""
    # Generate TTS for each segment with the correct speed
    processed = []
    for i, seg in enumerate(moment_segments):
        seg_text = seg['text'].strip()
        if not seg_text:
            continue
        seg_dur = seg['end'] - seg['start']
        if seg_dur <= 0.1:
            continue

        tts_raw = 'tmp_tts_%d.mp3' % i
        try:
            tts = gTTS(text=seg_text, lang='en', slow=False)
            tts.save(tts_raw)
        except Exception as e:
            print('TTS fail seg %d: %s' % (i, e))
            continue

        tts_dur = get_audio_duration(tts_raw)
        if tts_dur <= 0:
            continue

        # Speed adjustment: tempo > 1 = faster
        tempo = tts_dur / seg_dur
        if tempo > 1.6:
            tempo = 1.6
        if tempo < 0.6:
            tempo = 0.6

        tts_adj = 'tmp_adj_%d.wav' % i
        if abs(tempo - 1.0) > 0.03:
            subprocess.run(['ffmpeg', '-y', '-i', tts_raw,
                            '-filter:a', 'atempo=%0.3f' % tempo,
                            '-ar', '44100', '-ac', '2', tts_adj],
                           capture_output=True)
        else:
            subprocess.run(['ffmpeg', '-y', '-i', tts_raw,
                            '-ar', '44100', '-ac', '2', tts_adj],
                           capture_output=True)

        # Now pad/trim to exactly seg_dur
        tts_final = 'tmp_fin_%d.wav' % i
        subprocess.run(['ffmpeg', '-y', '-i', tts_adj,
                        '-af', 'apad', '-t', '%0.3f' % seg_dur,
                        '-ar', '44100', '-ac', '2', tts_final],
                       capture_output=True)

        delay_ms = int(seg['start'] * 1000)
        processed.append({'file': tts_final, 'delay': delay_ms})
        try:
            os.remove(tts_raw)
            os.remove(tts_adj)
        except:
            pass

    if not processed:
        return False

    # Build ffmpeg command with anullsrc base + each segment delayed
    cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i',
           'anullsrc=r=44100:cl=stereo', '-t', '%0.3f' % moment_duration]
    for p in processed:
        cmd += ['-i', p['file']]

    filters = []
    filters.append('[0:a]volume=0[base]')
    mix_inputs = ['[base]']
    for idx, p in enumerate(processed):
        label = '[s%d]' % idx
        filters.append('[%d:a]adelay=%d|%d,volume=1.0%s' % (idx + 1, p['delay'], p['delay'], label))
        mix_inputs.append(label)
    n = len(processed) + 1
    filters.append('%samix=inputs=%d:duration=first:normalize=0[out]' % (''.join(mix_inputs), n))

    filter_complex = ';'.join(filters)

    cmd += ['-filter_complex', filter_complex,
            '-map', '[out]', '-ar', '44100', '-ac', '2',
            '-c:a', 'libmp3lame', '-b:a', '192k', output_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print('Dub track build failed: ' + result.stderr[-500:])
        return False

    for p in processed:
        try:
            os.remove(p['file'])
        except:
            pass

    return True


# ---------- STEP 4: Build SRT from word timestamps ----------
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


# ---------- STEP 5: Process each moment ----------
for idx, moment in enumerate(moments):
    print('\n========== SHORT ' + str(idx + 1) + '/' + str(len(moments)) + ' ==========')
    start = float(moment['start'])
    end = float(moment['end'])
    duration = end - start

    # Get segments that fall inside this moment
    moment_segs = []
    for seg in seg_data:
        if seg['end'] < start or seg['start'] > end:
            continue
        # Clip segment boundaries to moment range
        new_seg = {
            'start': max(seg['start'], start) - start,
            'end': min(seg['end'], end) - start,
            'text': seg['text'],
            'words': []
        }
        # Also clip words
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

    # Build English dub track
    print('Building English dub track...')
    dub_path = 'dub_%d.mp3' % idx
    if not build_dub_track(moment_segs, duration, dub_path):
        print('Dub track failed, using silence')
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', str(duration), '-q:a', '9', '-acodec', 'libmp3lame', dub_path])

    # Build SRT
    print('Building SRT...')
    srt_path = 'subs_%d.srt' % idx
    srt_content = build_srt(0, duration, moment_segs)  # already relative to moment
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    # Render final Short: original video + dub track (original audio 15%)
    print('Rendering Short...')
    out_path = 'shorts_%d.mp4' % idx
    vf = "[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,subtitles=" + srt_path + ":force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=50'[v];[0:a]volume=0.15[bg];[1:a]volume=1.0[dub];[bg][dub]amix=inputs=2:duration=first[aout]"

    subprocess.run([
        'ffmpeg', '-y', '-ss', str(start), '-t', str(duration),
        '-i', 'video.mp4', '-i', dub_path,
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
        '-F', 'caption=Short ' + str(idx + 1) + '/' + str(len(moments)) + ' (English Dub)'
    ])
    time.sleep(3)

    # Cleanup
    try:
        os.remove(dub_path)
        os.remove(srt_path)
    except:
        pass

print('\nAll shorts generated and sent!')
