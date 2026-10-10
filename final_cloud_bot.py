import os, json, tempfile, requests, time, random
from datetime import datetime
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, ImageClip
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_KEY"]
PEXELS_KEY = os.environ["PEXELS_KEY"]
HISTORY_FILE = "history.json"
LONG_TITLE = "Desi Life Official - Long Videos"
SHORT_TITLE = "Desi Life Official - Shorts"
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
FB_APP_ID = os.environ.get("FB_APP_ID", "")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET", "")
FB_USER_TOKEN = os.environ.get("FB_USER_TOKEN", "")
FB_ENABLED = False
TIKTOK_ENABLED = False
VOICE_GENDER = "male"
VOICE_NAME_MALE = "ur-PK-AsadNeural"
VOICE_NAME_FEMALE = "ur-PK-UzmaNeural"

def get_fresh_page_token():
    global FB_PAGE_TOKEN
    user_token_to_use = FB_USER_TOKEN if FB_USER_TOKEN else ""
    if FB_USER_TOKEN:
        try:
            if FB_APP_ID and FB_APP_SECRET:
                try:
                    exchange_url = f"https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id={FB_APP_ID}&client_secret={FB_APP_SECRET}&fb_exchange_token={FB_USER_TOKEN}"
                    ex_res = requests.get(exchange_url, timeout=20)
                    if ex_res.status_code == 200:
                        new_user_token = ex_res.json().get("access_token")
                        if new_user_token:
                            user_token_to_use = new_user_token
                except: pass
            url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={user_token_to_use}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                data = res.json()
                for page in data.get("data", []):
                    if str(page["id"]) == str(FB_PAGE_ID):
                        return page["access_token"]
                if data.get("data"):
                    return data["data"][0]["access_token"]
        except: pass
    return FB_PAGE_TOKEN


def generate_azure_tts(text, output_path, voice_name="ur-PK-AsadNeural"):
    """
    MS Azure TTS - PRO quality, stable
    Requires: AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in GitHub Secrets
    Free tier: 500k chars/month
    Voices: ur-PK-AsadNeural (Male), ur-PK-UzmaNeural (Female)
    """
    import os
    azure_key = os.environ.get("AZURE_SPEECH_KEY", "")
    azure_region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
    
    if not azure_key:
        print("AZURE_SPEECH_KEY not set, skipping Azure")
        return False
    
    try:
        # Method 1: Using REST API (no SDK needed, lightweight)
        import requests
        
        # Azure Speech REST API
        url = f"https://{azure_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": azure_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mp3"
        }
        
        # SSML for better prosody - 6 min ke liye perfect
        ssml = f"""
        <speak version='1.0' xml:lang='ur-PK'>
            <voice xml:lang='ur-PK' xml:gender='Male' name='{voice_name}'>
                <prosody rate='0%' pitch='0%'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """.strip()
        
        print(f"Azure TTS: {voice_name} | Region: {azure_region} | Chars: {len(text)}")
        response = requests.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=60)
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Azure TTS SUCCESS - {len(response.content)/1024:.1f} KB")
            return True
        else:
            print(f"❌ Azure TTS failed: {response.status_code} {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"Azure TTS error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_azure_tts_sdk(text, output_path, voice_name="ur-PK-AsadNeural"):
    """
    Alternative using Azure SDK (needs azure-cognitiveservices-speech pip package)
    Better for long texts
    """
    import os
    azure_key = os.environ.get("AZURE_SPEECH_KEY", "")
    azure_region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
    
    if not azure_key:
        return False
    
    try:
        import azure.cognitiveservices.speech as speechsdk
        
        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        speech_config.speech_synthesis_voice_name = voice_name
        # Output to file
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        # For long text, use SSML
        ssml = f"<speak version='1.0' xml:lang='ur-PK'><voice name='{voice_name}'>{text}</voice></speak>"
        result = synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"✅ Azure SDK TTS SUCCESS")
            return True
        else:
            print(f"Azure SDK failed: {result.reason}")
            return False
    except Exception as e:
        print(f"Azure SDK error: {e}")
        return False

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"used_titles": [], "used_video_ids": [], "playlists": {}}

def save_history(h):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except: pass

