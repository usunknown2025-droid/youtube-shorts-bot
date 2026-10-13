import json, os, requests, subprocess, time, re, asyncio, urllib.parse
from gtts import gTTS
import edge_tts

GROQ_KEY = os.environ['GROQ_API_KEY']
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
DURATION = int(os.environ.get('DURATION', '45'))
NUM_SHORTS = int(os.environ.get('NUM_SHORTS', '3'))
CATEGORY = os.environ.get('CATEGORY', 'mystery')
VOICE_NAME = os.environ.get('VOICE_NAME', 'en-GB-RyanNeural')

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
    prompt += 'Also generate 6 VISUAL SCENE descriptions for AI image generation. Each scene must be:\n'
    prompt += '- Dark, cinematic, moody, documentary style\n'
    prompt += '- Related to the story progression\n'
    prompt += '- Detailed (subject, setting, lighting, atmosphere)\n'
    prompt += 'Return JSON: {"script": "narration text", "scenes": ["scene1", "scene2", "scene3", "scene4", "scene5", "scene6"]}'

    result = groq_call(prompt, max_tokens=1200, temp=0.8, json_mode=True)
    if result:
        data = parse_json_safe(result)
        if data and data.get('script'):
            return data

    return {
        'script': hook + '. ' + topic + ' remains one of history\'s greatest mysteries. Follow for more mysteries!',
        'scenes': [
            'dark abandoned ship in foggy ocean at night, cinematic',
            'old wooden deck of ship, moonlight, eerie atmosphere',
            'empty captain cabin, dusty, dark, cinematic',
            'storm clouds over ocean, dramatic lighting',
            'ship silhouette in heavy fog, mysterious',
            'dark horizon fading into night, ominous, cinematic'
        ]
    }


def gen_ai_image(scene_description, output_path, seed=42):
    try:
        cinematic_prompt = (
            scene_description + ', ' +
            'dark cinematic documentary style, moody atmospheric lighting, ' +
            'deep shadows, film grain, 1800s historical aesthetic, ' +
            'realistic, ultra detailed, 8k, dramatic composition, ' +
            'masterpiece, cinematic color grading'
        )
        encoded = urllib.parse.quote(cinematic_prompt)
        url = 'https://image.pollinations.ai/prompt/' + encoded
        url += '?width=720&height=1280&model=flux&nologo=true&seed=' + str(seed) + '&enhance=true'

        print('Generating image: ' + scene_description[:60])
        r = requests.get(url, timeout=180)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(output_path, 'wb') as f:
                f.write(r.content)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
                return True
        print('Image gen failed: status ' + str(r.status_code) + ', size ' + str(len(r.content)))
    except Exception as e:
        print('Image error: ' + str(e))
    return False


def gen_scene_images(scenes, topic):
    images = []
    for i, scene in enumerate(scenes[:6]):
        path = 'scene_%d.jpg' % i
        seed = 42 + i * 111
        if gen_ai_image(scene, path, seed):
            images.append(path)
            print('Image ' + str(i+1) + ' ready: ' + path)
        time.sleep(3)
        if len(images) >= 6:
            break

    while len(images) < 3:
        fallback_scene = topic + ', dark mysterious cinematic scene ' + str(len(images)+1)
        path = 'scene_fb_%d.jpg' % len(images)
        if gen_ai_image(fallback_scene, path, 999 + len(images)):
            images.append(path)
        else:
            break
        time.sleep(3)

    return images


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


