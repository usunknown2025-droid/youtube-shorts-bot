import json, os, requests, subprocess, time, random

PK = os.environ.get('PIXABAY_API_KEY', '')
CID = os.environ.get('CHAT_ID', '')
BT = os.environ.get('BOT_TOKEN', '')
GK = os.environ.get('GROQ_API_KEY', '')
MUSIC = os.environ.get('MUSIC_URL', '')
NS = int(os.environ.get('NUM_VIDEOS', '1'))
SU = os.environ.get('SUPABASE_URL', '').rstrip('/')
SK = os.environ.get('SUPABASE_KEY', '')

SEARCH = ['cute cat', 'funny cat', 'kitten playing', 'cat jumping', 'fluffy cat', 'cat meowing']

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

def get_vids(n=10):
    seen = set(); vids = []
    for _ in range(n*3):
        if len(vids) >= n: break
        try:
            r = requests.get('https://pixabay.com/api/videos/', params={'key': PK, 'q': random.choice(SEARCH), 'per_page': 10, 'safesearch': 'true', 'video_type': 'film'}, timeout=30).json()
            if 'hits' in r:
                for h in r['hits']:
                    if h['id'] in seen: continue
                    seen.add(h['id'])
                    u = h['videos'].get('medium', {}).get('url') or h['videos'].get('small', {}).get('url')
                    if u: vids.append(u)
                    if len(vids) >= n: break
        except: pass
        time.sleep(0.3)
    return vids

def fast_clip(inp, out, dur):
    td = probe(inp)
    if td < dur + 0.2: return False
    st = random.uniform(0, td - dur - 0.1)
    fx = random.choice(['eq=contrast=1.2:saturation=1.4:brightness=0.05', 'eq=contrast=1.3:saturation=1.5', 'eq=contrast=1.15:saturation=1.3'])
    vf = 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,' + fx + ',unsharp=5:5:1.0,fps=30,setsar=1,format=yuv420p'
    r = subprocess.run(['ffmpeg', '-y', '-ss', str(st), '-t', str(dur), '-i', inp, '-vf', vf, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-an', out], capture_output=True)
    return r.returncode == 0 and os.path.exists(out)

def ftime(s):
    return str(int(s//3600)) + ':' + str(int((s%3600)//60)).zfill(2) + ':' + ('%05.2f' % (s%60))

def build_ass(texts, td, ap):
    L = ['[Script Info]','ScriptType: v4.00+','PlayResX: 720','PlayResY: 1280','WrapStyle: 0','ScaledBorderAndShadow: yes','','[V4+ Styles]','Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding','Style: Meme,Arial,90,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,3,5,40,40,40,1','','[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    pt = td / max(len(texts), 1)
    for i, t in enumerate(texts):
        L.append('Dialogue: 0,' + ftime(i*pt) + ',' + ftime((i+1)*pt) + ',Meme,,0,0,0,,' + t.upper())
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
    p = 'Generate YouTube Shorts metadata for viral cat video. Title must be funny (max 60 chars) + end with "#Shorts #Viral #MrBeast #Trending". Description: 2 lines + 15 hashtags. Tags: 15 minimum. Return JSON: {"title":"...","description":"...","tags":["t1"]}'
    r = groq(p)
    if r:
        d = pj(r)
        if d: return d
    return {'title': 'Cat Aura +1000 #Shorts #Viral #MrBeast #Trending', 'description': 'Viral cat moments!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing', 'tags': ['cat', 'funny cat', 'cute cat', 'kitten', 'viral cat', 'shorts', 'viral', 'trending', 'mrbeast', 'youtube shorts', 'must watch', 'aura', 'jumpstyle', 'meme', 'funny']}

def build(idx):
    print('JUMPSTYLE CAT ' + str(idx+1))
    urls = get_vids(10)
    if len(urls) < 4:
        print('Few videos'); return None
    
    clips = []
    for i, u in enumerate(urls[:10]):
        p = 'c_' + str(i) + '.mp4'
        if dwn(u, p):
            cp = 'cc_' + str(i) + '.mp4'
            if fast_clip(p, cp, random.uniform(0.5, 0.9)):
                clips.append(cp)
        try: os.remove(p)
        except: pass
    if len(clips) < 4:
        print('Few clips'); return None
    print(str(len(clips)) + ' clips ready')
    
    tp = 'Generate 4 SHORT funny texts (max 4 words each) for viral cat video. Style: meme like "Aura +1000", "Wait for it...", "OMG". Return JSON: {"texts":["t1","t2","t3","t4"]}'
    texts = ['Aura +1000', 'Wait for it...', 'OMG', 'Main character']
    ai = groq(tp)
    if ai:
        d = pj(ai)
        if d and d.get('texts'): texts = d['texts']
    
    open('l.txt', 'w').write('\n'.join("file '" + os.path.abspath(c) + "'" for c in clips))
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'l.txt', '-c', 'copy', 'cat.mp4'], capture_output=True)
    td = probe('cat.mp4')
    if td < 2: return None
    
    ap = 'ov.ass'
    build_ass(texts, td, ap)
    op = 'jump_' + str(idx) + '.mp4'
    
    if MUSIC:
        mp = 'm.mp3'
        if dwn(MUSIC, mp):
            subprocess.run(['ffmpeg', '-y', '-i', 'cat.mp4', '-i', mp, '-filter_complex', '[0:v]ass=' + ap + '[v];[1:a]volume=0.8[a]', '-map', '[v]', '-map', '[a]', '-shortest', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', op], capture_output=True)
            try: os.remove(mp)
            except: pass
    
    if not os.path.exists(op):
        subprocess.run(['ffmpeg', '-y', '-i', 'cat.mp4', '-vf', 'ass=' + ap, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-an', op], capture_output=True)
    
    for c in clips:
        try: os.remove(c)
        except: pass
    try: os.remove('l.txt'); os.remove('cat.mp4'); os.remove(ap)
    except: pass
    
    if not os.path.exists(op): return None
    print('Video: ' + op)
    
    tg = subprocess.run(['curl', '-s', '-X', 'POST', 'https://api.telegram.org/bot' + BT + '/sendVideo', '-F', 'chat_id=' + CID, '-F', 'video=@' + op, '-F', 'caption=Jumpstyle Cat ' + str(idx+1)], capture_output=True, text=True)
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
        txt = '🐱 Jumpstyle Cat ' + str(idx+1) + '/' + str(NS) + '\n\n📄 ' + ti + '\n\n📝 ' + de[:300] + '...\n\n🏷️ ' + tg_tag[:250] + '...\n\nKya karna hai?'
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