def get_script(is_short, history):
    client = genai.Client(api_key=GEMINI_KEY)
    today = datetime.now().strftime("%Y-%m-%d-%H-%M")
    seed = random.randint(1, 9999999)
    used = ", ".join(history["used_titles"][-5:]) if history["used_titles"] else "none"
    SHORT_TOPICS = ["gaon ki subah 5 baje ka jadoo","chulhe par desi chai ka zaiqa","khet me bail gadi ka safar","mitti ka chulha kaise jalta hai dekho","gaon ka nalka - thanda pani","dadi ka charkha - purani yaadein","gaon ke bachche khelte hue mastiyan","khet me pani lagana - kisan ki mehnat","gaon ki masjid ki azan","sarson ka khet peela samandar","gandum ki katai ka mausam","bhains ka doodh nikalna - asli lassi","gaon ka mela - full masti","desi lassi banana - thandi thandi","khet me tractor ka zor","gaon ki shaam - sukoon hi sukoon","mitti ke ghar - thande thande","gaon ka kuwa - gehra raaz","desi khana chulhe par - chatpatta","khet me parinde - subah ki ronak"]
    LONG_TOPICS = ["gaon ki shaadi kaise hoti hai - poora riwaj 3 din ka jashan","gandum ki fasal ugane ka poora tarika 0 se 100","chulhe par desi khana kaise banta hai - 5 dishes","gaon ki subah se shaam tak ki zindagi - full day routine","barish ke baad gaon ka khoobsurat manzar - jannat jaisa","gaon ke mele ki raunaq aur khail - bachpan yaad ayega","kisan ki mehnat - khet se mandi tak 1 lakh kaise kamaye","mitti ke ghar kaise bante hain - bina cement ke","gaon me Eid kaise manate hain - subah se shaam tak masti","desi lassi aur makhan kaise banta hai - asli tareeqa","gaon me pani ka intezam - kuwe aur nalke ka raaz","garmi me gaon ki thandi shaam - nehar kinare","sardi me gaon ka chulha aur kahani - dadi ki kahani","gaon ki aurat ki din bhar ki mehnat - subah 5 se raat 10","gaon ke bachchon ka school jana - 5 km paidal","bail gadi se khet tak safar - slow life ka maza","sarson ke khet ki khoobsurati - drone view jaisa","aam ke bagh me garmi ka maza - khatte meetha aam","gaon ki biryani aur desi zaiqa - chulhe wali biryani","mitti ke bartan kaise bante hain - kumhar ki kala","gaon me machhli pakadna - nehar se 10 kg machhli","gaon ka bazaar - sabzi mandi sasti sabzi","gaon me shadi ki taiyariyan - 1 mahina pehle se","khet me hal chalana - purana tareeqa vs tractor","gaon ki raat - chand aur sitare bina light ke","desi murgi palna gaon me - mahine ke 20 hazar kamai","gaon me bhains palna aur doodh - roz 20 liter","gaon ka desi ilaj - jari bootiyan se ilaj","gaon ki kahani - buzurgon ki zuban se 100 saal purani","sheher aur gaon ki zindagi me farq - kaun behtar","gaon me ghar kaise banta hai 2 lakh me - full detail","gaon ki zameen kitne ki hai - 1 acre ka rate","gaon me bijli nahi to kya karte hain - jugad","gaon ki sasti zindagi - 500 me pura din","gaon ka asli sukoon - sheher wale kyun taraste hain"]
    if is_short:
        random.seed(f"{today}-{seed}")
        topic = random.choice(SHORT_TOPICS)
        random.seed()
        prompt = f"You are viral Pakistani village shorts writer for MAX views 2026. ONLY valid JSON. Topic: {topic} DateSeed: {today}-{seed} Avoid old: {used} VIRAL SHORT RULES 2026: Title 55 chars MAX, hook + emoji, MUST include | Desi Life Official, Description 3 lines CTA + 15 hashtags, Urdu voice 30-35 sec, FIRST 3 words MUST be Dekho doston!, Caption BIG BOLD 35 chars, Hook text UNIQUE per topic 2 words MAX (<12 chars) like for {topic} make unique hook e.g. CHULHE KA JADOO?! or 5 BAJE KA RAAZ?! JSON ONLY: {{\"title\":\"{topic.title()} 😱 Dekho Kya Hua | Desi Life Official\", \"description\":\"{topic} - Gaon ka asli jadoo dekho! #viral #shorts\", \"tags\":[\"village shorts viral\",\"desi shorts\",\"gaon\",\"DesiLifeOfficial\"], \"pexels_queries\":[\"{topic} pakistan village vertical\",\"village pakistan portrait\"], \"urdu_voice\":\"Dekho doston! {topic} gaon ki zindagi ka sabse khoobsurat raaz hai! Yahan subah 5 baje thandi hawa, khule khet, aur logon ka pyaar! Sheher wale is sukoon ke liye taraste hain! Ye hai asli Pakistan! Video pasand aaye to Like Share Subscribe zaroor karen\", \"caption\":\"{topic.upper()[:35]} 😱🔥\", \"hook_text\":\"UNIQUE HOOK\"}}"
    else:
        random.seed(f"{today}-{seed}-long")
        topic = random.choice(LONG_TOPICS)
        random.seed()
        # Generate unique hook per topic
        prompt = f"You are top Pakistani village vlogger 2026 algorithm for MAX retention + monetization + story format. ONLY valid JSON. Need 8 min 5 sec video (mid-roll eligible) = 900 words. Topic: {topic} DateSeed: {today}-{seed}-long Avoid old: {used} 2026 RETENTION FORMULA: 8:05 min = 900 words, Story format 40% higher retention, First 30 sec critical, Include chapters 00:00 Hook, 01:15 Part1, 02:45 Earning, 04:30 Secret, 06:30 Twist, End CTA, Must include: Rukiye! 4:30 pe raaz, Last tak dekho, Unique hook per topic <12 chars e.g. for shaadi topic = 3 DIN JASHAN?! for gandum topic = 1 LAKH FAIDA?! for mitti ghar topic = BINA CEMENT?! JSON ONLY 900 words urdu_voice: {{\"title\":\"{topic.title()} - Unique Hook? 😱 | Desi Life Official\", \"description\":\"Aaj {topic} ki poori kahani + kamai 2026! Chapters: 00:00 Hook, 01:15 Part1, 02:45 Earning, 04:30 Secret, 06:30 Twist #desilife\", \"tags\":[\"village life pakistan viral long 8 min\",\"desi life official\",\"gaon ki kahani 8 min\"], \"pexels_queries\":[\"{topic} pakistan village horizontal\",\"pakistan village life landscape\"], \"urdu_voice\":\"Assalam-o-Alaikum pyare doston! Dekho doston aaj ka topic sunke aap hairan ho jaoge aur end tak dekhna kyunki sabse important raaz main 4 minute 30 second pe bataunga! {topic}! Doston gaon ki zindagi me itna sukoon hai ke sheher wale taraste hain! Subah 5 baje azan ki awaz, thandi hawa, aur khet sone jaise chamak rahe! Lekin rukiye, ye sirf khoobsurati nahi! {topic} hamari 100 saal purani riwayat hai! Buzurg kehte hain gaon ki mitti me barkat hai! Part 1 suno: Gaon me log subah 4 baje uthte hain, khet me jate hain, aur shaam tak mehnat karte hain! {topic} ka tareeqa dekho to hairan ho jaoge! Part 2, kitni kamai? Doston {topic} se log mahine ke 30 se 50 hazar tak kamate hain! 1 acre se 1 lakh tak! Sheher me mahina lagta hai, gaon me 5 din! Part 3: 4:30 wala raaz - gaon me kharcha kam hai, 500 me din nikal jata hai! Sheher me 5000! Isi liye gaon ke log zyada khush hain! End: Video pasand aaye to Like Share Subscribe karo!\", \"caption\":\"{topic.title()[:35]} - UNIQUE? 😱🔥\", \"hook_text\":\"UNIQUE\"}}"
    for m in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:].strip()
            data = json.loads(txt)
            if "urdu_voice" in data and len(data["urdu_voice"]) > 100:
                # 2026 fix: Ensure unique hook not same
                hook = data.get("hook_text","").upper()
                if len(hook) > 12:
                    hook = hook[:12]
                # Make hook unique per topic if generic
                if hook in ["30 HAZAR?!", "30 HAZAR", "GAON MEIN"]:
                    # Generate topic-based hook
                    topic_words = topic.split()[:2]
                    hook = f"{topic_words[0][:4].upper()} {topic_words[1][:4].upper()}?!" if len(topic_words)>1 else f"{topic[:8].upper()}?!"
                    hook = hook[:12]
                data["hook_text"] = hook
                # 2026: Ensure 8 min = 900 words ~ 5000 chars
                if not is_short and len(data["urdu_voice"]) < 1500:
                    continue
                return data
        except Exception as e:
            print(f"Gemini {m} failed {e}")
            continue
    # Fallback with UNIQUE hooks per topic
    if is_short:
        # Unique short hook
        short_hooks = [f"{topic.split()[0][:4].upper()} JADOO?!", f"{topic.split()[0][:5].upper()} RAAZ?!", "DEKHO JADOO?!", "GAON KA RAAZ?!"]
        hook = random.choice(short_hooks)[:12]
        return {"title": f"{topic.title()} Dekho Jadoo 😱 | Desi Life Official", "description": f"{topic} - Gaon ki kahani #viral #shorts Chapters: 00:00 Hook", "tags": ["village life","gaon","desi life"], "pexels_queries": [f"{topic} pakistan vertical","village pakistan"], "urdu_voice": f"Dekho doston! Aaj hum baat karenge {topic} ke bare me. Gaon ki zindagi bohat khoobsurat hai. Yahan subah thandi hawa chalti hai, kisan khet me kaam karta hai, aur sham ko sab mil kar baithte hain. {topic} hamari pehchan hai. Video pasand aaye to Like Subscribe zaroor karen.", "caption": topic.upper()[:40]+" 😱", "hook_text": hook}
    else:
        # 2026 UNIQUE hook mapping per topic type
        hook_map = {
            "shaadi": "3 DIN JASHAN?!",
            "gandum": "1 LAKH FAIDA?!",
            "chulhe": "CHULHE KA JADOO?!",
            "subah": "5 BAJE RAAZ?!",
            "barish": "JANNAT JAISA?!",
            "mela": "MELA RONAQUE?!",
            "kisan": "1 LAKH KAMAI?!",
            "mitti": "BINA CEMENT?!",
            "Eid": "EID KA JASHAN?!",
            "lassi": "ASLI LASSI?!",
            "pani": "PAANI KA RAAZ?!",
            "nehar": "THANDI SHAAM?!",
            "chulha": "DADI KI KAHANI?!",
            "aurat": "DIN BHAR MEHNAT?!",
            "school": "5 KM PAIDAL?!",
            "bail gadi": "SLOW LIFE?!",
            "sarson": "PEELA SAMANDAR?!",
            "aam": "KHATTA MEETHA?!",
            "biryani": "CHULHE WALI?!",
            "bartan": "KUMHAR KALA?!",
            "machhli": "10 KG MACHHLI?!",
            "bazaar": "SASTI SABZI?!",
            "shadi": "1 MAHINA TAYARI?!",
            "hal": "BAIL VS TRACTOR?!",
            "raat": "CHAND SITARE?!",
            "murgi": "20 HAZAR KAMAI?!",
            "bhains": "20 LITER DOODH?!",
            "ilaj": "JARI BOOTI?!",
            "kahani": "100 SAAL PURANI?!",
            "farq": "GAON VS SHEHER?!",
            "ghar": "2 LAKH MEIN?!",
            "zameen": "1 ACRE RATE?!",
            "bijli": "JUGAD LIGHT?!",
            "sasti": "500 MEIN DIN?!",
            "sukoon": "SHEHER TARSE?!"
        }
        # Find matching hook
        unique_hook = "YE KYA?!"
        for key, h in hook_map.items():
            if key in topic.lower():
                unique_hook = h
                break
        # 2026: 8:05 min = 900 words = 5000 chars guaranteed
        base_voice = f"Assalam-o-Alaikum pyare doston! Dekho doston aaj ka topic {topic} sunke aap hairan ho jaoge aur end tak dekhna kyunki sabse important raaz main 4 minute 30 second pe bataunga! {topic}! Doston gaon ki zindagi me itna sukoon hai ke sheher wale taraste hain! Subah 5 baje azan ki awaz, thandi hawa, aur khet sone jaise chamak rahe! Lekin rukiye, ye sirf khoobsurati nahi! {topic} hamari 100 saal purani riwayat hai jo aaj bhi zinda hai! Buzurg kehte hain gaon ki mitti me barkat hai! Part 1 suno: Gaon me log subah 4 baje uthte hain, khet me jate hain, aur shaam tak mehnat karte hain! {topic} ka tareeqa dekho to hairan ho jaoge! Purane zamane se yehi chalta aa raha hai! Sheher wale ye mehnat dekh kar sharminda ho jate hain! Ab part 2, sabse important, kitni kamai hoti hai? Doston {topic} se log mahine ke 30 se 50 hazar tak kamate hain! Haan sach me! 1 acre se 1 lakh tak! Sheher me itne ke liye poora mahina office jana padta hai, gaon me 5 din ka kaam! Sasta khana, free hawa, aur apni zameen! Ab rukiye, 4:30 wala raaz: Sabse bada faida ye hai ke gaon me kharcha bohat kam hai! 500 rupaye me pura din nikal jata hai! Sheher me 5000 lagte hain! Isi liye gaon ke log zyada khush hain! Unke chehre pe sukoon hai! Bachpan yaad ayega ye dekh kar! Part 4 twist 6:30 pe: Doston agar aap bhi gaon se hain to comment me batao! Aapke gaon me {topic} kaise hota hai? Kya aapne kabhi dekha hai? Toh doston agar video pasand aaye to LIKE karo, SHARE karo apne doston se, channel ko SUBSCRIBE karo aur bell icon zaroor dabao taake har video sabse pehle apko mile! Comment me batao apka gaon kahan hai aur {topic} apko kaisa laga? Aapke pyare comments ka intezar rahega! Allah Hafiz aur gaon ka pyaar! Gaon ki mitti me hi asli zindagi hai! Sheher ki bhaag daud se door ye sukoon kahi nahi milta! Agar aap bhi gaon se pyaar karte hain to video ko share zaroor karen! Gaon me rehne wale log dil ke bohat saaf hote hain! Unki mehmaan nawazi duniya me mashhoor hai! 2026 me gaon ki zindagi aur bhi khoobsurat ho gayi hai! Naye tools aur technology se kisan aur bhi zyada kama rahe hain! "
        long_voice = (base_voice + " ") * 2
        long_voice = long_voice[:5000]  # 8:05 min = 5000 chars
        return {"title": f"{topic.title()} - {unique_hook} 😱 | Desi Life Official", "description": f"{topic} - Full story 2026 8 min! Chapters: 00:00 Hook, 01:15 Part1, 02:45 Earning, 04:30 Secret, 06:30 Twist #desilife", "tags": ["village life long 8 min","gaon","desi life 2026"], "pexels_queries": [f"{topic} pakistan horizontal","village pakistan landscape"], "urdu_voice": long_voice, "caption": f"{topic.title()[:25]} - {unique_hook}", "hook_text": unique_hook}


