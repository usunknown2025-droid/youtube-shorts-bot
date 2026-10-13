import json, os, requests, subprocess, time, random

PK = os.environ.get('PIXABAY_API_KEY', '')
CID = os.environ.get('CHAT_ID', '')
BT = os.environ.get('BOT_TOKEN', '')
GK = os.environ.get('GROQ_API_KEY', '')
MUSIC = os.environ.get('MUSIC_URL', '')
NS = int(os.environ.get('NUM_VIDEOS', '1'))
SU = os.environ.get('SUPABASE_URL', '').rstrip('/')
SK = os.environ.get('SUPABASE_KEY', '')

def groq(p):
    u = 'https://api.groq.com/openai/v1/chat/completions'
    h = {'Authorization': 'Bearer ' + GK, 'Content-Type': 'application/json'}
    pl = {'model': 'openai/gpt-oss-120b', 'messages': [{'role': 'user', 'content': p}], 'temperature': 0.9, 'max_tokens': 500, 'response_format': {'type': 'json_object'}}
    for _ in range(3):
        try:
            r = requests.post(u, headers=h, json=pl, timeout=60).json()
            if 'choices' in r: return r['choices'][0]['message']['content']
        except: pass
        time.sleep(3)
    return None

def pj(t):
    try:
        c = t.strip()
        if c.startswith('```'): c = c.split('```')[1]
        if c.startswith('json'): c = c[4:]
        s = c.find('{'); e = c.rfind('}')
        return json.loads(c[s:e+1])
    except: return None

def dwn(url, path):
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            return os.path.getsize(path) > 5000
    except: pass
    return False

def probe(p):
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', p], capture_output=True, text=True)
        return float(r.stdout.strip())
    except: return 0

def pick_cat_videos():
    cats = ['cute cat', 'orange cat', 'tabby cat', 'kitten playing', 'cat sitting', 'fluffy cat', 'black cat', 'white cat', 'cat looking', 'cat meowing', 'cat relaxing']
    for attempt in range(8):
        q = random.choice(cats)
        try:
            r = requests.get('https://pixabay.com/api/videos/', params={'key': PK, 'q': q, 'per_page': 20, 'safesearch': 'true', 'video_type': 'film', 'order': 'popular'}, timeout=30).json()
            if 'hits' in r and len(r['hits']) >= 6:
                vids = []
                for h in r['hits'][:15]:
                    u = h['videos'].get('medium', {}).get('url') or h['videos'].get('small', {}).get('url')
                    if u: vids.append(u)
                if len(vids) >= 6:
                    print('Cat: ' + q + ' (' + str(len(vids)) + ' videos)')
                    return vids
        except: pass
        time.sleep(0.4)
    return []

def fast_clip(inp, out, dur):
    td = probe(inp)
    if td < dur + 0.2: return False
    st = random.uniform(0, td - dur - 0.1)
    fx = random.choice([
        'eq=contrast=1.25:saturation=1.5:brightness=0.06',
        'eq=contrast=1.3:saturation=1.6:brightness=0.05',
        'eq=contrast=1.2:saturation=1.4,unsharp=5:5:1.5',
        'eq=contrast=1.35:saturation=1.55'
    ])
    zoom = random.choice([1.0, 1.05, 1.1])
    vf = 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,' + fx
    if zoom > 1.0:
        vf += ',crop=iw/' + str(zoom) + ':ih/' + str(zoom) + ',scale=720:1280'
    vf += ',fps=30,setsar=1,format=yuv420p'
    r = subprocess.run(['ffmpeg', '-y', '-ss', str(st), '-t', str(dur), '-i', inp, '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-an', out], capture_output=True)
    return r.returncode == 0 and os.path.exists(out)

