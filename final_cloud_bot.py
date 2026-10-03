
import os, json, tempfile, requests, time, random
from datetime import datetime

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, ImageClip, ColorClip
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_KEY"]
PEXELS_KEY = os.environ["PEXELS_KEY"]
HISTORY_FILE = "history.json"

# Configs
LONG_TITLE = "Desi Life Official - Long Videos"
SHORT_TITLE = "Desi Life Official - Shorts"

FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")

FB_APP_ID = os.environ.get("FB_APP_ID", "")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET", "")
FB_USER_TOKEN = os.environ.get("FB_USER_TOKEN", "")  # Long-lived user token (60 days)

# TikTok - DISABLED FOR NOW (as per user request)
TIKTOK_ENABLED = False  # Set True to enable later
TIKTOK_ACCESS_TOKEN = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")

# Voice Config - MALE
VOICE_GENDER = "male"  # male / female
VOICE_NAME_MALE = "ur-PK-AsadNeural"  # Male Urdu voice (Edge-TTS)
VOICE_NAME_FEMALE = "ur-PK-UzmaNeural"

def get_fresh_page_token():
    """AUTO REFRESH - FIXED FOR ERROR 190"""
    global FB_PAGE_TOKEN
    
    # FIX: Even if APP_ID/SECRET missing, try with USER_TOKEN alone
    user_token_to_use = FB_USER_TOKEN if FB_USER_TOKEN else ""
    
    # Try auto refresh if USER_TOKEN exists (60 days wala)
    if FB_USER_TOKEN:
        try:
            print("--- AUTO REFRESH: Getting fresh Page token ---")
            # Step 1: Extend if APP_ID/SECRET available
            if FB_APP_ID and FB_APP_SECRET:
                try:
                    exchange_url = f"https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id={FB_APP_ID}&client_secret={FB_APP_SECRET}&fb_exchange_token={FB_USER_TOKEN}"
                    ex_res = requests.get(exchange_url, timeout=20)
                    if ex_res.status_code == 200:
                        new_user_token = ex_res.json().get("access_token")
                        if new_user_token:
                            print(f"User token auto-extended to 60 days!")
                            user_token_to_use = new_user_token
                except Exception as e:
                    print(f"Token extend skip: {e}")
            
            # Step 2: Get fresh Page token
            url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={user_token_to_use}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                data = res.json()
                for page in data.get("data", []):
                    if str(page["id"]) == str(FB_PAGE_ID):
                        fresh_token = page["access_token"]
                        print(f"AUTO REFRESH SUCCESS! Fresh Page token for Page {FB_PAGE_ID}")
                        return fresh_token
                if data.get("data"):
                    fresh_token = data["data"][0]["access_token"]
                    print(f"AUTO REFRESH: Using first available page {data['data'][0]['id']}")
                    return fresh_token
            else:
                print(f"AUTO REFRESH failed: {res.status_code} {res.text[:500]}")
                # If USER_TOKEN also expired, fallback
        except Exception as e:
            print(f"AUTO REFRESH error: {e}")
    
    # Fallback to static token
    if FB_PAGE_TOKEN:
        print(f"Using static FB_PAGE_ACCESS_TOKEN (may expire) - FIX: Add FB_USER_TOKEN secret for auto-refresh!")
    else:
        print(f"WARNING: No FB tokens set!")
    return FB_PAGE_TOKEN



