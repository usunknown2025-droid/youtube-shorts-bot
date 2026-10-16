print('STEP 6: Metadata')

# Facts-specific hashtags based on category
FACTS_TAGS = {
    'space': ['space facts', 'universe', 'galaxy', 'astronomy', 'cosmos', 'nasa', 'planets', 'stars', 'space exploration', 'science facts'],
    'animals': ['animal facts', 'wildlife', 'nature', 'animal kingdom', 'wild animals', 'nature facts', 'amazing animals', 'zoology', 'animal behavior', 'nature lovers'],
    'history': ['history facts', 'historical', 'ancient', 'history', 'did you know', 'past', 'civilization', 'historical facts', 'ancient history', 'world history'],
    'science': ['science facts', 'scientific', 'physics', 'chemistry', 'biology', 'science', 'experiment', 'discovery', 'science education', 'stem'],
    'funny': ['funny facts', 'amazing facts', 'weird facts', 'fun facts', 'hilarious', 'comedy', 'entertaining', 'surprising facts', 'unbelievable', 'interesting facts'],
}
FACTS_HASHTAGS = {
    'space': ['#Facts', '#Space', '#Universe', '#Astronomy', '#Cosmos', '#NASA', '#Galaxy', '#DidYouKnow', '#Education', '#Learning', '#Science', '#Knowledge', '#Explore', '#SpaceFacts', '#Amazing'],
    'animals': ['#Facts', '#Animals', '#Wildlife', '#Nature', '#AnimalKingdom', '#DidYouKnow', '#Education', '#Learning', '#AmazingAnimals', '#NatureFacts', '#Knowledge', '#Explore', '#WildAnimals', '#Zoology', '#Interesting'],
    'history': ['#Facts', '#History', '#Ancient', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#Historical', '#Civilization', '#WorldHistory', '#Past', '#Explore', '#AncientHistory', '#HistoryFacts', '#Interesting'],
    'science': ['#Facts', '#Science', '#Physics', '#Chemistry', '#Biology', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#STEM', '#Discovery', '#Explore', '#ScienceFacts', '#Scientific', '#Amazing'],
    'funny': ['#Facts', '#FunFacts', '#AmazingFacts', '#DidYouKnow', '#WeirdFacts', '#Interesting', '#Education', '#Learning', '#Knowledge', '#Explore', '#Funny', '#Surprising', '#Unbelievable', '#FunFactsDaily', '#Wow'],
}

# Get category-specific tags
if CUSTOM_CAT:
    cat_key = 'random'
    fallback_tags = ['facts', 'did you know', 'education', 'learning', 'knowledge'] + [CUSTOM_CAT, CUSTOM_CAT+' facts', 'amazing '+CUSTOM_CAT, 'interesting '+CUSTOM_CAT, 'top '+CUSTOM_CAT]
    fallback_hashtags = ['#Facts', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#Amazing', '#Explore', '#Interesting', '#TopFacts', '#MustWatch', '#'+CUSTOM_CAT.replace(' ',''), '#'+CUSTOM_CAT.replace(' ','')+'Facts', '#Nature', '#Wildlife', '#Discovery']
else:
    cat_key = CAT
    fallback_tags = FACTS_TAGS.get(CAT, ['facts', 'did you know', 'education', 'learning', 'knowledge', 'amazing facts', 'interesting facts', 'top facts', 'science facts', 'nature facts'])
    fallback_hashtags = FACTS_HASHTAGS.get(CAT, ['#Facts', '#DidYouKnow', '#Education', '#Learning', '#Knowledge', '#Amazing', '#Explore', '#Interesting', '#TopFacts', '#MustWatch'])

# Groq prompt — facts-specific
tp = 'Write YouTube Shorts metadata for a "'+topic_name+'" FACTS video.\n\n'
tp += 'RULES:\n'
tp += '1. Title: max 60 chars, catchy but educational. End with 4 hashtags: #Shorts #Facts #[CategorySpecific] #DidYouKnow\n'
tp += '2. DO NOT use #MrBeast, #Viral, #Trending, #FYP — these are for gaming/vlog channels, not facts channels\n'
tp += '3. Description: 2-3 lines describing the topic + blank line + 15 facts-specific hashtags\n'
tp += '4. Hashtags should be educational: #Facts #DidYouKnow #Education #Learning #Knowledge #[Category]\n'
tp += '5. Tags: 15 comma-separated SEO tags for facts niche (e.g., "facts", "did you know", "educational", "'+topic_name+' facts")\n'
tp += '6. NO tags like: mrbeast, viral, trending, fyp, shorts\n\n'
tp += 'Return JSON: {"title":"...","description":"...","tags":["tag1","tag2",...]}'

# Fallback title (facts style)
ti = topic_name.title() + ' Facts #Shorts #Facts #' + (topic_name.replace(' ','').title()) + ' #DidYouKnow'

# Fallback description (facts style)
de = 'Mind-blowing ' + topic_name + ' facts you never knew!\n\n' + ' '.join(fallback_hashtags)

# Fallback tags
tgs = ', '.join(fallback_tags)

# Groq call
r = gq(tp, 900, 0.5, True)
if r:
    md = pj(r)
    if md:
        # Title fix
        ti = md.get('title', '') or ti
        # Remove Mr Beast hashtags if Groq added them
        for bad in ['#MrBeast', '#Viral', '#Trending', '#FYP', '#ViralVideo', '#TrendingNow']:
            ti = ti.replace(bad, '')
        ti = ti.strip()
        # Ensure facts hashtags
        for h in ['#Shorts', '#Facts', '#DidYouKnow']:
            if h.lower() not in ti.lower():
                ti = ti.rstrip() + ' ' + h
        
        # Description fix
        de = md.get('description', '') or de
        # Remove Mr Beast hashtags
        for bad in ['#MrBeast', '#Viral', '#Trending', '#FYP', '#ViralVideo', '#TrendingNow', '#ViralClip', '#ShortsFeed']:
            de = de.replace(bad, '')
        # Ensure enough facts hashtags
        if len(re.findall(r'#\w+', de)) < 15:
            for b in fallback_hashtags:
                if b.lower() not in de.lower() and len(re.findall(r'#\w+', de)) < 15:
                    de += ' ' + b
        
        # Tags fix
        tgd = md.get('tags', []) or []
        # Remove bad tags
        bad_tags = ['mrbeast', 'viral', 'trending', 'fyp', 'viral video', 'shorts feed']
        tgd = [t for t in tgd if t.lower() not in bad_tags]
        # Add facts tags if not enough
        if len(tgd) < 15:
            for b in fallback_tags:
                if b not in tgd and len(tgd) < 15:
                    tgd.append(b)
        if tgd:
            tgs = ', '.join(tgd)

print('Title: ' + ti[:80])
print('Tags: ' + tgs[:80])