def ftime(s):
    return str(int(s//3600)) + ':' + str(int((s%3600)//60)).zfill(2) + ':' + ('%05.2f' % (s%60))

def build_ass(td, ap):
    L = ['[Script Info]','ScriptType: v4.00+','PlayResX: 720','PlayResY: 1280','WrapStyle: 0','ScaledBorderAndShadow: yes','','[V4+ Styles]','Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding','Style: Meme,Arial,70,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,3,2,40,40,180,1','','[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    L.append('Dialogue: 0,0:00:00.00,' + ftime(td) + ',Meme,,0,0,0,,AURA +1000')
    open(ap, 'w').write('\n'.join(L))

def supabase(fid, ti, de, tg, n):
    u = SU + '/rest/v1/pending_shorts'
    h = {'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    d = {'chat_id': CID, 'file_id': fid, 'title': ti, 'description': de, 'tags': tg, 'status': 'pending', 'short_number': n, 'upload_status': 'pending', 'content_type': 'jumpstyle_cat', 'script': 'jumpstyle cat', 'voice_style': 'none'}
    try:
        r = requests.post(u, headers=h, json=d, timeout=30).json()
        if isinstance(r, list) and r: return r[0].get('id')
    except: pass
    return None

def gen_meta():
    p = 'YouTube Shorts metadata for viral jumpstyle cat video. Title funny (max 60 chars) + "#Shorts #Viral #MrBeast #Trending". Description: 2 lines + 15 hashtags. Tags: 15 min. Return JSON: {"title":"...","description":"...","tags":["t1"]}'
    r = groq(p)
    if r:
        d = pj(r)
        if d: return d
    return {'title': 'Cat Aura +1000 #Shorts #Viral #MrBeast #Trending', 'description': 'Viral cat moment!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing', 'tags': ['cat', 'funny cat', 'cute cat', 'kitten', 'viral cat', 'shorts', 'viral', 'trending', 'mrbeast', 'youtube shorts', 'must watch', 'aura', 'jumpstyle', 'meme', 'funny']}

def build(idx):
    print('=== CAT VIDEO ' + str(idx+1) + ' ===')
    urls = pick_cat_videos()
    if len(urls) < 6:
        print('Not enough videos'); return None
    
    clips = []
    for i, u in enumerate(urls):
        p = 'c_' + str(i) + '.mp4'
        if dwn(u, p):
            cp = 'cc_' + str(i) + '.mp4'
            if fast_clip(p, cp, random.uniform(0.3, 0.45)):
                clips.append(cp)
        try: os.remove(p)
        except: pass
        if len(clips) >= 12: break
    if len(clips) < 5:
        print('Not enough clips'); return None
    print(str(len(clips)) + ' fast clips ready')
    
    open('l.txt', 'w').write('\n'.join("file '" + os.path.abspath(c) + "'" for c in clips))
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'l.txt', '-c', 'copy', 'cat_raw.mp4'], capture_output=True)
    td = probe('cat_raw.mp4')
    if td < 2: return None
    print('Total: ' + str(round(td, 2)) + 's')
    
    ap = 'ov.ass'
    build_ass(td, ap)
    op = 'cat_' + str(idx) + '.mp4'
    
    if MUSIC:
        mp = 'm.mp3'
        print('Downloading music...')
        if dwn(MUSIC, mp):
            print('Music added!')
            subprocess.run(['ffmpeg', '-y', '-i', 'cat_raw.mp4', '-i', mp, '-filter_complex', '[0:v]ass=' + ap + '[v];[1:a]volume=0.9[a]', '-map', '[v]', '-map', '[a]', '-shortest', '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-b:a', '128k', op], capture_output=True)
            try: os.remove(mp)
            except: pass
        else:
            print('Music download failed')
    
    if not os.path.exists(op):
        print('Rendering without music')
        subprocess.run(['ffmpeg', '-y', '-i', 'cat_raw.mp4', '-vf', 'ass=' + ap, '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-an', op], capture_output=True)
    
    for c in clips:
        try: os.remove(c)
        except: pass
    try: os.remove('l.txt'); os.remove('cat_raw.mp4'); os.remove(ap)
    except: pass
    
    if not os.path.exists(op): return None
    print('Video ready: ' + op)
    
    tg = subprocess.run(['curl', '-s', '-X', 'POST', 'https://api.telegram.org/bot' + BT + '/sendVideo', '-F', 'chat_id=' + CID, '-F', 'video=@' + op, '-F', 'caption=Cat Video ' + str(idx+1)], capture_output=True, text=True)
    fid = None
    try:
        j = json.loads(tg.stdout)
        if j.get('ok'): fid = j['result']['video']['file_id']
    except: pass
    if not fid: return None
    
    meta = gen_meta()
    ti = meta.get('title', 'Cat Aura')
    de = meta.get('description', '')
    tg_tag = ', '.join(meta.get('tags', []))
    
    rid = supabase(fid, ti, de, tg_tag, idx+1)
    print('Row: ' + str(rid))
    
    if rid:
        kb = json.dumps({'inline_keyboard':[[{'text':'✅ Upload','callback_data':'approve_'+str(rid)},{'text':'📅 Schedule','callback_data':'schedule_'+str(rid)}],[{'text':'✏️ Custom','callback_data':'custom_'+str(rid)},{'text':'❌ Skip','callback_data':'skip_'+str(rid)}]]})
        txt = '🐱 Cat Video ' + str(idx+1) + '/' + str(NS) + '\n\n📄 ' + ti + '\n\n📝 ' + de[:300] + '...\n\n🏷️ ' + tg_tag[:250] + '...\n\nKya karna hai?'
        subprocess.run(['curl', '-s', '-X', 'POST', 'https://api.telegram.org/bot' + BT + '/sendMessage', '--data-urlencode', 'chat_id=' + CID, '--data-urlencode', 'text=' + txt, '--data-urlencode', 'reply_markup=' + kb], capture_output=True, text=True)
    
    try: os.remove(op)
    except: pass
    return rid

for i in range(NS):
    try:
        build(i)
    except Exception as e:
        print('Error: ' + str(e))
    time.sleep(2)

print('All Done!')