def make_kenburns_clip(image_path, clip_duration, output_path, direction='in'):
    fps = 30
    total_frames = int(clip_duration * fps)
    if total_frames < 30:
        total_frames = 30

    if direction == 'in':
        z_expr = "min(1+0.0015*on,1.35)"
    elif direction == 'out':
        z_expr = "max(1.35-0.0015*on,1.0)"
    else:
        z_expr = "min(1+0.0012*on,1.3)"

    cine = ("eq=contrast=1.15:saturation=1.25:brightness=0.02,"
            "unsharp=5:5:0.8:3:3:0.4,"
            "vignette=PI/5")

    vf = (
        "scale=1440:2560:force_original_aspect_ratio=increase,"
        "crop=1440:2560,"
        "zoompan=z='" + z_expr + "':d=" + str(total_frames) + ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280:fps=" + str(fps) + ","
        + cine + ","
        "fps=30,setsar=1,format=yuv420p"
    )

    r = subprocess.run([
        'ffmpeg', '-y', '-loop', '1', '-i', image_path,
        '-t', str(clip_duration),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-pix_fmt', 'yuv420p',
        '-an',
        output_path
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print('KenBurns error: ' + r.stderr[-300:])
    return os.path.exists(output_path)


def build_video_from_images(images, voice_path, voice_duration, ass_path, output_path):
    total_dur = voice_duration + 0.5
    n_images = len(images)
    if n_images == 0:
        return False

    per_image = total_dur / n_images
    directions = ['in', 'out', 'in', 'out', 'in', 'out', 'in', 'out']

    clip_paths = []
    for i, img in enumerate(images):
        clip = 'kb_%d.mp4' % i
        direction = directions[i % len(directions)]
        if make_kenburns_clip(img, per_image, clip, direction):
            clip_paths.append(clip)
            print('Ken Burns clip ' + str(i+1) + ' done')

    if not clip_paths:
        return False

    with open('kb_list.txt', 'w') as f:
        for cp in clip_paths:
            f.write("file '" + os.path.abspath(cp) + "'\n")

    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'kb_list.txt',
        '-c', 'copy', 'kb_concat.mp4'
    ], capture_output=True)

    vf = "[0:v]ass=" + ass_path + "[v]"
    r = subprocess.run([
        'ffmpeg', '-y', '-i', 'kb_concat.mp4', '-i', voice_path,
        '-filter_complex', vf,
        '-map', '[v]', '-map', '1:a',
        '-t', str(total_dur),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        output_path
    ], capture_output=True, text=True)

    if r.returncode != 0:
        print('Final render error: ' + r.stderr[-300:])

    for cp in clip_paths:
        try: os.remove(cp)
        except: pass
    try:
        os.remove('kb_concat.mp4')
        os.remove('kb_list.txt')
    except: pass

    return os.path.exists(output_path)


def process_one_short(topic_data, idx):
    topic = topic_data['topic']
    hook = topic_data['hook']
    print('=== SHORT ' + str(idx+1) + ': ' + topic + ' ===')

    print('Generating script + scenes...')
    script_data = gen_mystery_script(topic, hook, DURATION)
    script = script_data.get('script', '')
    scenes = script_data.get('scenes', [])
    print('Script: ' + script[:150])
    print('Scenes: ' + str(len(scenes)))

    print('Generating voice...')
    voice_path = 'voice_%d.mp3' % idx
    if not gen_voice(script, voice_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-t', str(DURATION), '-q:a', '9', '-acodec', 'libmp3lame', voice_path])
    voice_duration = get_audio_duration(voice_path)
    print('Voice duration: %0.2f s' % voice_duration)

    print('Generating AI images...')
    images = gen_scene_images(scenes, topic)
    print('Images ready: ' + str(len(images)))

    if len(images) < 2:
        print('Not enough images, using fallback')
        for i in range(3):
            fb_path = 'scene_fb_final_%d.jpg' % i
            if gen_ai_image(topic + ', dark mysterious cinematic atmosphere ' + str(i+1), fb_path, 777+i):
                images.append(fb_path)

    if not images:
        print('No images at all, skipping short')
        return None

    print('Building captions...')
    segments = split_script_to_segments(script, len(images))
    ass_path = 'captions_%d.ass' % idx
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(build_mystery_ass(segments, voice_duration))

    print('Rendering video...')
    out_path = 'mystery_short_%d.mp4' % idx
    ok = build_video_from_images(images, voice_path, voice_duration, ass_path, out_path)

    if not ok:
        print('Video render failed for short ' + str(idx+1))
        return None

    print('Video rendered: ' + out_path)

    print('Generating metadata...')
    meta = gen_yt_metadata(topic, script)
    title = meta.get('title', topic)
    description = meta.get('description', '')
    tags = ', '.join(meta.get('tags', []))
    print('Title: ' + title)

    print('Sending to Telegram...')
    tg_response = subprocess.run([
        'curl', '-s', '-X', 'POST',
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendVideo',
        '-F', 'chat_id=' + CHAT_ID,
        '-F', 'video=@' + out_path,
        '-F', 'caption=Mystery Short ' + str(idx+1) + '/' + str(NUM_SHORTS) + ' - ' + topic
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
        return None

    print('Saving to Supabase...')
    row_id = save_to_supabase(CHAT_ID, file_id, title, description, tags, idx+1,
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
        approval_text = '📝 Mystery Short ' + str(idx+1) + '/' + str(NUM_SHORTS) + '\n\n'
        approval_text += '🎬 Topic: ' + topic + '\n\n'
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

    try:
        os.remove(voice_path)
        os.remove(ass_path)
    except: pass
    for img in images:
        try: os.remove(img)
        except: pass
    try: os.remove(out_path)
    except: pass

    return row_id


# MAIN EXECUTION
for i in range(NUM_SHORTS):
    if i >= len(topics):
        break
    try:
        process_one_short(topics[i], i)
    except Exception as e:
        print('Short ' + str(i+1) + ' failed: ' + str(e))
        continue
    time.sleep(3)

print('All mystery shorts generated!')
