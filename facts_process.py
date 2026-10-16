import json,os,requests,subprocess,time,re,asyncio,random,urllib.parse
import edge_tts

GK=os.environ['GROQ_API_KEY']
CID=os.environ.get('CHAT_ID','')
BT=os.environ.get('BOT_TOKEN','')
VN=os.environ.get('VOICE_NAME','en-GB-RyanNeural')
CAT=os.environ.get('CATEGORY','space')
CUSTOM_CAT=os.environ.get('CUSTOM_CATEGORY','')
NF=int(os.environ.get('NUM_FACTS','5'))
PK=os.environ.get('PIXABAY_API_KEY','')
SU=os.environ.get('SUPABASE_URL','').rstrip('/')
SK=os.environ.get('SUPABASE_KEY','')

CAT_KW={
'space':'galaxy nebula stars planets cosmos space',
'animals':'wildlife nature animals ocean forest',
'history':'ancient ruins old architecture historical',
'science':'laboratory molecules technology science',
'funny':'funny cats dogs comedy cute animals'
}

SUBTOPICS={
'space':['black holes','mars missions','the sun','galaxies','exoplanets','space travel','asteroids','jupiter','saturn','venus','the moon','space stations','nebulae','cosmic rays','big bang','dark matter','milky way','voyager probes','comets','solar system'],
'history':['ancient egypt','roman empire','mongol empire','renaissance','bronze age','vikings','medieval europe','silk road','ancient greece','maya civilization','aztec empire','inca empire','persian empire','ottoman empire','industrial revolution','world war one','world war two','cold war','age of exploration','ancient china'],
'animals':['ocean creatures','big cats','arctic wildlife','rainforest animals','birds of prey','reptiles','insects','deep sea creatures','african safari','amazon jungle','australian wildlife','endangered species','prehistoric animals','polar bears','whales','sharks','elephants','primates','wild canines','desert animals'],
'science':['quantum physics','dna','black holes','chemistry','brain science','evolution','cells','physics laws','space science','medicine','vaccines','renewable energy','artificial intelligence','robots','nanotechnology','biotechnology','climate science','oceanography','geology','meteorology'],
'funny':['funny cats','funny dogs','silly animals','funny babies','awkward moments','animal bloopers','funny sounds','unexpected humor','comedy wildlife','fails compilation','funny sports','funny food','pet antics','animal reactions','pranks gone wrong','funny accidents','comedy skits','stand up comedy','funny pranks','silly jokes']
}

def gq(p,mt=1500,t=0.85,jm=False):
    u='https://api.groq.com/openai/v1/chat/completions'
    h={'Authorization':'Bearer '+GK,'Content-Type':'application/json'}
    pl={'model':'openai/gpt-oss-120b','messages':[{'role':'user','content':p}],'temperature':t,'max_tokens':mt}
    if jm:pl['response_format']={'type':'json_object'}
    for _ in range(3):
        try:
            r=requests.post(u,headers=h,json=pl,timeout=90).json()
            if 'choices' in r:return r['choices'][0]['message']['content']
            time.sleep(5)
        except:time.sleep(5)
    return None

def pj(t):
    if not t:return None
    try:
        c=t.strip()
        if c.startswith('```'):
            c=c.split('```')[1]
            if c.startswith('json'):c=c[4:]
        s=c.find('{');e=c.rfind('}')
        return json.loads(c[s:e+1])
    except:return None

def dwn(url,path):
    try:
        r=requests.get(url,timeout=120,stream=True)
        if r.status_code==200:
            with open(path,'wb') as f:
                for c in r.iter_content(8192):f.write(c)
            return os.path.getsize(path)>5000
    except:pass
    return False

def probe(p):
    try:
        r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',p],capture_output=True,text=True)
        return float(r.stdout.strip())
    except:return 0

def get_vids(kw,count=5):
    vids=[]
    for _ in range(10):
        try:
            r=requests.get('https://pixabay.com/api/videos/',params={'key':PK,'q':kw,'per_page':5,'safesearch':'true','video_type':'film'},timeout=30).json()
            if 'hits' in r:
                for h in r['hits']:
                    u=h['videos'].get('medium',{}).get('url') or h['videos'].get('small',{}).get('url')
                    if u and u not in vids:vids.append(u)
        except:pass
        if len(vids)>=count:break
        time.sleep(0.3)
    return vids[:count]

