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
        prompt = f"You are viral Pakistani village shorts writer for MAX views. ONLY valid JSON. Topic: {topic} DateSeed: {today}-{seed} Avoid old: {used} VIRAL SHORT RULES - PRO HOOK (research: 3 words max, <12 chars, yellow highest scroll-stop): Title: 55 chars MAX, hook + emoji, MUST include | Desi Life Official Description: 3 lines CTA + 15 hashtags Urdu voice: 30-35 sec, FIRST 3 words MUST be Dekho doston! (HOOK) Caption: BIG BOLD 35 chars with emoji Hook text: 2 words MAX like 30 HAZAR?! or YE KYA?! (must be <12 chars for CTR) JSON ONLY: {{\"title\":\"{topic.title()} 😱 Dekho Kya Hua | Desi Life Official\", \"description\":\"{topic} - Gaon ka asli jadoo dekho!\", \"tags\":[\"village shorts viral\",\"desi shorts\",\"gaon\",\"DesiLifeOfficial\"], \"pexels_queries\":[\"{topic} pakistan village vertical\",\"village pakistan portrait\"], \"urdu_voice\":\"Dekho doston! {topic} gaon ki zindagi ka sabse khoobsurat raaz hai! Yahan subah 5 baje thandi hawa, khule khet, aur logon ka pyaar! Sheher wale is sukoon ke liye taraste hain! Ye hai asli Pakistan! Video pasand aaye to Like Share Subscribe zaroor karen\", \"caption\":\"{topic.upper()[:35]} 😱🔥\", \"hook_text\":\"30 HAZAR?!\"}}"
    else:
        random.seed(f"{today}-{seed}-long")
        topic = random.choice(LONG_TOPICS)
        random.seed()
        prompt = f"You are top Pakistani village vlogger for MAX retention + monetization. ONLY valid JSON. Need 6-7 min video (sweet spot). Topic: {topic} DateSeed: {today}-{seed}-long Avoid old: {used} LONG RETENTION FORMULA (6-7 MIN = 700 words): Total urdu_voice: 700 words approx (5-6 min audio) - MUST BE LONG 650-750 words! Structure: HOOK 0-10 sec Dekho doston! Aaj 30 hazar ka raaz!, Part1 01:15, Part2 02:45 earning twist Rukiye! 30 hazar ka hisab 2:45 pe, Secret 04:30 Sabse important 4:30 pe, End CTA Must include: Rukiye! Sabse important baat 4:30 pe bataunga, Last tak dekho, money angle Hook text: 2 words MAX like 30 HAZAR?! or 1 LAKH?! (<12 chars for CTR) JSON ONLY, urdu_voice 650-750 words: {{\"title\":\"{topic.title()} - Mahine Ke 30 Hazar Ka Raaz? 😱 | Desi Life Official\", \"description\":\"Aaj ki video me {topic} ki poori kahani + kamai!\", \"tags\":[\"village life pakistan viral long\",\"desi life official\",\"gaon ki kahani 6 min\"], \"pexels_queries\":[\"{topic} pakistan village horizontal\",\"pakistan village life landscape\"], \"urdu_voice\":\"Assalam-o-Alaikum pyare doston! Dekho doston aaj ka topic sunke aap hairan ho jaoge aur end tak dekhna kyunki sabse important raaz main 4 minute 30 second pe bataunga! {topic}! Doston gaon ki zindagi me itna sukoon hai ke sheher wale taraste hain! Subah 5 baje azan ki awaz, thandi hawa, aur khet sone jaise chamak rahe! Lekin rukiye, ye sirf khoobsurati nahi! {topic} hamari 100 saal purani riwayat hai! Buzurg kehte hain gaon ki mitti me barkat hai! Part 1 suno: Gaon me log subah 4 baje uthte hain, khet me jate hain, aur shaam tak mehnat karte hain! {topic} ka tareeqa dekho to hairan ho jaoge! Part 2, kitni kamai? Doston {topic} se log mahine ke 30 se 50 hazar tak kamate hain! 1 acre se 1 lakh tak! Sheher me mahina lagta hai, gaon me 5 din! Part 3: 4:30 wala raaz - gaon me kharcha kam hai, 500 me din nikal jata hai! Sheher me 5000! Isi liye gaon ke log zyada khush hain! End: Video pasand aaye to Like Share Subscribe karo!\", \"caption\":\"{topic.title()[:35]} - 30 HAZAR? 😱🔥\", \"hook_text\":\"30 HAZAR?!\"}}"
    for m in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:].strip()
            data = json.loads(txt)
            if "urdu_voice" in data and len(data["urdu_voice"]) > 25:
                if not is_short and len(data["urdu_voice"]) < 400: continue
                return data
        except: continue
    if is_short:
        return {"title": f"{topic.title()} Dekho Jadoo 😱 | Desi Life Official", "description": f"{topic} - Gaon ki kahani #viral #shorts", "tags": ["village life","gaon","desi life"], "pexels_queries": [f"{topic} pakistan vertical","village pakistan"], "urdu_voice": f"Dekho doston! Aaj hum baat karenge {topic} ke bare me. Gaon ki zindagi bohat khoobsurat hai. Yahan subah thandi hawa chalti hai, kisan khet me kaam karta hai, aur sham ko sab mil kar baithte hain. {topic} hamari pehchan hai. Video pasand aaye to Like Subscribe zaroor karen.", "caption": topic.upper()[:40]+" 😱", "hook_text": "30 HAZAR?!"}
    else:
        return {"title": f"{topic.title()} - 30 Hazar Ka Raaz? 😱 | Desi Life Official", "description": f"{topic} - Full story #desilife", "tags": ["village life long","gaon","desi life"], "pexels_queries": [f"{topic} pakistan horizontal","village pakistan landscape"], "urdu_voice": f"Assalam-o-Alaikum doston! Dekho doston aaj hum baat karenge {topic} ke bare me jo 6 minute tak aapko hairan rakhega! Rukiye sabse important baat 4:30 pe bataunga! Gaon ki zindagi bohat khoobsurat hai. Yahan subah 5 baje azan hoti hai, thandi hawa chalti hai, kisan khet me kaam karta hai. {topic} hamari 100 saal purani riwayat hai. Buzurg kehte hain gaon ki mitti me barkat hai. Part 1: Gaon me log subah 4 baje uthte hain, khet me jate hain. {topic} ka tareeqa purana hai. Part 2: Kitni kamai? Doston {topic} se mahine ke 30 se 50 hazar kamate hain! 1 acre se 1 lakh! Sheher me mahina lagta hai, gaon me 5 din! Part 3: 4:30 wala raaz - gaon me kharcha kam hai, 500 me din nikal jata hai! Sheher me 5000! Isi liye gaon ke log khush hain! End: Video pasand aaye to Like Share Subscribe karo aur comment me batao apka gaon kahan hai? Allah Hafiz!", "caption": f"{topic.title()[:35]} - 30 HAZAR?", "hook_text": "30 HAZAR?!"}

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
    a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    audio = None
    try:
        import edge_tts
        import asyncio
        voice_to_use = VOICE_NAME_MALE if VOICE_GENDER == "male" else VOICE_NAME_FEMALE
        async def generate_edge_tts():
            communicate = edge_tts.Communicate(urdu_text, voice_to_use)
            await communicate.save(a_path)
        asyncio.run(generate_edge_tts())
        audio = AudioFileClip(a_path)
    except:
        try:
            tts = gTTS(text=urdu_text, lang='ur', slow=False, tld='com')
            tts.save(a_path)
            audio = AudioFileClip(a_path)
        except:
            tts = gTTS(text=urdu_text, lang='ur', slow=False)
            tts.save(a_path)
            audio = AudioFileClip(a_path)
    vcs = []
    per = audio.duration / len(paths) if paths else audio.duration
    for p in paths:
        try:
            vc = VideoFileClip(p)
            vc = resize_and_crop(vc, target_size)
            s = random.uniform(0, max(0, vc.duration - per - 0.3))
            vc = vc.subclip(s, s+per+0.5)
            vcs.append(vc)
        except: continue
    if not vcs: raise Exception("No clips usable")
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration: final_v = final_v.loop(duration=audio.duration)
    else: final_v = final_v.subclip(0, audio.duration)
    final_v = resize_and_crop(final_v, target_size)
    cap_path = create_caption_image(caption, is_short, tw, th)
    cap_clip = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip = cap_clip.set_position(('center', th*0.78)) if is_short else cap_clip.set_position(('center', th*0.82))
    hook_path = create_hook_image(hook_text, is_short, tw, th)
    hook_clip_3sec = ImageClip(hook_path).set_duration(min(3, audio.duration)).set_position(('center','center'))
    cap_clip_full = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip_full = cap_clip_full.set_position(('center', th*0.78)) if is_short else cap_clip_full.set_position(('center', th*0.82))
    final = CompositeVideoClip([final_v, cap_clip_full, hook_clip_3sec], size=target_size).set_duration(audio.duration).set_audio(audio)
    endcard_path = create_subscribe_endcard(is_short, tw, th)
    endcard_clip = ImageClip(endcard_path).set_duration(4)
    final_with_endcard = concatenate_videoclips([final, endcard_clip], method="compose")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_with_endcard.write_videofile(out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"], threads=4, logger=None)
    return out

def build_youtube_client():
    for scopes in [["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.upload"], ["https://www.googleapis.com/auth/youtube.upload"]]:
        try:
            creds = Credentials(None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"], scopes=scopes)
            yt = build("youtube","v3", credentials=creds)
            yt.channels().list(part="snippet", mine=True).execute()
            return yt
        except: continue
    raise Exception("YOUTUBE_REFRESH_TOKEN invalid")

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