def download_pexels(queries, history, count, is_short):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used = set(history.get("used_video_ids", []))
    orientation = "portrait" if is_short else "landscape"
    search_queries = queries + (["village pakistan portrait vertical reel" if is_short else "village pakistan horizontal landscape"]*2)
    for q in search_queries[:7]:
        if len(clips) >= count: break
        try:
            page = random.randint(1, 5)
            url = f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}&orientation={orientation}"
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code != 200:
                res = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}", headers=headers, timeout=30)
                if res.status_code != 200: continue
            vids = res.json().get("videos", [])
            if not vids: continue
            fresh = [v for v in vids if v["id"] not in used]
            pool = fresh if len(fresh) >= 2 else vids
            for v in random.sample(pool, min(3, len(pool))):
                if len(clips) >= count: break
                mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4"]
                if not mp4s: continue
                if is_short:
                    vertical = [f for f in mp4s if f["height"] > f["width"]]
                    candidates = vertical if vertical else mp4s
                    candidates = sorted(candidates, key=lambda x: x["width"])
                    link = candidates[min(2, len(candidates)-1)]["link"] if len(candidates)>2 else candidates[-1]["link"]
                else:
                    horiz = [f for f in mp4s if f["width"] >= f["height"]]
                    candidates = horiz if horiz else mp4s
                    good = [f for f in candidates if 1280 <= f["width"] <= 1920]
                    candidates = good if good else candidates
                    link = sorted(candidates, key=lambda x: x["width"])[-1]["link"]
                data = requests.get(link, timeout=120).content
                if len(data) < 80000: continue
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp.write(data); tmp.close()
                clips.append(tmp.name)
                history["used_video_ids"].append(v["id"])
                history["used_video_ids"] = history["used_video_ids"][-300:]
                time.sleep(0.5)
        except Exception as e:
            print(f"Pexels err {q}: {e}")
            continue
    if len(clips)==1 and count>1:
        clips = clips*count
    return clips