def clip(inp,out,dur):
    td=probe(inp)
    if td<dur+0.3:return False
    st=random.uniform(0,td-dur-0.2)
    fx=random.choice(['eq=contrast=1.2:saturation=1.4:brightness=0.05','eq=contrast=1.25:saturation=1.45','eq=contrast=1.15:saturation=1.3,unsharp=5:5:1.0'])
    vf='scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,'+fx+',fps=30,setsar=1,format=yuv420p'
    r=subprocess.run(['ffmpeg','-y','-ss',str(st),'-t',str(dur),'-i',inp,'-vf',vf,'-c:v','libx264','-preset','fast','-crf','23','-an',out],capture_output=True)
    return r.returncode==0 and os.path.exists(out)

def tts_with_timing(text, path):
    async def g():
        c = edge_tts.Communicate(text, VN)
        words = []
        with open(path, 'wb') as f:
            async for chunk in c.stream():
                if chunk['type'] == 'audio':
                    f.write(chunk['data'])
                elif chunk['type'] == 'WordBoundary':
                    words.append({
                        'text': chunk['text'],
                        'offset': chunk['offset'] / 10000000.0,
                        'duration': chunk['duration'] / 10000000.0
                    })
        return words
    try:
        return asyncio.run(g())
    except Exception as e:
        print('TTS error: ' + str(e))
        return []

def estimate_word_times(text, total_duration):
    words = [w for w in text.split() if w.strip()]
    if not words:
        return []
    total_weight = sum(len(w) + 1 for w in words)
    times = []
    t = 0.0
    for w in words:
        dur = ((len(w) + 1) / total_weight) * total_duration
        times.append({'text': w, 'offset': t, 'duration': dur})
        t += dur
    return times

