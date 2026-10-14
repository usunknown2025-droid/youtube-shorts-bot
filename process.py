import json,os,requests,subprocess,time,re,asyncio
from faster_whisper import WhisperModel
from gtts import gTTS
import edge_tts

GK=os.environ['GROQ_API_KEY']
CID=os.environ.get('CHAT_ID','')
BT=os.environ.get('BOT_TOKEN','')
DUR=int(os.environ.get('DURATION','45'))
NS=int(os.environ.get('NUM_SHORTS','3'))
VN=os.environ.get('VOICE_NAME','en-US-DavisNeural')
TOPIC=os.environ.get('TOPIC','')
SU=os.environ.get('SUPABASE_URL','').rstrip('/')
SK=os.environ.get('SUPABASE_KEY','')

def dur(p):
    try:
        r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',p],capture_output=True,text=True)
        return float(r.stdout.strip())
    except:return 10.0

def gq(p,mt=2000,t=0.3,jm=False):
    u='https://api.groq.com/openai/v1/chat/completions'
    h={'Authorization':'Bearer '+GK,'Content-Type':'application/json'}
    pl={'model':'openai/gpt-oss-120b','messages':[{'role':'system','content':'Respond with valid JSON only.'},{'role':'user','content':p}],'temperature':t,'max_tokens':mt}
    if jm:pl['response_format']={'type':'json_object'}
    for _ in range(3):
        try:
            r=requests.post(u,headers=h,json=pl,timeout=90).json()
            if 'choices' in r:return r['choices'][0]['message']['content']
            if 'rate limit' in str(r).lower():time.sleep(60)
            else:time.sleep(5)
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
        if s>=0 and e>s:c=c[s:e+1]
        return json.loads(c)
    except:return None

def sb(fid,ti,de,tg,n,sc='',vs=''):
    u=SU+'/rest/v1/pending_shorts'
    h={'apikey':SK,'Authorization':'Bearer '+SK,'Content-Type':'application/json','Prefer':'return=representation'}
    data={'chat_id':CID,'file_id':fid,'title':ti,'description':de,'tags':tg,'status':'pending','short_number':n,'upload_status':'pending','content_type':'mrbeast','script':sc,'voice_style':vs}
    try:
        r=requests.post(u,headers=h,json=data,timeout=30).json()
        if isinstance(r,list) and r:return r[0].get('id')
    except:pass
    return None

def tts(scr,path):
    async def g():
        c=edge_tts.Communicate(scr,VN)
        await c.save(path)
    try:
        asyncio.run(g())
        if os.path.getsize(path)>1000:return True
    except:pass
    try:
        gTTS(text=scr,lang='en',slow=False).save(path)
        return os.path.getsize(path)>1000
    except:return False

