import json,os,requests,subprocess,time,re,asyncio,urllib.parse
from gtts import gTTS
import edge_tts

GK=os.environ['GROQ_API_KEY']
CID=os.environ.get('CHAT_ID','')
BT=os.environ.get('BOT_TOKEN','')
DUR=int(os.environ.get('DURATION','45'))
NS=int(os.environ.get('NUM_SHORTS','3'))
CAT=os.environ.get('CATEGORY','mystery')
VN=os.environ.get('VOICE_NAME','en-GB-RyanNeural')
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
        c=c.strip()
        s=c.find('{');e=c.rfind('}')
        if s>=0 and e>s:c=c[s:e+1]
        return json.loads(c)
    except:return None

def sb(fid,ti,de,tg,n,sc,vs):
    u=SU+'/rest/v1/pending_shorts'
    h={'apikey':SK,'Authorization':'Bearer '+SK,'Content-Type':'application/json','Prefer':'return=representation'}
    d={'chat_id':CID,'file_id':fid,'title':ti,'description':de,'tags':tg,'status':'pending','short_number':n,'upload_status':'pending','content_type':'mystery','script':sc,'voice_style':vs}
    try:
        r=requests.post(u,headers=h,json=d,timeout=30).json()
        if isinstance(r,list) and r:return r[0].get('id')
    except:pass
    return None

def mkscript(topic,hook):
    wc=int(DUR*2.7)
    p='Write '+str(DUR)+'-second mystery narration (~'+str(wc)+' words).\nTopic: '+topic+'\nHook: '+hook+'\nStructure: Hook+Setup+Mystery+Twist+CTA. End with "Follow for more mysteries!".\nAlso 6 dark cinematic scene descriptions for AI images.\nReturn JSON: {"script":"...","scenes":["s1","s2","s3","s4","s5","s6"]}'
    r=gq(p,1200,0.8,True)
    if r:
        d=pj(r)
        if d and d.get('script'):return d
    return {'script':hook+'. '+topic+' remains one of history\'s greatest mysteries. Follow for more mysteries!','scenes':['dark abandoned ship in foggy ocean, cinematic','old wooden deck at night','empty cabin dark','storm clouds over ocean','ship silhouette in fog','dark horizon fading']}

def genimg(sc,path,seed=42):
    try:
        cp=sc+', dark cinematic documentary style, moody atmospheric lighting, deep shadows, film grain, realistic, ultra detailed, 8k, cinematic color grading'
        u='https://image.pollinations.ai/prompt/'+urllib.parse.quote(cp)+'?width=720&height=1280&model=flux&nologo=true&seed='+str(seed)
        r=requests.get(u,timeout=180)
        if r.status_code==200 and len(r.content)>5000:
            open(path,'wb').write(r.content)
            return os.path.getsize(path)>5000
    except:pass
    return False

def genimgs(scenes,topic):
    imgs=[]
    for i,sc in enumerate(scenes[:6]):
        p='scene_'+str(i)+'.jpg'
        if genimg(sc,p,42+i*111):imgs.append(p)
        time.sleep(3)
    while len(imgs)<3:
        p='scene_fb_'+str(len(imgs))+'.jpg'
        if genimg(topic+', dark mysterious cinematic',p,999+len(imgs)):imgs.append(p)
        else:break
        time.sleep(3)
    return imgs

def genvoice(scr,path):
    try:
        async def g():
            c=edge_tts.Communicate(scr,VN)
            await c.save(path)
        asyncio.run(g())
        if os.path.getsize(path)>1000:return True
    except:pass
    try:
        gTTS(text=scr,lang='en').save(path)
        if os.path.getsize(path)>1000:return True
    except:pass
    return False