# Size requirements
LONG_SIZE = (1920, 1080)  # YouTube Long + FB Video
SHORT_SIZE = (1080, 1920) # YouTube Shorts + FB Reel - 9:16

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
    # Date + time + random seed = har dafa naya topic
    today = datetime.now().strftime("%Y-%m-%d-%H-%M")
    seed = random.randint(1, 9999999)
    # History nahi milta GitHub me, is liye date+seed se naya topic
    used = ", ".join(history["used_titles"][-5:]) if history["used_titles"] else "none"
    
    # 150 VIRAL SHORT topics - high CTR
    SHORT_TOPICS = [
        "gaon ki subah 5 baje ka jadoo", "chulhe par desi chai ka zaiqa", "khet me bail gadi ka safar", "mitti ka chulha kaise jalta hai dekho", "gaon ka nalka - thanda pani",
        "dadi ka charkha - purani yaadein", "gaon ke bachche khelte hue mastiyan", "khet me pani lagana - kisan ki mehnat", "gaon ki masjid ki azan", "sarson ka khet peela samandar",
        "gandum ki katai ka mausam", "bhains ka doodh nikalna - asli lassi", "gaon ka mela - full masti", "desi lassi banana - thandi thandi", "khet me tractor ka zor",
        "gaon ki shaam - sukoon hi sukoon", "mitti ke ghar - thande thande", "gaon ka kuwa - gehra raaz", "desi khana chulhe par - chatpatta", "khet me parinde - subah ki ronak",
        "gaon ka bazar - sasti sabzi", "mitti ki khushbu - barish ke baad", "gaon ki barish - keechar hi keechar", "kisan ki subah 4 baje uthna", "desi charpai pe neend",
        "gaon ka school - bachpan yaad ayega", "khet me dhan ki fasal", "gaon ka chand - kitna bada", "desi achaar banana - khatta meetha", "gaon me Eid - full enjoy",
        "chulhe ki roti - gol gol", "gaay ka doodh - taza taza", "gaon ki hawa - thandi thandi", "khet me hal chalana - purana zamana", "gaon ki biryani - desi zaiqa",
        "mitti ke bartan - haath se bane", "gaon ki chai - kulhad wali", "khet me machhli - pakdo pakdo", "gaon ki raat - jugnu chamke", "desi ghee - asli wala",
        "gaon ka kuwa - rassi se pani", "sarson ka saag - makki ki roti", "gaon ka mela - jhule jhule", "kisan ka khana - desi style", "gaon ki dulhan - laal joda"
    ]
    
    # 100 VIRAL LONG topics - high retention
    LONG_TOPICS = [
        "gaon ki shaadi kaise hoti hai - poora riwaj 3 din ka jashan", "gandum ki fasal ugane ka poora tarika 0 se 100", "chulhe par desi khana kaise banta hai - 5 dishes",
        "gaon ki subah se shaam tak ki zindagi - full day routine", "barish ke baad gaon ka khoobsurat manzar - jannat jaisa",
        "gaon ke mele ki raunaq aur khail - bachpan yaad ayega", "kisan ki mehnat - khet se mandi tak 1 lakh kaise kamaye", "mitti ke ghar kaise bante hain - bina cement ke",
        "gaon me Eid kaise manate hain - subah se shaam tak masti", "desi lassi aur makhan kaise banta hai - asli tareeqa",
        "gaon me pani ka intezam - kuwe aur nalke ka raaz", "garmi me gaon ki thandi shaam - nehar kinare", "sardi me gaon ka chulha aur kahani - dadi ki kahani",
        "gaon ki aurat ki din bhar ki mehnat - subah 5 se raat 10", "gaon ke bachchon ka school jana - 5 km paidal",
        "bail gadi se khet tak safar - slow life ka maza", "sarson ke khet ki khoobsurati - drone view jaisa", "aam ke bagh me garmi ka maza - khatte meetha aam",
        "gaon ki biryani aur desi zaiqa - chulhe wali biryani", "mitti ke bartan kaise bante hain - kumhar ki kala",
        "gaon me machhli pakadna - nehar se 10 kg machhli", "gaon ka bazaar - sabzi mandi sasti sabzi", "gaon me shadi ki taiyariyan - 1 mahina pehle se",
        "khet me hal chalana - purana tareeqa vs tractor", "gaon ki raat - chand aur sitare bina light ke",
        "desi murgi palna gaon me - mahine ke 20 hazar kamai", "gaon me bhains palna aur doodh - roz 20 liter",
        "gaon ka desi ilaj - jari bootiyan se ilaj", "gaon ki kahani - buzurgon ki zuban se 100 saal purani", "sheher aur gaon ki zindagi me farq - kaun behtar",
        "gaon me ghar kaise banta hai 2 lakh me - full detail", "gaon ki zameen kitne ki hai - 1 acre ka rate", "gaon me bijli nahi to kya karte hain - jugad",
        "gaon ki sasti zindagi - 500 me pura din", "gaon ka asli sukoon - sheher wale kyun taraste hain"
    ]
    
    if is_short:
        # Har bar date + random se naya topic pick
        random.seed(f"{today}-{seed}")
        topic = random.choice(SHORT_TOPICS)
        random.seed()  # reset
        
        prompt = f"""You are viral Pakistani village shorts writer for MAX views. ONLY valid JSON.
Topic: {topic}
DateSeed: {today}-{seed}
Avoid these old topics: {used}

RULES FOR VIRAL (must follow):
- Title: 60 chars, with hook + emoji, MUST include | Desi Life Official, use words like Dekho, Jadoo, Asli, Raaz, Shock, Viral
- Description: 3 lines, CTA, 15 hashtags trending #viral #trending #shorts #desilife #villagelife #pakistan #gaon #punjab #desi #village #reels #fyp #foryou #tiktok #desilifeofficial
- Urdu voice: 35 sec, first 3 sec hook "Dekho doston!" + emotional story + end "Comment me batao apka gaon kaisa hai?"
- Caption: BIG BOLD 40 chars with emoji

JSON ONLY:
{{"title":"{topic.title()} 😱 Dekho Kya Hua | Desi Life Official", "description":"{topic} - Gaon ka asli jadoo dekho! 😍\\n\\nVideo pasand aaye to LIKE 👍 SHARE karo aur SUBSCRIBE karo 🔔\\nBell dabana mat bhoolna!\\n\\n#viral #trending #shorts #desilife #villagelife #pakistan #gaon #punjab #desi #village #reels #fyp #foryou #tiktok #desilifeofficial #DesiLifeOfficial", "tags":["village shorts viral","desi shorts trending","gaon ki kahani","DesiLifeOfficial","reels viral","punjab village","pakistan village life","fyp","foryou","tiktok viral","shorts viral"], "pexels_queries":["{topic} pakistan village vertical","village pakistan portrait","pakistan village life vertical"], "urdu_voice":"Dekho doston! {topic} gaon ki zindagi ka sabse khoobsurat raaz hai! Yahan subah 5 baje thandi hawa, khule khet, aur logon ka pyaar! Sheher wale is sukoon ke liye taraste hain! Ye hai asli Pakistan! Video pasand aaye to Like Share Subscribe zaroor karen aur comment me batao apka gaon kahan hai?", "caption":"{topic.upper()[:35]} 😱🔥"}}"""
    else:
        random.seed(f"{today}-{seed}-long")
        topic = random.choice(LONG_TOPICS)
        random.seed()
        
        prompt = f"""You are top Pakistani village vlogger for 1M views. ONLY valid JSON.
Topic: {topic}
DateSeed: {today}-{seed}-long
Avoid old: {used}
Need LONG 420-500 words urdu_voice, 4 paras, HOOK in first 10 sec, emotional + money/earning angle for retention.

VIRAL RULES:
- Title: 70 chars, include number, hook, | Desi Life Official, e.g. "5 Din Me 1 Lakh? {topic.title()} | Desi Life Official"
- Description: SEO, timestamps 00:00 Intro 01:00 Main 03:00 End, 20 hashtags, CTA Subscribe
- Tags: 15 tags trending

JSON:
{{"title":"{topic.title()} - 1 Din Me Kaise Hota Hai? Full Detail | Desi Life Official", "description":"Aaj ki video me {topic} ki poori kahani! Gaon ki asli zindagi dekho 🔥\\n\\n00:00 Intro - {topic} kya hai?\\n01:00 Main Story - Gaon ka tareeqa\\n03:00 End - Apka sawal?\\n\\n👉 LIKE karo agar gaon pasand hai\\n👉 SHARE karo doston se\\n👉 SUBSCRIBE + Bell 🔔 dabao\\n\\n#DesiLife #VillageLife #Gaon #PakistanVillage #DesiLifeOfficial #GaonKiKahani #VillageVlog #Pakistan #Punjab #Desi #Viral #Trending #VillageLifePakistan #GaonKiZindagi #DesiFood\\n\\nFull video on TikTok: Desi Life Official", "tags":["village life pakistan viral","desi life official","gaon ki kahani trending","pakistan village vlog 2026","village life earning","punjab village life","desi village","gaon ki zindagi","village earning","pakistan gaon","viral village","desi life","village vlog pakistan","gaon","desi"], "pexels_queries":["{topic} pakistan village","pakistan village life horizontal","village pakistan house"], "urdu_voice":"Assalam-o-Alaikum pyare doston! Dekho aaj ka topic sunke aap hairan ho jaoge - {topic}! Doston gaon ki zindagi me itna sukoon hai ke sheher wale taraste hain! Subah 5 baje azan, thandi hawa, aur khet sone jaise chamak rahe! {topic} hamari 100 saal purani riwayat hai! Buzurg kehte hain gaon ki mitti me barkat hai! Yahan 1 din me log itna kamate hain ke sheher me mahina lag jata! {topic} se mahine ke 30 hazar tak kamai hoti hai! Bachpan yaad ayega! Agar video pasand aaye to LIKE karo, SHARE karo, channel ko SUBSCRIBE karo aur bell dabao! Comment me batao apka gaon kahan hai aur {topic} apko kaisa laga? Aapke pyare comments ka intezar rahega! Allah Hafiz!", "caption":"{topic.title()[:40]} 🔥"}}"""

    for m in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-001"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:].strip()
            data = json.loads(txt)
            if "urdu_voice" in data and len(data["urdu_voice"]) > 25:
                print(f"Gemini {m} SUCCESS - Topic: {topic}")
                return data
        except Exception as e:
            print(f"{m} fail {str(e)[:120]}")
            continue
    
    # Final fallback with date-unique topic
    fallback_topic = f"Gaon Ki Kahani {today} {seed}"
    print(f"Using FALLBACK unique topic: {fallback_topic}")
    return {
        "title": f"{topic.title()} {today} | Desi Life Official",
        "description": f"{topic} - Gaon ki khoobsurat kahani #{today} #desilife #villagelife",
        "tags": ["village life", f"gaon {seed}", "desi life"],
        "pexels_queries": [f"{topic} pakistan {'vertical' if is_short else 'horizontal'}", "village pakistan"],
        "urdu_voice": f"Assalam-o-Alaikum doston! Aaj hum baat karenge {topic} ke bare me. Gaon ki zindagi bohat khoobsurat hai. Yahan subah thandi hawa chalti hai, kisan khet me kaam karta hai, aur sham ko sab mil kar baithte hain. {topic} hamari pehchan hai. Video pasand aaye to Like Subscribe zaroor karen.",
        "caption": topic.upper()[:40]
    }