def atime(s):
    return str(int(s//3600))+':'+str(int((s%3600)//60)).zfill(2)+':'+('%05.2f'%(s%60))

def wrap(t,mc=18):
    ws=t.split();ls=[];c=''
    for w in ws:
        if len(c)+len(w)+1<=mc:c=(c+' '+w).strip()
        else:
            if c:ls.append(c)
            c=w
    if c:ls.append(c)
    return '\\N'.join(ls[-2:])

def mksubs(com,td,segs,atd=None):
    if atd is None:atd=td
    L=['[Script Info]','ScriptType: v4.00+','PlayResX: 720','PlayResY: 1280','WrapStyle: 0','ScaledBorderAndShadow: yes','','[V4+ Styles]','Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding','Style: Commentary,Arial,45,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,3,8,30,30,700,1','Style: Caption,Arial,80,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,3,2,30,30,270,1','','[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    ws=com.split()
    if ws:
        wd=atd/len(ws);gr=[]
        for i,w in enumerate(ws):
            gr.append(w);a=i*wd;b=(i+1)*wd
            if b<=a:b=a+0.2
            L.append('Dialogue: 0,'+atime(a)+','+atime(b)+',Commentary,,0,0,0,,'+' '.join(gr))
    for sg in segs:
        sw=sg.get('words',[])
        if not sw:
            st=sg.get('text','').strip()
            if st:
                a=sg.get('start',0)+td;b=sg.get('end',0)+td
                if b>a:L.append('Dialogue: 0,'+atime(a)+','+atime(b)+',Caption,,0,0,0,,'+wrap(st))
            continue
        gr=[]
        for i,w in enumerate(sw):
            gr.append(w['word'].strip());a=w['start']+td
            b=sw[i+1]['start']+td if i+1<len(sw) else w['end']+td
            if b<=a:b=a+0.3
            L.append('Dialogue: 0,'+atime(a)+','+atime(b)+',Caption,,0,0,0,,'+wrap(' '.join(gr)))
    return '\n'.join(L)

def hooktext(ti):
    c=re.sub(r'#\w+','',ti).strip()
    st=['the','a','an','and','or','of','in','on','to','for','is','was','with','at','by']
    ws=[w for w in c.split() if w.lower() not in st][:3]
    h=' '.join(ws).upper()
    h=re.sub(r'[^A-Z0-9 !?]','',h)
    return h[:25].strip() or 'WATCH THIS'

print('STEP 1: Whisper')
m=WhisperModel('tiny',device='cpu',compute_type='int8')
segs,_=m.transcribe('audio.wav',task='translate',word_timestamps=True)
sd=[];tw=0
for s in segs:
    sw=[]
    if s.words:
        for w in s.words:
            sw.append({'start':w.start,'end':w.end,'word':w.word});tw+=1
    sd.append({'start':s.start,'end':s.end,'text':s.text.strip(),'words':sw})
vtd=sd[-1]['end'] if sd else 60
print('Words: '+str(tw)+' Dur: '+str(round(vtd,1))+'s')

print('STEP 2: Moments')
mp=int(vtd//DUR);tm=min(NS,mp)
ct=' '.join([s['text'] for s in sd])[:4000]
p='Find '+str(tm)+' viral moments (~'+str(DUR)+'s each, no overlap). Return JSON: {"moments":[{"start":12.5,"end":57.5,"reason":"why"}]}\n\n'+ct
r=gq(p,1500,0.3,True)
am=[]
if r:
    md=pj(r)
    if md:am=md.get('moments',[])
if len(am)<tm:
    es=set(int(x.get('start',0)) for x in am)
    for i in range(tm):
        cs=int(i*(vtd-DUR)/max(1,tm-1)) if tm>1 else 0
        ce=cs+DUR
        if cs in es:continue
        ov=False
        for x in am:
            if not(ce<=float(x.get('start',0)) or cs>=float(x.get('end',0))):ov=True;break
        if not ov:am.append({'start':cs,'end':ce,'reason':'fb'})
        if len(am)>=tm:break
am.sort(key=lambda x:x.get('start',0))
fl=[]
for x in am:
    ov=False
    for f in fl:
        if not(x['end']<=f['start'] or x['start']>=f['end']):ov=True;break
    if not ov:fl.append(x)
    if len(fl)>=tm:break
moments=fl[:tm] or [{'start':0,'end':DUR,'reason':'fb'}]
print('Got '+str(len(moments))+' moments')

for idx,mom in enumerate(moments):
    print('SHORT '+str(idx+1)+'/'+str(len(moments)))
    st=float(mom['start']);en=float(mom['end']);durclip=en-st
    msegs=[]
    for sg in sd:
        if sg['end']<st or sg['start']>en:continue
        nw={'start':max(sg['start'],st)-st,'end':min(sg['end'],en)-st,'text':sg['text'],'words':[]}
        for w in sg.get('words',[]):
            if w['end']<st or w['start']>en:continue
            nw['words'].append({'start':max(w['start'],st)-st,'end':min(w['end'],en)-st,'word':w['word']})
        if nw['end']>nw['start']:msegs.append(nw)
    if not msegs:continue
    mt=' '.join([s['text'] for s in msegs])
    
    cp='Write short ENGLISH commentary (max 35 words). Describe SPECIFIC action. End with CTA like "Comment what you think!". Segment: '+mt[:800]
    com='Check out this amazing moment! Comment what you think!'
    for _ in range(3):
        r=gq(cp,150,0.7)
        if r:
            t=r.strip()
            if t:com=t;break
        time.sleep(5)
    com=re.sub(r'["\'\n\r]',' ',com).strip()[:300]
    print('Com: '+com[:80])
    
    tp='YouTube Shorts metadata. Topic: '+(TOPIC or 'video content')+'\nTranscript: '+mt[:800]+'\nCommentary: '+com[:300]+'\nRules:\n- Title specific to content + end "#Shorts #Viral #MrBeast #Trending"\n- Desc: 2-3 lines + blank + 15-20 hashtags\n- Tags: 15 minimum\nReturn JSON: {"title":"...","description":"...","tags":["t1"]}'
    ti='Viral Moment #Shorts #Viral #MrBeast #Trending'
    de='Viral moment!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing'
    tgs='shorts, viral, trending, mrbeast, youtube shorts, must watch, explore, fyp, viral clip, usa, amazing, funny, wow, best, top'
    r=gq(tp,900,0.5,True)
    if r:
        mt_d=pj(r)
        if mt_d:
            ti=mt_d.get('title','')
            for h in ['#Shorts','#Viral','#MrBeast','#Trending']:
                if h.lower() not in ti.lower():ti=ti.rstrip()+' '+h
            de=mt_d.get('description','')
            if len(re.findall(r'#\w+',de))<15:
                for b in ['#MrBeast','#Shorts','#Viral','#Trending','#YouTubeShorts','#ViralClip','#USA','#MustWatch','#Explore','#ShortsFeed','#FYP','#ViralVideo','#TrendingNow','#ExploreMore','#Amazing']:
                    if b.lower() not in de.lower():de+='\n'+b
            tgd=mt_d.get('tags',[])
            if len(tgd)<15:
                for b in ['shorts','viral','trending','mrbeast','youtube shorts','must watch','explore','fyp','viral clip','usa','amazing','funny','wow','best','top']:
                    if b not in tgd and len(tgd)<15:tgd.append(b)
            tgs=', '.join(tgd)
    print('Ti: '+ti[:80])
    
    vp='v_'+str(idx)+'.mp3'
    if not tts(com,vp):
        subprocess.run(['ffmpeg','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','30','-q:a','9','-acodec','libmp3lame',vp])
    atd=dur(vp);td=atd+0.4
    
    ap='s_'+str(idx)+'.ass'
    open(ap,'w',encoding='utf-8').write(mksubs(com,td,msegs,atd))
    
    hp='h_'+str(idx)+'.jpg'
    ho=min(2.0,durclip*0.3);ht=st+ho
    subprocess.run(['ffmpeg','-y','-ss',str(ht),'-i','video.mp4','-vframes','1','-vf','scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1','-q:v','2',hp],capture_output=True)
    htx=hooktext(ti)
    print('Hook: '+htx)
    fp='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    
    op='short_'+str(idx)+'.mp4'
    vf='[2:v]fps=30,scale=720:1280,setsar=1,drawtext=text=\''+htx+'\':fontcolor=Yellow:fontsize=58:borderw=6:bordercolor=Black:box=1:boxcolor=Black@0.6:boxborderw=15:x=(w-text_w)/2:y=h*0.12:fontfile='+fp+'[hv];[0:v]crop=ih*9/16:ih,scale=720:1280:flags=lanczos,setsar=1,fps=30[v0];[hv][v0]concat=n=2:v=1:a=0[vc];[vc]ass='+ap+'[v]'
    af='[1:a]volume=1.0[t];[0:a]volume=0.2[o];[t][o]concat=n=2:v=0:a=1[a]'
    subprocess.run(['ffmpeg','-y','-ss',str(st),'-t',str(durclip),'-i','video.mp4','-i',vp,'-loop','1','-t',str(td),'-i',hp,'-filter_complex',vf+';'+af,'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','24','-c:a','aac','-b:a','128k',op],capture_output=True)
    try:os.remove(hp)
    except:pass
    
    tg=subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendVideo','-F','chat_id='+CID,'-F','video=@'+op,'-F','caption=Short '+str(idx+1)+'/'+str(len(moments))],capture_output=True,text=True)
    fid=None
    try:
        j=json.loads(tg.stdout)
        if j.get('ok'):fid=j['result']['video']['file_id']
    except:pass
    if not fid:continue
    
    rid=sb(fid,ti,de,tgs,idx+1,com,VN)
    print('Row: '+str(rid))
    if not rid:continue
    
    kb=json.dumps({'inline_keyboard':[[{'text':'✅ Upload','callback_data':'approve_'+str(rid)},{'text':'📅 Schedule','callback_data':'schedule_'+str(rid)}],[{'text':'✏️ Custom','callback_data':'custom_'+str(rid)},{'text':'❌ Skip','callback_data':'skip_'+str(rid)}]]})
    txt='📝 *Short '+str(idx+1)+'/'+str(len(moments))+'*\n\n'
    if TOPIC:txt+='🎬 Topic: '+TOPIC+'\n\n'
    txt+='📄 Title: '+ti+'\n\n📝 Description: '+de[:400]+'...\n\n🏷️ Tags: '+tgs[:300]+'...\n\nKya karna hai?'
    subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendMessage','-d','chat_id='+CID,'-d','text='+txt,'-d','parse_mode=Markdown','-d','reply_markup='+kb],capture_output=True,text=True)
    
    pt='🎨 CHATGPT THUMBNAIL PROMPT for Short '+str(idx+1)+'\n\nCopy this and paste in ChatGPT:\n\nYou are a MrBeast-style YouTube Shorts thumbnail designer. Generate 6 DIFFERENT thumbnails for:\n\nVIDEO TOPIC: '+re.sub(r'#\w+','',ti).strip()+'\n\nRULES:\n1. Real human face with SHOCKED or EXCITED expression\n2. BIG BOLD YELLOW text with THICK BLACK OUTLINE\n3. Large EMOJI in corner\n4. RED CIRCLE or RED ARROW pointing to key detail\n5. HIGH CONTRAST, saturated vibrant colors\n6. Format: 9:16 vertical (720x1280)\n\nSTYLES: 1-Face+Big Text+Emoji, 2-Action+Red Circle, 3-Face+Text+Red Arrow, 4-Text-Heavy+Small Face, 5-Before/After Split, 6-Dramatic Zoom+Text\n\nFor each: generate image, label "Style 1", "Style 2" etc.\nOutput all 6 images so I can compare.'
    subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendMessage','-d','chat_id='+CID,'-d','text='+pt],capture_output=True,text=True)
    
    time.sleep(3)
    try:
        os.remove(vp);os.remove(ap)
    except:pass

print('All Done!')