def atime(s):
    if s < 0:
        s = 0
    return str(int(s // 3600)) + ':' + str(int((s % 3600) // 60)).zfill(2) + ':' + ('%05.2f' % (s % 60))

def get_used_facts(topic, limit=500):
    if not SU or not SK:
        return []
    try:
        r = requests.get(
            SU + '/rest/v1/used_facts',
            headers={'apikey': SK, 'Authorization': 'Bearer ' + SK},
            params={'topic': 'eq.' + topic, 'select': 'fact_text', 'order': 'created_at.desc', 'limit': str(limit)},
            timeout=30
        ).json()
        if isinstance(r, list):
            return [item.get('fact_text', '') for item in r if item.get('fact_text')]
    except Exception as e:
        print('Used facts fetch error: ' + str(e))
    return []

def save_used_facts(topic, facts):
    if not SU or not SK:
        return
    rows = [{'topic': topic, 'fact_text': f} for f in facts if f]
    if not rows:
        return
    try:
        requests.post(
            SU + '/rest/v1/used_facts',
            headers={'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'},
            json=rows,
            timeout=30
        )
        print('Saved ' + str(len(rows)) + ' facts to history')
    except Exception as e:
        print('Save used facts error: ' + str(e))

def get_used_subtopics(topic, limit=200):
    if not SU or not SK:
        return []
    try:
        r = requests.get(
            SU + '/rest/v1/used_subtopics',
            headers={'apikey': SK, 'Authorization': 'Bearer ' + SK},
            params={'topic': 'eq.' + topic, 'select': 'subtopic', 'order': 'created_at.desc', 'limit': str(limit)},
            timeout=30
        ).json()
        if isinstance(r, list):
            return [item.get('subtopic', '') for item in r if item.get('subtopic')]
    except Exception as e:
        print('Used subtopics fetch error: ' + str(e))
    return []

def save_used_subtopic(topic, subtopic):
    if not SU or not SK:
        return
    try:
        requests.post(
            SU + '/rest/v1/used_subtopics',
            headers={'apikey': SK, 'Authorization': 'Bearer ' + SK, 'Content-Type': 'application/json'},
            json=[{'topic': topic, 'subtopic': subtopic}],
            timeout=30
        )
        print('Saved subtopic: ' + subtopic)
    except Exception as e:
        print('Save subtopic error: ' + str(e))

def mksubs(facts, word_times, fact_timings):
    L = [
        '[Script Info]',
        'ScriptType: v4.00+',
        'PlayResX: 720',
        'PlayResY: 1280',
        'WrapStyle: 0',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        'Style: Fact,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,25,25,300,1',
        '',
        '[Events]',
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
    ]
    if not word_times:
        for i, f in enumerate(facts):
            if i < len(fact_timings):
                s, e = fact_timings[i]
            else:
                s, e = 0, 2
            L.append('Dialogue: 0,' + atime(s) + ',' + atime(e) + ',Fact,,0,0,0,,' + f.upper())
        return '\n'.join(L)
    all_words = []
    for fact in facts:
        for w in fact.split():
            if w.strip():
                all_words.append(w)
    CHUNK = 4
    for i in range(0, len(all_words), CHUNK):
        chunk = all_words[i:i+CHUNK]
        if i + len(chunk) - 1 >= len(word_times):
            break
        start = word_times[i]['offset']
        last = word_times[i + len(chunk) - 1]
        end = last['offset'] + last['duration'] + 0.15
        mid = (len(chunk) + 1) // 2
        line1 = ' '.join(w.upper() for w in chunk[:mid])
        line2 = ' '.join(w.upper() for w in chunk[mid:])
        text = line1 + '\\N' + line2
        L.append('Dialogue: 0,' + atime(start) + ',' + atime(end) + ',Fact,,0,0,0,,' + text)
    return '\n'.join(L)

def sb(fid,ti,de,tg):
    u=SU+'/rest/v1/pending_shorts'
    h={'apikey':SK,'Authorization':'Bearer '+SK,'Content-Type':'application/json','Prefer':'return=representation'}
    data={'chat_id':CID,'file_id':fid,'title':ti,'description':de,'tags':tg,'status':'pending','short_number':1,'upload_status':'pending','content_type':'facts','script':CAT,'voice_style':VN}
    try:
        r=requests.post(u,headers=h,json=data,timeout=30).json()
        if isinstance(r,list) and r:return r[0].get('id')
    except:pass
    return None

print('FACTS GENERATOR (Connected)')
print('Category: '+CAT+' Facts: '+str(NF))

if CUSTOM_CAT:
    topic_name=CUSTOM_CAT
    subtopic=topic_name
    kw=topic_name+' nature mystery'
else:
    topic_name=CAT
    used_subtopics=get_used_subtopics(topic_name,200)
    print('Used subtopics: '+str(len(used_subtopics)))
    all_sub=SUBTOPICS.get(CAT,[])
    available=[s for s in all_sub if s.lower() not in [u.lower() for u in used_subtopics]]
    if not available:
        print('All subtopics used! Resetting cycle...')
        available=all_sub
    subtopic=random.choice(available)
    save_used_subtopic(topic_name,subtopic)
    kw=subtopic+' '+CAT_KW.get(CAT,'nature universe')

print('Topic: '+topic_name)
print('Subtopic: '+subtopic)

print('Fetching previously used facts...')
used_facts = get_used_facts(topic_name, 500)
print('Already used: ' + str(len(used_facts)) + ' facts')

print('STEP 1: Generate connected facts')
seed = random.randint(10000, 99999)
p = 'Generate ' + str(NF) + ' CONNECTED facts about "' + subtopic + '" (part of ' + topic_name + ' category) that flow like a mini-story.\n\n'
p += 'Random seed: ' + str(seed) + '\n\n'
p += 'CRITICAL RULES:\n'
p += '1. Each fact MUST connect to the previous one\n'
p += '2. Fact 2 should build on Fact 1, Fact 3 on Fact 2, etc.\n'
p += '3. They should feel like chapters of a single story\n'
p += '4. NO random unrelated facts\n'
p += '5. Each fact: 6-9 words maximum (SHORT!)\n'
p += '6. Shocking, interesting, viral-worthy\n'
p += '7. Focus ONLY on "' + subtopic + '" — do NOT wander into other ' + topic_name + ' topics\n\n'
if used_facts:
    p += 'DO NOT REPEAT OR REPHRASE THESE ALREADY-USED FACTS:\n'
    for u in used_facts[:100]:
        p += '- ' + u + '\n'
    p += '\nGenerate COMPLETELY NEW and UNIQUE facts.\n\n'
p += 'Return JSON: {"facts":["fact1","fact2",...]}'
r=gq(p,1200,0.95,True)
facts=[]
if r:
    d=pj(r)
    if d:facts=d.get('facts',[])
if facts and used_facts:
    used_lower=[u.lower().strip() for u in used_facts]
    fresh=[f for f in facts if f.lower().strip() not in used_lower]
    if len(fresh)<NF:
        print('Regenerating (duplicates found)...')
        p2=p+'\n\nYour previous output had duplicates. Generate entirely different facts.'
        r2=gq(p2,1200,1.0,True)
        if r2:
            d2=pj(r2)
            if d2:
                facts=d2.get('facts',[])
        else:
            facts=fresh
    else:
        facts=fresh
if not facts:
    facts=['Fact 1 about '+subtopic,'Fact 2 building on fact 1','Fact 3 continuing the story','Fact 4 adds detail','Fact 5 concludes']
facts=facts[:NF]
for i,f in enumerate(facts):print('Fact '+str(i+1)+': '+f)

print('Saving facts to history EARLY')
save_used_facts(topic_name, facts)

print('STEP 2: Voiceover with word timing')
vp='voice.mp3'
full='. '.join(facts)+'.'
word_times = tts_with_timing(full, vp)
if not os.path.exists(vp) or os.path.getsize(vp) < 1000:
    print('TTS failed, fallback to silence')
    subprocess.run(['ffmpeg','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t',str(NF*4),'-q:a','9','-acodec','libmp3lame',vp])
    word_times = []
atd=probe(vp)
print('Audio: '+str(round(atd,1))+'s, words captured: '+str(len(word_times)))
if not word_times:
    print('Word boundaries missing — estimating from duration')
    word_times = estimate_word_times(full, atd)
    print('Estimated ' + str(len(word_times)) + ' word timings')

fact_timings = []
if word_times:
    wi = 0
    for fact in facts:
        fw = [w for w in fact.split() if w.strip()]
        n = len(fw)
        if n == 0:
            continue
        if wi + n <= len(word_times):
            start = word_times[wi]['offset']
            last = word_times[wi + n - 1]
            end = last['offset'] + last['duration']
        elif wi < len(word_times):
            start = word_times[wi]['offset']
            end = atd
        else:
            start = atd
            end = start + 1
        fact_timings.append((start, end))
        wi += n
else:
    pt = atd / max(len(facts), 1)
    fact_timings = [(i * pt, (i + 1) * pt) for i in range(len(facts))]

print('STEP 3: Download stock videos')
urls=get_vids(kw,NF)
print('Got '+str(len(urls))+' videos')

print('STEP 4: Create clips')
per=atd/NF
clips=[]
for i,u in enumerate(urls):
    p='c_'+str(i)+'.mp4'
    if dwn(u,p):
        cp='cc_'+str(i)+'.mp4'
        if clip(p,cp,per):clips.append(cp)
        try:os.remove(p)
        except:pass
    if len(clips)>=NF:break
print('Clips: '+str(len(clips)))

if len(clips)<2:
    print('Not enough clips');exit(1)

print('STEP 5: Concat + captions')
open('l.txt','w').write('\n'.join("file '"+os.path.abspath(c)+"'" for c in clips))
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i','l.txt','-c','copy','raw.mp4'],capture_output=True)
ap='s.ass'
open(ap,'w',encoding='utf-8').write(mksubs(facts, word_times, fact_timings))
op='facts_short.mp4'
subprocess.run(['ffmpeg','-y','-i','raw.mp4','-i',vp,'-filter_complex','[0:v]ass='+ap+'[v];[1:a]volume=1.0[a]','-map','[v]','-map','[a]','-shortest','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','128k',op],capture_output=True)
for c in clips:
    try:os.remove(c)
    except:pass
try:os.remove('l.txt');os.remove('raw.mp4');os.remove(ap)
except:pass
if not os.path.exists(op):
    print('Render failed');exit(1)
print('Video: '+op)
print('STEP 7: Metadata')
FACTS_TAGS = {
    'space': ['space facts', 'universe', 'galaxy', 'astronomy', 'cosmos', 'nasa', 'planets', 'stars', 'space exploration', 'science facts', 'did you know', 'educational', 'space science', 'cosmology', 'astrophysics'],
    'animals': ['animal facts', 'wildlife', 'nature', 'animal kingdom', 'wild animals', 'nature facts', 'amazing animals', 'zoology', 'animal behavior', 'nature lovers', 'did you know', 'educational', 'wildlife facts', 'animals', 'wild nature'],
    'history': ['history facts', 'historical', 'ancient', 'history', 'did you know', 'past', 'civilization', 'historical facts', 'ancient history', 'world history', 'educational', 'history channel', 'ancient civilization', 'historical events', 'history lover'],
    'science': ['science facts', 'scientific', 'physics', 'chemistry', 'biology', 'science', 'experiment', 'discovery', 'science education', 'stem', 'did you know', 'educational', 'science geeks', 'science lover', 'amazing science'],
    'funny': ['funny facts', 'amazing facts', 'weird facts', 'fun facts', 'hilarious', 'comedy', 'entertaining', 'surprising facts', 'unbelievable', 'interesting facts', 'did you know', 'educational', 'fun trivia', 'random facts', 'wow facts'],
}
FACTS_HASHTAGS = {
    'space': ['#Facts', '#Space', '#Universe', '#Astronomy', '#Cosmos', '#NASA', '#Galaxy', '#DidYouKnow', '#Education', '#Learning', '#Science', '#Knowledge', '#Explore', '#SpaceFacts', '#Amazing'],
    'animals': ['#Facts', '#Animals', '#Wildlife', '#Nature', '#AnimalKingdom', '#DidYouKnow', '#Education', '#Learning', '#AmazingAnimals', '#NatureFacts', '#Knowledge', '#Explore', '#WildAnimals', '#Zoology', '#Interesting'],
    'history': ['#Facts', '#History', '#Ancient', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#Historical', '#Civilization', '#WorldHistory', '#Past', '#Explore', '#AncientHistory', '#HistoryFacts', '#Interesting'],
    'science': ['#Facts', '#Science', '#Physics', '#Chemistry', '#Biology', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#STEM', '#Discovery', '#Explore', '#ScienceFacts', '#Scientific', '#Amazing'],
    'funny': ['#Facts', '#FunFacts', '#AmazingFacts', '#DidYouKnow', '#WeirdFacts', '#Interesting', '#Education', '#Learning', '#Knowledge', '#Explore', '#Funny', '#Surprising', '#Unbelievable', '#FunFactsDaily', '#Wow'],
}
if CUSTOM_CAT:
    cat_clean = CUSTOM_CAT.replace(' ', '')
    fallback_tags = ['facts', 'did you know', 'education', 'learning', 'knowledge', CUSTOM_CAT, CUSTOM_CAT + ' facts', 'amazing ' + CUSTOM_CAT, 'interesting ' + CUSTOM_CAT, 'top ' + CUSTOM_CAT, 'educational', 'discovery', 'nature facts', 'explore', 'amazing facts']
    fallback_hashtags = ['#Facts', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#Amazing', '#Explore', '#Interesting', '#TopFacts', '#' + cat_clean, '#' + cat_clean + 'Facts', '#Discovery', '#Nature', '#Wildlife', '#MustWatch']
else:
    fallback_tags = FACTS_TAGS.get(CAT, FACTS_TAGS['space'])
    fallback_hashtags = FACTS_HASHTAGS.get(CAT, FACTS_HASHTAGS['space'])

tp = 'Write YouTube Shorts metadata for a "' + subtopic + '" FACTS video (category: ' + topic_name + ').\n\n'
tp += 'CRITICAL RULES:\n'
tp += '1. Title: max 60 chars, catchy but educational. End with 4 hashtags: #Shorts #Facts #[SubtopicSpecific] #DidYouKnow\n'
tp += '2. DO NOT use #MrBeast, #Viral, #Trending, #FYP\n'
tp += '3. Description: 2-3 lines + blank line + 15 facts hashtags\n'
tp += '4. Tags: 15 comma-separated SEO tags\n'
tp += '5. NO tags like: mrbeast, viral, trending, fyp, shorts\n\n'
tp += 'Return JSON: {"title":"...","description":"...","tags":["tag1","tag2",...]}'

ti = subtopic.title() + ' Facts #Shorts #Facts #' + subtopic.replace(' ', '').title() + ' #DidYouKnow'
de = 'Mind-blowing ' + subtopic + ' facts you never knew!\n\n' + ' '.join(fallback_hashtags)
tgs = ', '.join(fallback_tags)

r = gq(tp, 900, 0.5, True)
if r:
    md = pj(r)
    if md:
        ti = md.get('title', '') or ti
        for bad in ['#MrBeast', '#Viral', '#Trending', '#FYP', '#ViralVideo', '#TrendingNow', '#ViralClip', '#ShortsFeed']:
            ti = ti.replace(bad, '')
        ti = re.sub(r'\s+', ' ', ti).strip()
        for h in ['#Shorts', '#Facts', '#DidYouKnow']:
            if h.lower() not in ti.lower():
                ti = ti.rstrip() + ' ' + h
        de = md.get('description', '') or de
        for bad in ['#MrBeast', '#Viral', '#Trending', '#FYP', '#ViralVideo', '#TrendingNow', '#ViralClip', '#ShortsFeed']:
            de = de.replace(bad, '')
        if len(re.findall(r'#\w+', de)) < 15:
            for b in fallback_hashtags:
                if b.lower() not in de.lower() and len(re.findall(r'#\w+', de)) < 15:
                    de += ' ' + b
        tgd = md.get('tags', []) or []
        bad_tags = ['mrbeast', 'viral', 'trending', 'fyp', 'viral video', 'shorts feed', 'shorts']
        tgd = [t for t in tgd if t.lower() not in bad_tags]
        if len(tgd) < 15:
            for b in fallback_tags:
                if b not in tgd and len(tgd) < 15:
                    tgd.append(b)
        if tgd:
            tgs = ', '.join(tgd)

print('Title: ' + ti[:80])
print('Tags: ' + tgs[:80])

print('STEP 8: Send to Telegram')
tg=subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendVideo','-F','chat_id='+CID,'-F','video=@'+op,'-F','caption='+subtopic.title()+' Facts - '+str(NF)+' facts'],capture_output=True,text=True)
fid=None
try:
    j=json.loads(tg.stdout)
    if j.get('ok'):fid=j['result']['video']['file_id']
except:pass

if fid:
    rid=sb(fid,ti,de,tgs)
    print('Row: '+str(rid))
    if rid:
        kb=json.dumps({'inline_keyboard':[[{'text':'✅ Upload','callback_data':'approve_'+str(rid)},{'text':'📅 Schedule','callback_data':'schedule_'+str(rid)}],[{'text':'✏️ Custom','callback_data':'custom_'+str(rid)},{'text':'❌ Skip','callback_data':'skip_'+str(rid)}]]})
        txt='📝 *'+subtopic.title()+' Facts*\n\n📄 Title: '+ti+'\n\n📝 Desc: '+de[:400]+'...\n\n🏷️ Tags: '+tgs[:300]+'...\n\nKya karna hai?'
        subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendMessage','-d','chat_id='+CID,'-d','text='+txt,'-d','parse_mode=Markdown','-d','reply_markup='+kb],capture_output=True,text=True)
        pt='🎨 CHATGPT THUMBNAIL PROMPT\n\nCopy this and paste in ChatGPT:\n\nYou are a YouTube Shorts thumbnail designer for a FACTS channel. Generate 6 thumbnails for:\n\nVIDEO TOPIC: '+subtopic.title()+'\n\nRULES:\n1. NO human faces — use only subject imagery, objects, animals, historical figures, nature, or 3D renders relevant to the topic\n2. BIG BOLD YELLOW text with THICK BLACK OUTLINE\n3. Large EMOJI in corner (😱🤯😮💥🔥)\n4. RED CIRCLE or ARROW highlighting an interesting detail\n5. HIGH CONTRAST vibrant colors\n6. Ultra-detailed, cinematic, hyper-realistic\n7. Format: 9:16 vertical\n\nSTYLES: Subject+Text+Emoji, Action+Circle, Object+Arrow, Text-Heavy, Before/After, Zoom+Detail\n\nOutput all 6 images.'
        subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendMessage','--data-urlencode','chat_id='+CID,'--data-urlencode','text='+pt],capture_output=True,text=True)

try:os.remove(vp);os.remove(op)
except:pass

print('All Done!')