def download_pexels(queries, history, count, is_short):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used = set(history.get("used_video_ids", []))
    
    # For shorts, prefer vertical videos
    orientation = "portrait" if is_short else "landscape"
    
    search_queries = queries + (["village pakistan portrait vertical reel" if is_short else "village pakistan horizontal"]*2)
    
    for q in search_queries[:7]:
        if len(clips) >= count: break
        try:
            page = random.randint(1, 5)
            # Add orientation param for Pexels
            url = f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}&orientation={orientation}"
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code != 200: 
                # try without orientation
                res = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}", headers=headers, timeout=30)
                if res.status_code != 200: continue
            vids = res.json().get("videos", [])
            if not vids: continue
            fresh = [v for v in vids if v["id"] not in used]
            pool = fresh if len(fresh) >= 2 else vids
            
            for v in random.sample(pool, min(3, len(pool))):
                if len(clips) >= count: break
                # Select best quality
                mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4"]
                if not mp4s: continue
                
                if is_short:
                    # For vertical, prefer tall videos (height > width)
                    vertical = [f for f in mp4s if f["height"] > f["width"]]
                    candidates = vertical if vertical else mp4s
                    # Pick 720 width or 1080
                    candidates = sorted(candidates, key=lambda x: x["width"])
                    # Take middle quality to avoid huge files
                    link = candidates[min(2, len(candidates)-1)]["link"] if len(candidates)>2 else candidates[-1]["link"]
                else:
                    # Horizontal - prefer 1280x720 or 1920x1080
                    horiz = [f for f in mp4s if f["width"] >= f["height"]]
                    candidates = horiz if horiz else mp4s
                    # Filter 1280-1920 width
                    good = [f for f in candidates if 1280 <= f["width"] <= 1920]
                    candidates = good if good else candidates
                    link = sorted(candidates, key=lambda x: x["width"])[-1]["link"]
                
                print(f"BG {len(clips)+1}: {q} [{orientation}] ID {v['id']} -> {link[:60]}")
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