def download_pexels_image_for_thumbnail(query, is_short):
    headers = {"Authorization": PEXELS_KEY}
    try:
        orientation = "portrait" if is_short else "landscape"
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&orientation={orientation}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=15"
            res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None
        photos = res.json().get("photos", [])
        if not photos: return None
        photo = random.choice(photos[:5])
        img_url = photo["src"]["large2x"] or photo["src"]["large"]
        img_data = requests.get(img_url, timeout=20).content
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.write(img_data); tmp.close()
        return tmp.name
    except: return None

def create_caption_image(caption_text, is_short, video_width, video_height):
    from PIL import Image, ImageDraw, ImageFont
    caption_text = caption_text.upper()[:45]
    if is_short:
        img_w, img_h = int(video_width*0.94), 190
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        except: font = ImageFont.load_default()
        for dx in (-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6):
            for dy in (-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6):
                if abs(dx)+abs(dy) > 8: continue
                draw.text((img_w//2+dx, img_h//2+dy), caption_text, font=font, fill=(0,0,0,255), anchor="mm")
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,234,0,255), anchor="mm")
    else:
        img_w, img_h = int(video_width*0.88), 100
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,195))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        except: font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def create_hook_image(hook_text, is_short, tw, th):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGBA', (tw, th), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    YELLOW = (255, 234, 0); RED = (225, 6, 0); BLACK = (0, 0, 0); WHITE = (255, 255, 255)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.105) if is_short else int(th*0.125))
        font_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.048))
    except:
        font_big = ImageFont.load_default(); font_mid = ImageFont.load_default()
    short_hook = hook_text[:18].upper()
    if is_short:
        bh = int(th*0.13); by = int(th*0.16)
        draw.rounded_rectangle([int(tw*0.04)+5, by+5, int(tw*0.96)+5, by+bh+5], radius=20, fill=(0,0,0,170))
        draw.rounded_rectangle([int(tw*0.04), by, int(tw*0.96), by+bh], radius=20, fill=RED)
        draw.text((tw//2, by+bh//2), short_hook, font=font_big, fill=YELLOW, anchor="mm", stroke_width=8, stroke_fill=BLACK)
    else:
        top_text = short_hook + " 🔥"
        bbox = draw.textbbox((0,0), top_text, font=font_big)
        pw = bbox[2]-bbox[0] + 60; ph = int(th*0.15); px = (tw - pw)//2; py = int(th*0.035)
        draw.rounded_rectangle([px+6, py+6, px+pw+6, py+ph+6], radius=22, fill=(0,0,0,160))
        draw.rounded_rectangle([px, py, px+pw, py+ph], radius=22, fill=RED)
        draw.text((tw//2, py+ph//2), top_text, font=font_big, fill=YELLOW, anchor="mm", stroke_width=9, stroke_fill=BLACK)
        draw.rectangle([0, int(th*0.83), tw, th], fill=(0,0,0,215))
        draw.rectangle([0, int(th*0.83), tw, int(th*0.83)+5], fill=YELLOW)
        draw.text((tw//2, int(th*0.92)), "⏳ RUKIYE! 4:30 PE RAAZ KHULEGA! ⏳", font=font_mid, fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=BLACK)
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def create_thumbnail(title, is_short, pexels_query="village pakistan", hook_text_override=None):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    tw, th = (1280, 720) if not is_short else (720, 1280)
    YELLOW = (255, 234, 0); RED = (225, 6, 0); BLACK = (0, 0, 0); WHITE = (255, 255, 255)
    bg_path = download_pexels_image_for_thumbnail(pexels_query, is_short)
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert('RGB')
            bg = bg.resize((tw, th), Image.LANCZOS)
            enhancer = ImageEnhance.Color(bg); bg = enhancer.enhance(1.35)
            enhancer2 = ImageEnhance.Brightness(bg); bg = enhancer2.enhance(1.15)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))
            img = bg
        except: img = Image.new('RGB', (tw, th), (28, 36, 28))
    else: img = Image.new('RGB', (tw, th), (28, 36, 28))
    overlay = Image.new('RGBA', (tw, th), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    for y in range(int(th*0.22)):
        a = int(210 - (y/(th*0.22))*130)
        d.line([(0,y),(tw,y)], fill=(0,0,0,a))
    for y in range(int(th*0.68), th):
        a = int(((y-th*0.68)/(th*0.32))*230)
        d.line([(0,y),(tw,y)], fill=(0,0,0,a))
    for x in range(int(tw*0.18)):
        a = int((1-x/(tw*0.18))*90)
        d.line([(x,0),(x,th)], fill=(0,0,0,a))
        d.line([(tw-1-x,0),(tw-1-x,th)], fill=(0,0,0,a))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    try:
        font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 145 if not is_short else 125)
        font_sec = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62 if not is_short else 58)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except:
        font_main = ImageFont.load_default(); font_sec = ImageFont.load_default(); font_badge = ImageFont.load_default(); font_small = ImageFont.load_default()
    if hook_text_override: hook = hook_text_override.upper()[:14]
    else:
        clean = title.replace("| Desi Life Official","").strip()
        if "30" in clean or "haz" in clean.lower(): hook = "30 HAZAR?!"
        elif "1 lakh" in clean.lower() or "lakh" in clean.lower(): hook = "1 LAKH?!"
        elif "gaon" in clean.lower(): hook = "GAON KA RAAZ?!"
        else: hook = "YE KYA?!"
    hook_words = hook.split()[:3]
    hook_short = " ".join(hook_words)[:12]
    curiosity_map = {"30 HAZAR?!": "GAON MEIN 💰", "1 LAKH?!": "5 DIN MEIN?!", "GAON KA RAAZ?!": "KOI NAHI BATATA", "YE KYA?!": "DEKHO JADOO! 😱"}
    secondary = curiosity_map.get(hook_short, "DEKHO! 😱")
    if not is_short:
        draw.rounded_rectangle([28, 20, 210, 68], radius=24, fill=RED)
        draw.text((119, 44), "😱 VIRAL", font=font_badge, fill=WHITE, anchor="mm")
        draw.rounded_rectangle([tw-132, 20, tw-22, 60], radius=10, fill=BLACK, outline=YELLOW, width=3)
        draw.text((tw-77, 40), "6:30", font=font_badge, fill=YELLOW, anchor="mm")
        draw.text((tw//2+5, int(th*0.46)+5), hook_short, font=font_main, fill=(0,0,0,200), anchor="mm")
        draw.text((tw//2, int(th*0.46)), hook_short, font=font_main, fill=YELLOW, anchor="mm", stroke_width=18, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.62)), secondary, font=font_sec, fill=WHITE, anchor="mm", stroke_width=9, stroke_fill=BLACK)
        draw.text((32, int(th*0.92)), "Desi Life Official ✓", font=font_small, fill=WHITE, anchor="lm", stroke_width=2, stroke_fill=BLACK)
    else:
        draw.rounded_rectangle([(tw-200)//2, 18, (tw+200)//2, 62], radius=22, fill=RED)
        draw.text((tw//2, 40), "VIRAL 😱", font=font_badge, fill=WHITE, anchor="mm")
        try: font_emoji = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
        except: font_emoji = font_main
        draw.text((tw//2, int(th*0.32)), "😱", font=font_emoji, fill=WHITE, anchor="mm", stroke_width=8, stroke_fill=BLACK)
        draw.text((tw//2+4, int(th*0.52)+4), hook_short, font=font_main, fill=BLACK, anchor="mm")
        draw.text((tw//2, int(th*0.52)), hook_short, font=font_main, fill=YELLOW, anchor="mm", stroke_width=16, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.64)), secondary, font=font_sec, fill=WHITE, anchor="mm", stroke_width=8, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.92)), "Desi Life Official", font=font_small, fill=WHITE, anchor="mm", stroke_width=2, stroke_fill=BLACK)
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    img.save(path, "JPEG", quality=96)
    return path

def create_subscribe_endcard(is_short, tw, th):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (tw, th), (15, 15, 15))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, tw, int(th*0.07)], fill=(255, 0, 0))
    draw.rectangle([0, int(th*0.93), tw, th], fill=(0, 100, 0))
    draw.rounded_rectangle([int(tw*0.05), int(th*0.15), int(tw*0.95), int(th*0.88)], radius=30, fill=(30, 30, 30))
    try:
        font_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.10) if is_short else int(th*0.12))
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.07) if is_short else int(th*0.08))
        font_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.042) if is_short else int(th*0.045))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(th*0.028) if is_short else int(th*0.032))
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(th*0.022) if is_short else int(th*0.026))
    except:
        font_huge = ImageFont.load_default(); font_big = ImageFont.load_default(); font_mid = ImageFont.load_default(); font_small = ImageFont.load_default(); font_tiny = ImageFont.load_default()
    YT_HANDLE = "YouTube.com/@DesiLifeOfficial"
    FB_HANDLE = "Facebook.com/DesiLifeOfficial"
    YT_SHORT = "@DesiLifeOfficial"
    FB_SHORT = "Desi Life Official"
    if is_short:
        draw.text((tw//2, int(th*0.20)), "🔔", font=font_huge, fill=(255, 255, 255), anchor="mm")
        draw.text((tw//2, int(th*0.30)), "SUBSCRIBE", font=font_big, fill=(255, 0, 0), anchor="mm", stroke_width=3, stroke_fill=(255,255,255))
        draw.text((tw//2, int(th*0.36)), "KAREN", font=font_big, fill=(255,255,255), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        draw.text((tw//2, int(th*0.44)), "Desi Life Official", font=font_mid, fill=(255, 235, 0), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        btn_w, btn_h = int(tw*0.75), int(th*0.065)
        btn_x1, btn_y1 = (tw-btn_w)//2, int(th*0.50)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=25, fill=(255, 0, 0))
        draw.text((tw//2, btn_y1+btn_h//2), "SUBSCRIBED ✓  Bell 🔔", font=font_small, fill=(255,255,255), anchor="mm")
        yt_box_y = int(th*0.59)
        draw.rounded_rectangle([int(tw*0.08), yt_box_y, int(tw*0.92), yt_box_y+int(th*0.08)], radius=15, fill=(200, 0, 0))
        draw.text((int(tw*0.15), yt_box_y+int(th*0.04)), "▶️", font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), yt_box_y+int(th*0.025)), "YouTube", font=font_tiny, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), yt_box_y+int(th*0.055)), YT_HANDLE, font=font_small, fill=(255,255,255), anchor="lm")
        fb_box_y = int(th*0.68)
        draw.rounded_rectangle([int(tw*0.08), fb_box_y, int(tw*0.92), fb_box_y+int(th*0.08)], radius=15, fill=(0, 80, 180))
        draw.text((int(tw*0.15), fb_box_y+int(th*0.04)), "📘", font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), fb_box_y+int(th*0.025)), "Facebook", font=font_tiny, fill=(200,220,255), anchor="lm")
        draw.text((int(tw*0.25), fb_box_y+int(th*0.055)), FB_HANDLE, font=font_small, fill=(255,255,255), anchor="lm")
        draw.text((tw//2, int(th*0.80)), "👍 Like  |  💬 Comment  |  ↗️ Share", font=font_small, fill=(255,255,255), anchor="mm")
        draw.text((tw//2, int(th*0.84)), "Har Video Sabse Pehle Dekhne Ke Liye", font=font_tiny, fill=(180,180,180), anchor="mm")
        draw.text((tw//2, int(th*0.87)), "Bell Icon Zaroor Dabayen 🔔", font=font_tiny, fill=(255,235,0), anchor="mm")
    else:
        draw.text((int(tw*0.30), int(th*0.28)), "🔔 SUBSCRIBE KAREN 🔔", font=font_big, fill=(255,255,255), anchor="mm", stroke_width=3, stroke_fill=(0,0,0))
        draw.text((int(tw*0.30), int(th*0.42)), "Desi Life Official", font=font_mid, fill=(255,235,0), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        btn_w, btn_h = int(tw*0.22), int(th*0.12)
        btn_x1, btn_y1 = int(tw*0.30-btn_w//2), int(th*0.52)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=20, fill=(255,0,0))
        draw.text((int(tw*0.30), btn_y1+btn_h//2), "SUBSCRIBE ✓", font=font_mid, fill=(255,255,255), anchor="mm")
        draw.text((int(tw*0.30), int(th*0.75)), "👍 Like  •  💬 Comment  •  ↗️ Share", font=font_small, fill=(220,220,220), anchor="mm")
        draw.text((int(tw*0.30), int(th*0.81)), "Bell Dabana Mat Bhoolna! 🔔", font=font_small, fill=(255,235,0), anchor="mm")
        box_w, box_h = int(tw*0.38), int(th*0.18)
        box_x = int(tw*0.58)
        yt_y = int(th*0.28)
        draw.rounded_rectangle([box_x, yt_y, box_x+box_w, yt_y+box_h], radius=15, fill=(200, 0, 0))
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.30)), "▶️  YouTube Channel", font=font_small, fill=(255,200,200), anchor="lm")
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.65)), YT_SHORT, font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.85)), YT_HANDLE, font=font_tiny, fill=(255,220,220), anchor="lm")
        fb_y = int(th*0.52)
        draw.rounded_rectangle([box_x, fb_y, box_x+box_w, fb_y+box_h], radius=15, fill=(0, 80, 180))
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.30)), "📘  Facebook Page", font=font_small, fill=(180,210,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.65)), FB_SHORT, font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.85)), FB_HANDLE, font=font_tiny, fill=(200,220,255), anchor="lm")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def resize_and_crop(clip, target_size):
    tw, th = target_size
    cw, ch = clip.w, clip.h
    scale_w = tw / cw
    scale_h = th / ch
    scale = max(scale_w, scale_h)
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    clip = clip.resize((new_w, new_h))
    x_center = new_w // 2
    y_center = new_h // 2
    x1 = x_center - tw // 2
    y1 = y_center - th // 2
    clip = clip.crop(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)
    return clip

def make_video(paths, urdu_text, caption, hook_text, is_short):
    target_size = SHORT_SIZE if is_short else LONG_SIZE
    tw, th = target_size
    # === 2026 FIX: GUARANTEE 8:05 MIN FOR MID-ROLL (5000 chars) ===
    original_len = len(urdu_text)
    if not is_short:
        # 2026: 8:05 min = 5000 chars for 2 mid-roll ads
        while len(urdu_text) < 3500:
            urdu_text = urdu_text + " " + urdu_text[:1200]
        urdu_text = urdu_text[:5000]  # 8:05 min guarantee
        print(f"2026 FIX: Long voice extended from {original_len} to {len(urdu_text)} chars for 8:05 min guarantee (mid-roll eligible)")
    else:
        if len(urdu_text) > 400:
            urdu_text = urdu_text[:350]
    a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    audio = None
    # === PRIORITY 1: MS AZURE TTS (Most Stable, PRO quality) ===
    azure_success = False
    try:
        voice_to_use = VOICE_NAME_MALE if VOICE_GENDER == "male" else VOICE_NAME_FEMALE
        print(f"=== Trying Azure TTS (Priority 1) ===")
        azure_success = generate_azure_tts(urdu_text, a_path, voice_name=voice_to_use)
        if azure_success and os.path.exists(a_path) and os.path.getsize(a_path) > 1000:
            audio = AudioFileClip(a_path)
            print(f"✅ Azure TTS SUCCESS duration {audio.duration:.1f}s")
        else:
            print("Azure TTS not available or failed, trying Edge-TTS")
            azure_success = False
    except Exception as e:
        print(f"Azure check failed {e}")
        azure_success = False
    
    # === PRIORITY 2: Edge-TTS (if Azure fails) ===
    if not azure_success or audio is None:
        try:
            import edge_tts
            import asyncio
            voice_to_use = VOICE_NAME_MALE if VOICE_GENDER == "male" else VOICE_NAME_FEMALE
            print(f"Trying Edge-TTS {voice_to_use} with {len(urdu_text)} chars")
            async def generate_edge_tts():
                communicate = edge_tts.Communicate(urdu_text, voice_to_use)
                await communicate.save(a_path)
            asyncio.run(generate_edge_tts())
            audio = AudioFileClip(a_path)
            print(f"Edge-TTS SUCCESS duration {audio.duration:.1f}s")
        except Exception as e:
            print(f"Edge-TTS failed {e}, trying gTTS")
            try:
                tts = gTTS(text=urdu_text, lang='ur', slow=False, tld='com')
                tts.save(a_path)
                audio = AudioFileClip(a_path)
                print(f"gTTS com SUCCESS {audio.duration:.1f}s")
            except Exception as e2:
                print(f"gTTS com failed {e2}, trying gTTS default")
                tts = gTTS(text=urdu_text, lang='ur', slow=False)
                tts.save(a_path)
                audio = AudioFileClip(a_path)
                print(f"gTTS default SUCCESS {audio.duration:.1f}s")
    
    if audio is None:
        raise Exception("Audio generation failed - all TTS failed")
    
    vcs = []
    per = audio.duration / len(paths) if paths else audio.duration
    print(f"Audio {audio.duration:.1f}s split into {len(paths)} clips = {per:.1f}s each")
    for p in paths:
        try:
            vc = VideoFileClip(p)
            vc = resize_and_crop(vc, target_size)
            s = random.uniform(0, max(0, vc.duration - per - 0.3))
            vc = vc.subclip(s, s+per+0.5)
            vcs.append(vc)
        except Exception as e:
            print(f"Clip error {e}")
            continue
    if not vcs:
        raise Exception("No clips usable")
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration:
        final_v = final_v.loop(duration=audio.duration)
    else:
        final_v = final_v.subclip(0, audio.duration)
    final_v = resize_and_crop(final_v, target_size)
    cap_path = create_caption_image(caption, is_short, tw, th)
    cap_clip = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip = cap_clip.set_position(('center', th*0.78)) if is_short else cap_clip.set_position(('center', th*0.82))
    hook_path = create_hook_image(hook_text, is_short, tw, th)
    hook_clip_3sec = ImageClip(hook_path).set_duration(min(3, audio.duration)).set_position(('center','center'))
    cap_clip_full = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip_full = cap_clip_full.set_position(('center', th*0.78)) if is_short else cap_clip_full.set_position(('center', th*0.82))
    final = CompositeVideoClip([final_v, cap_clip_full, hook_clip_3sec], size=target_size).set_duration(audio.duration).set_audio(audio)
    target_str = "30-40s" if is_short else "480-490s (8:05 min mid-roll)"
    print(f"Main video duration: {final.duration:.1f}s - Target: {target_str}")
    endcard_path = create_subscribe_endcard(is_short, tw, th)
    endcard_clip = ImageClip(endcard_path).set_duration(4)
    final_with_endcard = concatenate_videoclips([final, endcard_clip], method="compose")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_with_endcard.write_videofile(out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"], threads=4, logger=None)
    return out


def build_youtube_client():
    # Try to refresh token manually first to show real error
    import os
    yt_client_id = os.environ.get("YOUTUBE_CLIENT_ID","")
    yt_client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET","")
    yt_refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN","")
    print(f"YT Creds check: client_id={yt_client_id[:15]}... secret={'SET' if yt_client_secret else 'MISSING'} refresh={'SET' if yt_refresh else 'MISSING'} len={len(yt_refresh)}")
    
    # Manual refresh attempt for better error message
    try:
        print("--- Trying manual token refresh ---")
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": yt_client_id,
            "client_secret": yt_client_secret,
            "refresh_token": yt_refresh,
            "grant_type": "refresh_token"
        }
        r = requests.post(token_url, data=data, timeout=20)
        print(f"Token refresh response: {r.status_code} {r.text[:800]}")
        if r.status_code != 200:
            print(f"❌ TOKEN EXPIRED! Need to regenerate YOUTUBE_REFRESH_TOKEN in GitHub Secrets!")
            print(f"Go to: https://developers.google.com/oauthplayground")
            print(f"Steps: Select YouTube Data API v3 -> https://www.googleapis.com/auth/youtube.upload -> Authorize -> Exchange -> Copy refresh_token")
    except Exception as e:
        print(f"Manual refresh error: {e}")

    for scopes in [["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.upload"], ["https://www.googleapis.com/auth/youtube.upload"]]:
        try:
            print(f"Trying scopes: {scopes}")
            creds = Credentials(None, refresh_token=yt_refresh, token_uri="https://oauth2.googleapis.com/token", client_id=yt_client_id, client_secret=yt_client_secret, scopes=scopes)
            # Force refresh
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            print(f"✅ Token refreshed! Access token: {creds.token[:20]}...")
            yt = build("youtube","v3", credentials=creds)
            yt.channels().list(part="snippet", mine=True).execute()
            print(f"✅ YouTube client built successfully with scopes {scopes}")
            return yt
        except Exception as e:
            print(f"YT scope {scopes} failed: {e}")
            import traceback
            traceback.print_exc()
            continue
    raise Exception("YOUTUBE_REFRESH_TOKEN invalid - EXPIRED! Regenerate from https://developers.google.com/oauthplayground - Select YouTube Data API v3 scope youtube.upload")

def get_or_create_playlist(youtube, history, title, is_short):
    key = "short" if is_short else "long"
    if key in history.get("playlists", {}) and history["playlists"][key]: return history["playlists"][key]
    try:
        pls = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for pl in pls.get("items", []):
            if title.lower() in pl["snippet"]["title"].lower() or pl["snippet"]["title"].lower() in title.lower():
                history["playlists"][key] = pl["id"]
                return pl["id"]
    except: return None
    try:
        body = {"snippet": {"title": title, "description": f"{title} auto"}, "status": {"privacyStatus": "public"}}
        resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
        history["playlists"][key] = resp["id"]
        return resp["id"]
    except: return None

def upload_to_youtube_and_fb(file_path, title, desc, tags, is_short, history, pexels_query="village pakistan", hook_text="30 HAZAR?!"):
    youtube = build_youtube_client()
    yt_title = title[:95]
    chunk_size = 1024*1024*10 if not is_short else 1024*1024*5
    body = {"snippet":{"title":yt_title,"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=chunk_size)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"YouTube Upload {int(st.progress()*100)}% - {'LONG 6min PRO CTR' if not is_short else 'SHORT PRO CTR'}")
    vid = resp.get('id')
    print(f"YouTube SUCCESS https://youtu.be/{vid}")
    try:
        thumb_path = create_thumbnail(title, is_short=is_short, pexels_query=pexels_query, hook_text_override=hook_text)
        youtube.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg", resumable=False)).execute()
        print(f"✅ PRO THUMBNAIL UPLOADED {vid}")
    except Exception as e:
        print(f"Thumbnail skip: {e}")
    try:
        pid = get_or_create_playlist(youtube, history, SHORT_TITLE if is_short else LONG_TITLE, is_short)
        if pid:
            youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    except: pass
    if not FB_ENABLED: print("--- Facebook DISABLED ---")
    if not TIKTOK_ENABLED: print("--- TikTok DISABLED ---")
    return resp

def run_once(is_short=False):
    h = load_history()
    print(f"--- {'SHORT 1080x1920 REEL ULTIMATE CTR' if is_short else 'LONG 1920x1080 VIDEO 6-7 MIN ULTIMATE CTR'} START ---")
    data = get_script(is_short, h)
    print(f"Title: {data['title']} | Hook: {data.get('hook_text','')} | Voice len: {len(data['urdu_voice'])} chars")
    h["used_titles"].append(data["title"])
    h["used_titles"] = h["used_titles"][-60:]
    clip_count = 2 if is_short else 6
    clips = download_pexels(data["pexels_queries"], h, count=clip_count, is_short=is_short)
    if not clips: raise Exception("No Pexels clips")
    final = make_video(clips, data["urdu_voice"], data["caption"], data.get("hook_text","30 HAZAR?!"), is_short)
    pexels_q = data["pexels_queries"][0] if data.get("pexels_queries") else "village pakistan"
    upload_to_youtube_and_fb(final, data["title"], data["description"], data["tags"], is_short, h, pexels_q, data.get("hook_text","30 HAZAR?!"))
    save_history(h)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
