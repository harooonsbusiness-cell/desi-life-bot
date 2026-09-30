
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

def get_fresh_page_token():
    """AUTO REFRESH - Har run pe naya Page token le lega, kabhi expire nahi hoga!"""
    global FB_PAGE_TOKEN
    
    # If we have APP_ID + APP_SECRET + USER_TOKEN, we can auto refresh forever
    if FB_APP_ID and FB_APP_SECRET and FB_USER_TOKEN:
        try:
            print("--- AUTO REFRESH: Getting fresh Page token ---")
            # Step 1: Try to extend user token (if near expiry, get new 60-day token)
            try:
                exchange_url = f"https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id={FB_APP_ID}&client_secret={FB_APP_SECRET}&fb_exchange_token={FB_USER_TOKEN}"
                ex_res = requests.get(exchange_url, timeout=20)
                if ex_res.status_code == 200:
                    new_user_token = ex_res.json().get("access_token")
                    if new_user_token:
                        print(f"User token auto-extended to 60 days!")
                        # Use new token for next step
                        user_token_to_use = new_user_token
                    else:
                        user_token_to_use = FB_USER_TOKEN
                else:
                    user_token_to_use = FB_USER_TOKEN
            except Exception as e:
                print(f"Token extend skip: {e}")
                user_token_to_use = FB_USER_TOKEN
            
            # Step 2: Get fresh Page token from me/accounts
            url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={user_token_to_use}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                data = res.json()
                for page in data.get("data", []):
                    if page["id"] == FB_PAGE_ID or str(page["id"]) == str(FB_PAGE_ID):
                        fresh_token = page["access_token"]
                        print(f"AUTO REFRESH SUCCESS! Fresh Page token got for Page {FB_PAGE_ID}")
                        return fresh_token
                # If page not found, take first page token
                if data.get("data"):
                    fresh_token = data["data"][0]["access_token"]
                    print(f"AUTO REFRESH: Using first available page {data['data'][0]['id']}")
                    return fresh_token
            print(f"AUTO REFRESH failed: {res.text[:500]}")
        except Exception as e:
            print(f"AUTO REFRESH error: {e}")
    
    # Fallback to static token
    print(f"Using static FB_PAGE_ACCESS_TOKEN (may expire)")
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
    
    # 100 SHORT topics
    SHORT_TOPICS = [
        "gaon ki subah 5 baje", "chulhe par desi chai", "khet me bail gadi", "mitti ka chulha kaise jalate hain", "gaon ka nalka", "dadi ka charkha", "gaon ke bachche khelte hue", "khet me pani lagana", "gaon ki masjid", "sarson ka khet",
        "gandum ki katai", "bhains ka doodh nikalna", "gaon ka mela", "desi lassi banana", "khet me tractor chalana", "gaon ki shaam", "mitti ke ghar", "gaon ka kuwa", "desi khana chulhe par", "khet me parinde",
        "gaon ka bazar", "mitti ki khushbu", "gaon ki barish", "kisan ki subah", "desi charpai", "gaon ka school", "khet me dhan", "gaon ka chand", "desi achaar banana", "gaon ki holi ya eid"
    ]
    
    # 100 LONG topics
    LONG_TOPICS = [
        "gaon ki shaadi kaise hoti hai - poora riwaj", "gandum ki fasal ugane ka poora tarika", "chulhe par desi khana kaise banta hai", "gaon ki subah se shaam tak ki zindagi", "barish ke baad gaon ka khoobsurat manzar",
        "gaon ke mele ki raunaq aur khail", "kisan ki mehnat - khet se mandi tak", "mitti ke ghar kaise bante hain", "gaon me Eid kaise manate hain", "desi lassi aur makhan kaise banta hai",
        "gaon me pani ka intezam - kuwe aur nalke", "garmi me gaon ki thandi shaam", "sardi me gaon ka chulha aur kahani", "gaon ki aurat ki din bhar ki mehnat", "gaon ke bachchon ka school jana",
        "bail gadi se khet tak safar", "sarson ke khet ki khoobsurati", "aam ke bagh me garmi ka maza", "gaon ki biryani aur desi zaiqa", "mitti ke bartan kaise bante hain",
        "gaon me machhli pakadna", "gaon ka bazaar - sabzi mandi", "gaon me shadi ki taiyariyan", "khet me hal chalana - purana tareeqa", "gaon ki raat - chand aur sitare",
        "desi murgi palna gaon me", "gaon me bhains palna aur doodh", "gaon ka desi ilaj - jari bootiyan", "gaon ki kahani - buzurgon ki zuban se", "sheher aur gaon ki zindagi me farq"
    ]
    
    if is_short:
        # Har bar date + random se naya topic pick
        random.seed(f"{today}-{seed}")
        topic = random.choice(SHORT_TOPICS)
        random.seed()  # reset
        
        prompt = f"""You are viral Pakistani village shorts writer. ONLY valid JSON.
Topic: {topic}
DateSeed: {today}-{seed}
Avoid these old topics: {used}
Write like Claude/ChatGPT - natural, viral.
Need 35 sec Urdu script.

JSON ONLY:
{{"title":"{topic.title()} | Gaon Ki Kahani #shorts #DesiLife", "description":"{topic} - Gaon ki asli khoobsurati. #shorts #desilife #villagelife #reels #DesiLifeOfficial", "tags":["village shorts","desi shorts","gaon ki kahani","DesiLifeOfficial","reels"], "pexels_queries":["{topic} pakistan village vertical","village pakistan portrait","pakistan village life vertical"], "urdu_voice":"{topic} gaon ki zindagi ka khoobsurat hissa hai. Subah ki thandi hawa, khule khet, aur logon ka pyaar. Yahi hai asli sukoon jo sheher me nahi milta.", "caption":"{topic.upper()[:40]}"}}"""
    else:
        random.seed(f"{today}-{seed}-long")
        topic = random.choice(LONG_TOPICS)
        random.seed()
        
        prompt = f"""You are top Pakistani village vlogger like ChatGPT Claude. ONLY valid JSON.
Topic: {topic}
DateSeed: {today}-{seed}-long
Avoid old: {used}
Need LONG 380-450 words urdu_voice, 3 paras, emotional desi story. Title must include topic.
Write like human, not robot.

JSON:
{{"title":"{topic.title()} | Gaon Ki Asli Zindagi | Desi Life Official", "description":"Aaj ki video me hum dekhenge {topic}. Gaon ki zindagi, logon ka pyaar, aur desi culture ki khoobsurati.\n\nAgar video pasand aaye to Like, Share aur Subscribe zaroor karen!\n\n#DesiLife #VillageLife #Gaon #PakistanVillage #DesiLifeOfficial #GaonKiKahani #VillageVlog", "tags":["village life pakistan","desi life official","gaon ki kahani","pakistan village vlog","village life"], "pexels_queries":["{topic} pakistan village","pakistan village life horizontal","village pakistan house"], "urdu_voice":"Assalam-o-Alaikum pyare doston! Desi Life Official me aap sab ko khush amdeed. Aaj hum ek bohat hi khoobsurat topic par baat karenge - {topic}. Doston gaon ki zindagi ka apna hi maza hai. Yahan subah ki shuruat azan se hoti hai, thandi hawa chal rahi hoti hai, aur khet khule aasman ke neeche lehra rahe hote hain. {topic} hamari desi riwayat ka hissa hai. Ye kaam sadiyon se gaon me ho raha hai. Buzurg kehte hain ke gaon ki mitti me barkat hai. Yahan har shakhs ek dusre ka khayal rakhta hai. Sheher ki bhag daud se door, gaon me sukoon hai. {topic} ko dekh kar dil khush ho jata hai. Bachpan ki yaadein taza ho jati hain. Doston agar aapko bhi gaon ki ye khoobsurat zindagi pasand hai to video ko Like karen, channel ko Subscribe karen, aur comment me batayen aapka gaon kaisa hai aur aapko {topic} kaisa laga. Aapke comments ka intezar rahega. Milte hain agle video me, Allah Hafiz!", "caption":"{topic.title()[:40]}"}}"""

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
        # Vertical - bigger, center
        img_w, img_h = int(video_width*0.90), 160
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62)
        except:
            font = ImageFont.load_default()
        # Black outline
        for dx in (-4,-3,-2,-1,0,1,2,3,4):
            for dy in (-4,-3,-2,-1,0,1,2,3,4):
                if abs(dx)+abs(dy) > 5: continue
                draw.text((img_w//2+dx, img_h//2+dy), caption_text, font=font, fill=(0,0,0,230), anchor="mm", align="center")
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    else:
        # Horizontal - smaller bottom
        img_w, img_h = int(video_width*0.82), 90
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,175))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        except:
            font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    
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
    print(f"Making video {tw}x{th} caption={caption} is_short={is_short}")
    
    try:
        tts = gTTS(text=urdu_text, lang='ur', slow=False)
        a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        tts.save(a_path)
        audio = AudioFileClip(a_path)
    except:
        tts = gTTS(text=urdu_text, lang='en', slow=False)
        a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        tts.save(a_path)
        audio = AudioFileClip(a_path)
    
    print(f"Audio duration {audio.duration:.1f}s")
    
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
    
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    # High quality, no glitch params
    final.write_videofile(
        out, 
        codec='libx264', 
        audio_codec='aac', 
        fps=24, 
        preset='ultrafast', 
        ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
        threads=4,
        logger=None
    )
    print(f"Final video {out} size {tw}x{th}")
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
        # Use graph-video for video uploads - this fixes code 190 Invalid JSON error
        if is_short:
            print(f"Uploading to Facebook Page {FB_PAGE_ID} as REEL/SHORT - Title: {title}")
            # For Page reels, we use /videos with special description, FB auto detects as reel if 9:16 and <90s
            url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
            with open(video_path, 'rb') as f:
                files = {'source': f}
                data = {
                    'title': title[:120],
                    'description': f"{title}\n\n{description}\n\n#DesiLife #Reels #VillageLife #Shorts #DesiLifeOfficial",
                    'access_token': token
                }
                print(f"FB Upload URL: {url}")
                response = requests.post(url, files=files, data=data, timeout=600)
            print(f"FB Short Response: {response.status_code} {response.text[:1000]}")
        else:
            print(f"Uploading to Facebook Page {FB_PAGE_ID} as LONG VIDEO - Title: {title}")
            url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
            with open(video_path, 'rb') as f:
                files = {'source': f}
                data = {
                    'title': title[:120],
                    'description': f"{title}\n\n{description}\n\n#DesiLife #VillageLife #Gaon #PakistanVillage\nFull video on YouTube: Desi Life Official",
                    'access_token': token
                }
                print(f"FB Upload URL: {url}")
                response = requests.post(url, files=files, data=data, timeout=600)
            print(f"FB Long Response: {response.status_code} {response.text[:1000]}")
        
        if response.status_code == 200:
            result = response.json()
            fb_video_id = result.get('id') or result.get('post_id') or result.get('video_id')
            print(f"FB SUCCESS ID: {fb_video_id} Full: {result}")
            return fb_video_id
        else:
            print(f"FB Upload failed: {response.status_code} - {response.text}")
            # Try to parse error
            try:
                err = response.json().get('error', {})
                if err.get('code') == 190:
                    print("ERROR 190 = Token expired/invalid! Get new 60-day Page token from me/accounts")
                    print("Steps: Graph Explorer -> me/accounts -> copy Page token -> update GitHub Secret FB_PAGE_ACCESS_TOKEN")
            except:
                pass
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
        print(f"DUAL UPLOAD COMPLETE! YT: https://youtu.be/{vid} FB: {fb_id}")
    else:
        print(f"YouTube done, Facebook skipped/failed. YT: https://youtu.be/{vid}")
    
    return resp

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