def create_caption_image(caption_text, is_short, video_width, video_height):
    from PIL import Image, ImageDraw, ImageFont
    caption_text = caption_text.upper()[:50]
    
    if is_short:
        # VIRAL STYLE - BIGGER + YELLOW + BLACK OUTLINE for Shorts
        img_w, img_h = int(video_width*0.92), 180
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 68)
        except:
            font = ImageFont.load_default()
        # Thick black outline for viral
        for dx in (-5,-4,-3,-2,-1,0,1,2,3,4,5):
            for dy in (-5,-4,-3,-2,-1,0,1,2,3,4,5):
                if abs(dx)+abs(dy) > 6: continue
                draw.text((img_w//2+dx, img_h//2+dy), caption_text, font=font, fill=(0,0,0,255), anchor="mm", align="center")
        # Yellow text for CTR
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,235,0,255), anchor="mm", align="center")
    else:
        # LONG - white with shadow
        img_w, img_h = int(video_width*0.85), 95
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,185))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        except:
            font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def create_thumbnail(title, is_short):
    """VIRAL Thumbnail generator - CTR boost"""
    from PIL import Image, ImageDraw, ImageFont
    tw, th = (1280, 720) if not is_short else (720, 1280)
    img = Image.new('RGB', (tw, th), (20, 120, 60))  # Green village
    draw = ImageDraw.Draw(img)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80 if not is_short else 70)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Text with stroke
    txt = title[:30].upper()
    draw.text((tw//2, th//2), txt, font=font_big, fill=(255,255,0), anchor="mm", stroke_width=8, stroke_fill=(0,0,0))
    draw.text((tw//2, int(th*0.75)), "Desi Life Official", font=font_small, fill=(255,255,255), anchor="mm", stroke_width=4, stroke_fill=(0,0,0))
    
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    img.save(path, "JPEG", quality=95)
    return path

def create_subscribe_endcard(is_short, tw, th):
    """End screen 3 sec - Subscribe + Bell + Desi Life Official"""
    from PIL import Image, ImageDraw, ImageFont
    # Background - YouTube style dark gradient
    img = Image.new('RGB', (tw, th), (18, 18, 18))
    draw = ImageDraw.Draw(img)
    
    # Red accent bar top
    draw.rectangle([0, 0, tw, int(th*0.08)], fill=(255, 0, 0))
    
    # Fonts
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.09) if is_short else int(th*0.10))
        font_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.045) if is_short else int(th*0.055))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(th*0.03) if is_short else int(th*0.04))
    except:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    if is_short:
        # VERTICAL 1080x1920
        # Bell icon text
        draw.text((tw//2, int(th*0.22)), "🔔", font=font_big, fill=(255,255,255), anchor="mm")
        draw.text((tw//2, int(th*0.32)), "SUBSCRIBE", font=font_big, fill=(255,0,0), anchor="mm", stroke_width=2, stroke_fill=(255,255,255))
        draw.text((tw//2, int(th*0.42)), "KAREN", font=font_big, fill=(255,255,255), anchor="mm")
        # Channel name
        draw.text((tw//2, int(th*0.55)), "Desi Life Official", font=font_mid, fill=(255,255,0), anchor="mm")
        draw.text((tw//2, int(th*0.62)), "Bell Icon Dabayen", font=font_small, fill=(200,200,200), anchor="mm")
        draw.text((tw//2, int(th*0.68)), "Har Video Sabse Pehle", font=font_small, fill=(180,180,180), anchor="mm")
        # Red subscribe button mock
        btn_w, btn_h = int(tw*0.70), int(th*0.07)
        btn_x1, btn_y1 = (tw-btn_w)//2, int(th*0.75)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=20, fill=(255,0,0))
        draw.text((tw//2, btn_y1+btn_h//2), "SUBSCRIBED ✓", font=font_mid, fill=(255,255,255), anchor="mm")
        draw.text((tw//2, int(th*0.92)), "Like | Share | Comment", font=font_small, fill=(150,150,150), anchor="mm")
    else:
        # HORIZONTAL 1920x1080
        draw.text((tw//2, int(th*0.25)), "🔔  SUBSCRIBE KAREN  🔔", font=font_big, fill=(255,255,255), anchor="mm", stroke_width=3, stroke_fill=(0,0,0))
        draw.text((tw//2, int(th*0.45)), "Desi Life Official", font=font_mid, fill=(255,255,0), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        draw.text((tw//2, int(th*0.55)), "Bell Icon Dabana Mat Bhoolen | Har Video Sabse Pehle Dekhen", font=font_small, fill=(220,220,220), anchor="mm")
        # Red button
        btn_w, btn_h = int(tw*0.30), int(th*0.12)
        btn_x1, btn_y1 = (tw-btn_w)//2, int(th*0.68)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=15, fill=(255,0,0))
        draw.text((tw//2, btn_y1+btn_h//2), "SUBSCRIBE ✓", font=font_mid, fill=(255,255,255), anchor="mm")
        draw.text((tw//2, int(th*0.90)), "Like  •  Share  •  Comment  •  Desi Life Official", font=font_small, fill=(180,180,180), anchor="mm")
    
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def resize_and_crop(clip, target_size):
    """Resize and crop to fill target_size without distortion - NO GLITCH"""
    tw, th = target_size
    # Calculate resize to fill
    cw, ch = clip.w, clip.h
    # Scale to fill
    scale_w = tw / cw
    scale_h = th / ch
    scale = max(scale_w, scale_h)  # Fill mode
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    clip = clip.resize((new_w, new_h))
    # Center crop
    x_center = new_w // 2
    y_center = new_h // 2
    x1 = x_center - tw // 2
    y1 = y_center - th // 2
    clip = clip.crop(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)
    return clip

def make_video(paths, urdu_text, caption, is_short):
    target_size = SHORT_SIZE if is_short else LONG_SIZE
    tw, th = target_size
    print(f"Making video {tw}x{th} caption={caption} is_short={is_short} VOICE={VOICE_GENDER} MALE")
    
    # === MALE VOICE GENERATION ===
    a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    audio = None
    
    # Try Edge-TTS male voice first (ur-PK-AsadNeural - Male)
    try:
        import edge_tts
        import asyncio
        
        voice_to_use = VOICE_NAME_MALE if VOICE_GENDER == "male" else VOICE_NAME_FEMALE
        print(f"Trying Edge-TTS male voice: {voice_to_use}")
        
        async def generate_edge_tts():
            communicate = edge_tts.Communicate(urdu_text, voice_to_use)
            await communicate.save(a_path)
        
        asyncio.run(generate_edge_tts())
        audio = AudioFileClip(a_path)
        print(f"Edge-TTS MALE SUCCESS - duration {audio.duration:.1f}s")
    except Exception as e:
        print(f"Edge-TTS male failed {e}, trying gTTS male style")
        try:
            # gTTS with male-sounding tld - com is deeper male voice
            tts = gTTS(text=urdu_text, lang='ur', slow=False, tld='com')
            tts.save(a_path)
            audio = AudioFileClip(a_path)
            print(f"gTTS ur male style SUCCESS")
        except Exception as e2:
            print(f"gTTS ur failed {e2}, trying en male")
            try:
                tts = gTTS(text=urdu_text, lang='en', slow=False, tld='co.uk')  # UK male deeper
                tts.save(a_path)
                audio = AudioFileClip(a_path)
            except Exception as e3:
                print(f"All TTS failed {e3}, using fallback")
                tts = gTTS(text=urdu_text, lang='ur', slow=False)
                tts.save(a_path)
                audio = AudioFileClip(a_path)
    
    print(f"Audio duration {audio.duration:.1f}s - MALE VOICE")
    
    vcs = []
    per = audio.duration / len(paths) if paths else audio.duration
    
    for p in paths:
        try:
            vc = VideoFileClip(p)
            # Fix glitch: ensure even dimensions after crop
            vc = resize_and_crop(vc, target_size)
            # Subclip
            s = random.uniform(0, max(0, vc.duration - per - 0.3))
            vc = vc.subclip(s, s+per+0.5)
            vcs.append(vc)
        except Exception as e:
            print(f"clip err {e}")
            continue
    
    if not vcs:
        raise Exception("No clips usable")
    
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration:
        final_v = final_v.loop(duration=audio.duration)
    else:
        final_v = final_v.subclip(0, audio.duration)
    
    # Ensure final size is exact target and even
    final_v = resize_and_crop(final_v, target_size)
    
    # Caption
    cap_path = create_caption_image(caption, is_short, tw, th)
    cap_clip = ImageClip(cap_path).set_duration(audio.duration)
    if is_short:
        cap_clip = cap_clip.set_position(('center', th*0.78))
    else:
        cap_clip = cap_clip.set_position(('center', th*0.82))
    
    final = CompositeVideoClip([final_v, cap_clip], size=target_size).set_audio(audio)
    
    # === NEW: Subscribe End Screen (3 sec) ===
    print(f"Creating subscribe endcard...")
    endcard_path = create_subscribe_endcard(is_short, tw, th)
    endcard_clip = ImageClip(endcard_path).set_duration(3)  # 3 sec end screen
    
    # Concatenate main video + endcard
    final_with_endcard = concatenate_videoclips([final, endcard_clip], method="compose")
    print(f"Final video with endcard duration: {final_with_endcard.duration:.1f}s (main {audio.duration:.1f}s + 3s endcard)")
    
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    # High quality, no glitch params
    final_with_endcard.write_videofile(
        out, 
        codec='libx264', 
        audio_codec='aac', 
        fps=24, 
        preset='ultrafast', 
        ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
        threads=4,
        logger=None
    )
    print(f"Final video {out} size {tw}x{th} with subscribe end screen")
    return out

def build_youtube_client():
    for scopes in [
        ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.upload"],
        ["https://www.googleapis.com/auth/youtube.upload"]
    ]:
        try:
            creds = Credentials(None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"], scopes=scopes)
            yt = build("youtube","v3", credentials=creds)
            yt.channels().list(part="snippet", mine=True).execute()
            return yt
        except Exception as e:
            print(f"YT scope {scopes} failed {e}")
            continue
    raise Exception("YOUTUBE_REFRESH_TOKEN invalid")

def get_or_create_playlist(youtube, history, title, is_short):
    key = "short" if is_short else "long"
    if key in history.get("playlists", {}) and history["playlists"][key]:
        return history["playlists"][key]
    try:
        pls = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for pl in pls.get("items", []):
            if title.lower() in pl["snippet"]["title"].lower() or pl["snippet"]["title"].lower() in title.lower():
                history["playlists"][key] = pl["id"]
                return pl["id"]
    except:
        return None
    try:
        body = {"snippet": {"title": title, "description": f"{title} auto"}, "status": {"privacyStatus": "public"}}
        resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
        history["playlists"][key] = resp["id"]
        print(f"Created playlist {title} -> {resp['id']}")
        return resp["id"]
    except Exception as e:
        print(f"Playlist skip {e}")
        return None


def upload_to_facebook(video_path, title, description, is_short):
    # AUTO REFRESH - try to get fresh token every run
    fresh_token = get_fresh_page_token()
    if not FB_PAGE_ID or not fresh_token:
        print("FB credentials not set, skipping. Set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN or FB_USER_TOKEN")
        return None
    
    # Clean token
    token = fresh_token.strip()
    if not token.startswith("EAA"):
        print(f"WARNING: FB token looks invalid (should start with EAA): {token[:20]}...")
    
    try:
        # DEBUG: Check token permissions first
        try:
            perm_url = f"https://graph.facebook.com/v19.0/me/permissions?access_token={token}"
            perm_res = requests.get(perm_url, timeout=10)
            print(f"Token permissions check: {perm_res.status_code} {perm_res.text[:800]}")
            # Check if pages_manage_posts exists
            if "pages_manage_posts" not in perm_res.text:
                print("WARNING: pages_manage_posts NOT in token! This will cause Error 100!")
        except Exception as e:
            print(f"Permission check error: {e}")

        # Try 2 endpoints for Error 100 fix
        endpoints_to_try = [
            f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos",
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
        ]
        
        response = None
        for attempt, url in enumerate(endpoints_to_try):
            try:
                if is_short:
                    print(f"Uploading to Facebook Page {FB_PAGE_ID} as REEL/SHORT - Title: {title} (Attempt {attempt+1})")
                    print(f"FB Upload URL: {url}")
                    with open(video_path, 'rb') as f:
                        files = {'source': f}
                        data = {
                            'title': title[:120],
                            'description': f"{title}\n\n{description}\n\n#DesiLife #Reels #VillageLife #Shorts #DesiLifeOfficial",
                            'access_token': token
                        }
                        response = requests.post(url, files=files, data=data, timeout=600)
                    print(f"FB Short Response: {response.status_code} {response.text[:1000]}")
                else:
                    print(f"Uploading to Facebook Page {FB_PAGE_ID} as LONG VIDEO - Title: {title} (Attempt {attempt+1})")
                    print(f"FB Upload URL: {url}")
                    with open(video_path, 'rb') as f:
                        files = {'source': f}
                        data = {
                            'title': title[:120],
                            'description': f"{title}\n\n{description}\n\n#DesiLife #VillageLife #Gaon #PakistanVillage\nFull video on YouTube: Desi Life Official",
                            'access_token': token
                        }
                        response = requests.post(url, files=files, data=data, timeout=600)
                    print(f"FB Long Response: {response.status_code} {response.text[:1000]}")
                
                # If success or error is not 100, break
                if response.status_code == 200:
                    break
                if response.status_code == 400 and "100" not in response.text:
                    break
                # If Error 100, try next endpoint
                if attempt == 0 and "100" in response.text:
                    print(f"Error 100 on first endpoint, trying fallback endpoint...")
                    time.sleep(2)
                    continue
                else:
                    break
            except Exception as e:
                print(f"Upload attempt {attempt+1} error: {e}")
                continue
        
        if response.status_code == 200:
            result = response.json()
            fb_video_id = result.get('id') or result.get('post_id') or result.get('video_id')
            print(f"FB SUCCESS ID: {fb_video_id} Full: {result}")
            return fb_video_id
        else:
            print(f"FB Upload failed: {response.status_code} - {response.text}")
            try:
                err = response.json().get('error', {})
                code = err.get('code')
                msg = err.get('message','')
                if code == 190:
                    print("===== FB ERROR 190 FIX =====")
                    print("Token expired! Your FB_PAGE_ACCESS_TOKEN is dead.")
                    print("QUICK FIX: Graph Explorer -> me/accounts -> new Page token -> update GitHub Secret FB_PAGE_ACCESS_TOKEN")
                    print("PERMANENT: Add FB_USER_TOKEN (60 days), FB_APP_ID, FB_APP_SECRET secrets")
                    print("============================")
                elif code == 100 and "No permission to publish" in msg:
                    print("===== FB ERROR 100 FIX - NO PERMISSION =====")
                    print(f"Token: {token[:20]}... Page: {FB_PAGE_ID}")
                    print("This means Page token has NO pages_manage_posts permission!")
                    print("FIX STEPS:")
                    print("1. Go https://developers.facebook.com/tools/explorer/")
                    print("2. Select YOUR APP (not Graph Explorer app)")
                    print("3. In Permissions, ADD: pages_show_list, pages_read_engagement, pages_manage_posts, publish_video")
                    print("4. IMPORTANT: Select 'Page Access Token' NOT User Token -> Choose your Page")
                    print("5. Generate -> Copy EAA... token")
                    print("6. Check token: https://developers.facebook.com/tools/debug/accesstoken/ - must show pages_manage_posts")
                    print("7. GitHub -> Secrets -> FB_PAGE_ACCESS_TOKEN = new token")
                    print("8. Also update FB_USER_TOKEN with new 60-day User token (with same permissions)")
                    print("If App is in Development Mode, make sure YOU are Admin of App + Page!")
                    # Debug token permissions
                    try:
                        dbg_url = f"https://graph.facebook.com/v19.0/me/permissions?access_token={token}"
                        dbg = requests.get(dbg_url, timeout=10).json()
                        print(f"Token permissions debug: {dbg}")
                    except Exception as e:
                        print(f"Permission check failed: {e}")
                    print("============================")
            except Exception as e:
                print(f"Error parse failed: {e}")
            return None
            
    except Exception as e:
        print(f"Facebook upload error: {e}")
        import traceback
        traceback.print_exc()
        return None


def upload_to_youtube_and_fb(file_path, title, desc, tags, is_short, history):
    youtube = build_youtube_client()
    # YouTube title limit
    yt_title = title[:95] if not is_short else title[:95]
    
    body = {"snippet":{"title":yt_title,"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"YouTube Upload {int(st.progress()*100)}%")
    vid = resp.get('id')
    print(f"YouTube SUCCESS https://youtu.be/{vid} (is_short={is_short})")
    
    # Playlist
    try:
        pid = get_or_create_playlist(youtube, history, SHORT_TITLE if is_short else LONG_TITLE, is_short)
        if pid:
            youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            print(f"Added to YT playlist {pid}")
    except Exception as e:
        print(f"YT Playlist skip {e}")
    
    # Facebook Upload
    print("--- Starting Facebook Page Upload ---")
    fb_id = upload_to_facebook(file_path, title, desc, is_short)
    if fb_id:
        print(f"FB SUCCESS: {fb_id}")
    else:
        print(f"Facebook skipped/failed")
    
    # TikTok - DISABLED as per user request
    tt_id = None
    if TIKTOK_ENABLED:
        print("--- Starting TikTok Upload ---")
        tt_id = upload_to_tiktok(file_path, title, desc, is_short)
        if tt_id:
            print(f"TIKTOK SUCCESS: {tt_id}")
        else:
            print(f"TikTok skipped/failed")
    else:
        print("--- TikTok DISABLED by user - Skipping ---")
    
    # Summary
    print(f"=== DUAL UPLOAD COMPLETE === YT: https://youtu.be/{vid} | FB: {fb_id} | TT: DISABLED")
    
    return resp

def upload_to_tiktok(video_path, title, description, is_short):
    """Upload to TikTok - DISABLED, kept for future use"""
    if not TIKTOK_ENABLED:
        print("TikTok is DISABLED - user request")
        return None
    if not TIKTOK_ACCESS_TOKEN:
        print("TIKTOK_ACCESS_TOKEN not set, skipping TikTok")
        return None
    
    try:
        # Check file size
        file_size = os.path.getsize(video_path)
        print(f"TikTok: File size {file_size/1024/1024:.1f} MB, is_short={is_short}")
        
        # Step 1: Init upload
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        
        # Title + hashtags for TikTok
        tt_title = f"{title[:90]} #DesiLife #VillageLife #Gaon #Pakistan #Desi #Village"
        
        init_data = {
            "post_info": {
                "title": tt_title[:220],  # TikTok max 220 chars
                "privacy_level": "PUBLIC",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1
            }
        }
        
        print(f"TikTok Init: {tt_title[:80]}...")
        res = requests.post(init_url, headers=headers, json=init_data, timeout=30)
        print(f"TikTok Init Response: {res.status_code} {res.text[:1000]}")
        
        if res.status_code != 200:
            print(f"TikTok init failed: {res.text}")
            return None
        
        data = res.json()
        if data.get("error", {}).get("code") != "ok" and "data" not in data:
            print(f"TikTok init error: {data}")
            return None
        
        publish_id = data.get("data", {}).get("publish_id")
        upload_url = data.get("data", {}).get("upload_url")
        
        if not upload_url or not publish_id:
            print(f"TikTok init missing upload_url/publish_id: {data}")
            return None
        
        # Step 2: Upload video file to upload_url
        print(f"TikTok uploading video to {upload_url[:80]}...")
        with open(video_path, 'rb') as f:
            # TikTok expects PUT with video bytes, Content-Range header
            put_headers = {
                "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                "Content-Type": "video/mp4"
            }
            put_res = requests.put(upload_url, headers=put_headers, data=f, timeout=300)
            print(f"TikTok PUT Response: {put_res.status_code} {put_res.text[:500]}")
            
            if put_res.status_code not in [200, 201, 204]:
                print(f"TikTok upload PUT failed")
                return None
        
        # Step 3: Publish is auto after upload for FILE_UPLOAD
        # Check status (optional)
        print(f"TikTok upload complete! Publish ID: {publish_id}")
        
        # Optional: Check publish status after few seconds
        time.sleep(2)
        status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
        status_data = {"publish_id": publish_id}
        try:
            status_res = requests.post(status_url, headers=headers, json=status_data, timeout=10)
            print(f"TikTok Status: {status_res.status_code} {status_res.text[:800]}")
        except Exception as e:
            print(f"TikTok status check skip: {e}")
        
        return publish_id
        
    except Exception as e:
        print(f"TikTok upload error: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_once(is_short=False):
    h = load_history()
    print(f"--- {'SHORT 1080x1920 REEL' if is_short else 'LONG 1920x1080 VIDEO'} START ---")
    data = get_script(is_short, h)
    print(f"Title: {data['title']} | Caption: {data['caption']} | Size: {SHORT_SIZE if is_short else LONG_SIZE}")
    h["used_titles"].append(data["title"])
    h["used_titles"] = h["used_titles"][-60:]
    
    clips = download_pexels(data["pexels_queries"], h, count=2 if is_short else 4, is_short=is_short)
    if not clips:
        raise Exception("No Pexels clips")
    print(f"Clips downloaded {len(clips)}")
    
    final = make_video(clips, data["urdu_voice"], data["caption"], is_short)
    upload_to_youtube_and_fb(final, data["title"], data["description"], data["tags"], is_short, h)
    save_history(h)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