def atime(s):
    return str(int(s//3600))+':'+str(int((s%3600)//60)).zfill(2)+':'+('%05.2f'%(s%60))

def wrap(t,mc=20):
    ws=t.split();ls=[];c=''
    for w in ws:
        if len(c)+len(w)+1<=mc:c=(c+' '+w).strip()
        else:
            if c:ls.append(c)
            c=w
    if c:ls.append(c)
    return '\\N'.join(ls[-2:])

def mksubs(segs,total):
    L=['[Script Info]','ScriptType: v4.00+','PlayResX: 720','PlayResY: 1280','WrapStyle: 0','ScaledBorderAndShadow: yes','','[V4+ Styles]','Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding','Style: Caption,Arial,85,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,3,2,40,40,200,1','','[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    wps=[len(s.split()) for s in segs]
    tw=sum(wps) or 1
    ct=0
    for i,sg in enumerate(segs):
        sd=(wps[i]/tw)*total
        ws=sg.split()
        if ws:
            wd=sd/len(ws);g=[]
            for j,w in enumerate(ws):
                g.append(w);a=ct+j*wd;b=ct+(j+1)*wd
                if b<=a:b=a+0.15
                L.append('Dialogue: 0,'+atime(a)+','+atime(b)+',Caption,,0,0,0,,'+wrap(' '.join(g)))
        ct+=sd
    return '\n'.join(L)

def kbclip(img,d,out,dirn='in'):
    fr=max(int(d*30),30)
    z={'in':'min(1+0.0015*on,1.35)','out':'max(1.35-0.0015*on,1.0)'}.get(dirn,'min(1+0.0012*on,1.3)')
    cf='eq=contrast=1.15:saturation=1.25:brightness=0.02,unsharp=5:5:0.8:3:3:0.4,vignette=PI/5'
    vf='scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,zoompan=z=\''+z+'\':d='+str(fr)+':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':s=720x1280:fps=30,'+cf+',fps=30,setsar=1,format=yuv420p'
    r=subprocess.run(['ffmpeg','-y','-loop','1','-i',img,'-t',str(d),'-vf',vf,'-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p','-an',out],capture_output=True)
    return r.returncode==0 and os.path.exists(out)

def buildvid(imgs,vp,vd,ap,out):
    td=vd+0.5;n=len(imgs)
    if not n:return False
    pi=td/n;dirs=['in','out']*(n//2+1)
    clips=[]
    for i,im in enumerate(imgs):
        c='kb_'+str(i)+'.mp4'
        if kbclip(im,pi,c,dirs[i]):clips.append(c)
    if not clips:return False
    open('kb.txt','w').write('\n'.join("file '"+os.path.abspath(c)+"'" for c in clips))
    subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i','kb.txt','-c','copy','kbc.mp4'],capture_output=True)
    subprocess.run(['ffmpeg','-y','-i','kbc.mp4','-i',vp,'-filter_complex','[0:v]ass='+ap+'[v]','-map','[v]','-map','1:a','-t',str(td),'-c:v','libx264','-preset','fast','-crf','24','-c:a','aac','-b:a','128k','-shortest',out],capture_output=True)
    for c in clips:
        try:os.remove(c)
        except:pass
    try:os.remove('kbc.mp4');os.remove('kb.txt')
    except:pass
    return os.path.exists(out)

def mkmeta(topic,scr):
    p='YouTube Shorts metadata for mystery.\nTopic: '+topic+'\nScript: '+scr[:300]+'\nRules:\n- Title ends with "#Shorts #Viral #MrBeast #Trending"\n- Description: 2 lines + blank + 15 hashtags\n- Tags: 15 minimum\nReturn JSON: {"title":"...","description":"...","tags":["t1"]}'
    r=gq(p,900,0.5,True)
    if r:
        d=pj(r)
        if d:
            ti=d.get('title',topic)
            for ht in ['#Shorts','#Viral','#MrBeast','#Trending']:
                if ht.lower() not in ti.lower():ti=ti.rstrip()+' '+ht
            de=d.get('description','')
            if len(re.findall(r'#\w+',de))<15:
                for b in ['#MrBeast','#Shorts','#Viral','#Trending','#YouTubeShorts','#ViralClip','#USA','#MustWatch','#Explore','#ShortsFeed','#FYP','#ViralVideo','#TrendingNow','#ExploreMore','#Amazing','#Mystery','#Unsolved']:
                    if b.lower() not in de.lower():de+='\n'+b
            tg=d.get('tags',[])
            for b in ['mystery','unsolved','unexplained','shorts','viral','mrbeast','trending','youtube shorts','must watch','history','documentary','creepy','paranormal','haunted','ghost']:
                if b not in tg and len(tg)<15:tg.append(b)
            return ti,de,', '.join(tg)
    return topic+' #Shorts #Viral #MrBeast #Trending',topic+' remains unsolved!\n\n#MrBeast #Shorts #Viral #Trending #YouTubeShorts #ViralClip #USA #MustWatch #Explore #ShortsFeed #FYP #ViralVideo #TrendingNow #ExploreMore #Amazing #Mystery #Unsolved','mystery, unsolved, unexplained, shorts, viral, mrbeast, trending, youtube shorts, must watch, history, documentary, creepy, paranormal, haunted, ghost'

print('Starting Mystery Generator')
cats={'aliens':'alien, UFO, area 51','ghosts':'haunted house, poltergeist','ships':'ghost ship, bermuda','abandoned':'abandoned places','cursed':'cursed object','disappearances':'missing person, vanished','creatures':'bigfoot, loch ness','places':'mysterious place','ancient':'lost civilization','space':'space mystery, alien signal'}

p='Generate '+str(NS)+' mystery topics. Category: '+CAT+'. Keywords: '+cats.get(CAT,'mystery')+'. SPECIFIC, UNSOLVED, SHOCKING. Return JSON: {"topics":[{"topic":"x","hook":"y"}]}'
r=gq(p,800,0.7,True)
topics=[]
if r:
    d=pj(r)
    if d:topics=d.get('topics',[])
if not topics:
    topics=[{'topic':'The Mary Celeste','hook':'Ship found empty in 1872'},{'topic':'Dyatlov Pass','hook':'9 hikers died mysteriously'},{'topic':'Bermuda Triangle','hook':'Ships vanish here'}][:NS]
print(str(len(topics))+' topics ready')

for idx,td in enumerate(topics):
    if idx>=NS:break
    try:
        topic,hook=td['topic'],td['hook']
        print('=== SHORT '+str(idx+1)+': '+topic+' ===')
        sd=mkscript(topic,hook)
        scr=sd.get('script','')
        scenes=sd.get('scenes',[])
        vp='v_'+str(idx)+'.mp3'
        if not genvoice(scr,vp):
            subprocess.run(['ffmpeg','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t',str(DUR),'-q:a','9','-acodec','libmp3lame',vp])
        vd=dur(vp)
        print('Voice: '+str(round(vd,1))+'s')
        imgs=genimgs(scenes,topic)
        print('Images: '+str(len(imgs)))
        if len(imgs)<2:
            for i in range(3):
                p='fb_'+str(i)+'.jpg'
                if genimg(topic+', dark cinematic',p,777+i):imgs.append(p)
        if not imgs:continue
        segs=[s.strip() for s in re.split(r'(?<=[.!?])\s+',scr) if s.strip()]
        if len(segs)<len(imgs):segs=segs*len(imgs)
        segs=segs[:len(imgs)] or [scr]
        ap='s_'+str(idx)+'.ass'
        open(ap,'w',encoding='utf-8').write(mksubs(segs,vd))
        op='ms_'+str(idx)+'.mp4'
        if not buildvid(imgs,vp,vd,ap,op):
            print('Render failed');continue
        print('Video: '+op)
        ti,de,tg=mkmeta(topic,scr)
        print('Title: '+ti)
        tr=subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendVideo','-F','chat_id='+CID,'-F','video=@'+op,'-F','caption=Short '+str(idx+1)+'/'+str(NS)+' - '+topic],capture_output=True,text=True)
        fid=None
        try:
            j=json.loads(tr.stdout)
            if j.get('ok'):fid=j['result']['video']['file_id']
        except:pass
        if fid:
            rid=sb(fid,ti,de,tg,idx+1,scr,VN)
            print('Row: '+str(rid))
            if rid:
                kb=json.dumps({'inline_keyboard':[[{'text':'✅ Upload','callback_data':'approve_'+str(rid)},{'text':'📅 Schedule','callback_data':'schedule_'+str(rid)}],[{'text':'✏️ Custom','callback_data':'custom_'+str(rid)},{'text':'❌ Skip','callback_data':'skip_'+str(rid)}]]})
                txt='📝 Short '+str(idx+1)+'/'+str(NS)+'\n\n🎬 Topic: '+topic+'\n\n📄 Title: '+ti+'\n\n📝 Desc: '+de[:400]+'...\n\n🏷️ Tags: '+tg[:300]+'...\n\nKya karna hai?'
                subprocess.run(['curl','-s','-X','POST','https://api.telegram.org/bot'+BT+'/sendMessage','--data-urlencode','chat_id='+CID,'--data-urlencode','text='+txt,'--data-urlencode','reply_markup='+kb],capture_output=True,text=True)
        for f in [vp,ap,op]+imgs:
            try:os.remove(f)
            except:pass
        time.sleep(2)
    except Exception as e:
        print('Error '+str(idx+1)+': '+str(e));continue

print('All Done!')
