
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
    used = ", ".join(history["used_titles"][-8:]) if history["used_titles"] else "none"
    seed = random.randint(1, 999999)
    
    if is_short:
        topic = random.choice(['gaon ki subah', 'desi khana chulhe par', 'khet me tractor', 'bail gadi', 'mitti ka chulha', 'gaon ka mela', 'dadi ki kahani'])
        # Short prompt - 35 sec
        prompt = f"""You are viral shorts script writer. ONLY valid JSON no markdown.
Topic: {topic}
Avoid: {used}
Seed: {seed}
Need 35 sec Urdu script.

JSON format:
{{"title":"{topic.title()} | Gaon Ki Kahani #shorts", "description":"{topic} - Gaon ki khoobsurat zindagi #shorts #desilife #villagelife #reels", "tags":["village shorts","desi shorts","gaon"], "pexels_queries":["{topic} pakistan vertical","village pakistan vertical","pakistan village life"], "urdu_voice":"Gaon ki subah bohat khoobsurat hoti hai. Thandi hawa, khule khet, aur chiryon ki awaz. Yahi hai asli sukoon.", "caption":"{topic.upper()}"}}"""
    else:
        topics = ['gaon ki shaadi kaise hoti hai', 'gandum ki fasal kaise ugate hain', 'desi khana mitti ke chulhe par kaise banta hai', 'gaon ki subah se shaam tak routine', 'barish ke baad gaon ka manzar', 'gaon ke mele ki raunaq']
        topic = random.choice(topics)
        # Long prompt - 400 words, 3 paras, Claude/ChatGPT style allowed
        prompt = f"""You are best Pakistani village vlogger. Write like ChatGPT/Claude - natural desi story. ONLY valid JSON no markdown.
Topic: {topic}
Avoid: {used}
Rand: {seed}
Need long 4 min script, 380-450 words urdu_voice in 3 paragraphs, emotional desi style.

JSON:
{{"title":"{topic.title()} - Gaon Ki Asli Kahani | Desi Life Official", "description":"Aaj hum dekhenge {topic}. Gaon ki zindagi ka asli maza, logon ka pyaar, aur desi culture. Video pasand aaye to Like Subscribe zaroor karen.\n\n#DesiLife #VillageLife #Gaon #PakistanVillage #DesiLifeOfficial", "tags":["village life","desi life official","pakistan village","gaon ki kahani"], "pexels_queries":["{topic} pakistan village","pakistan village house life","village life pakistan"], "urdu_voice":"Assalam-o-Alaikum doston! Desi Life Official me khush amdeed. Aaj hum baat karenge {topic} ke bare me. Gaon me subah ka manzar bohat sukoon deta hai. Thandi hawa chal rahi hoti hai, kisan apne khet ki taraf ja rahe hote hain, aur gharon se chulhe ka dhuan uth raha hota hai. Gaon ki zindagi me ek alag hi maza hai. Yahan har koi ek dusre ko janta hai, mil jul kar rehta hai. {topic} hamari desi pehchan hai. Ye riwayat sadiyon se chali aa rahi hai. Sheher ki bhag daud se door, gaon me sukoon hai, pyaar hai, aur apnapan hai. Doston agar apko gaon ki ye kahani pasand aayi ho to video ko Like karen, Channel ko Subscribe karen, aur comment me batayen apka gaon kaisa hai. Shukriya!", "caption":"{topic.title()}"}}"""

    # Try all models - support Claude/ChatGPT style fallback
    for m in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-flash-latest"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:].strip()
            data = json.loads(txt)
            print(f"Gemini {m} success")
            # Validate
            if "urdu_voice" in data and len(data["urdu_voice"]) > 20:
                return data
        except Exception as e:
            print(f"{m} fail {str(e)[:150]}")
            continue
    
    # Fallback if Gemini fails - you can paste Claude/ChatGPT script here manually
    print("Using FALLBACK script - you can replace with Claude/ChatGPT script")
    return {
        "title": f"Gaon Ki Khoobsurat Zindagi {random.randint(1,9999)} | Desi Life Official",
        "description": "Gaon ki khoobsurat zindagi #desilife #villagelife #DesiLifeOfficial #reels",
        "tags": ["village life","desi life"],
        "pexels_queries": ["village pakistan vertical" if is_short else "village pakistan", "pakistan village life"],
        "urdu_voice": "Gaon ki zindagi bohat khoobsurat hoti hai. Subah sawere kisan khet me jata hai, aur sham ko sab mil kar baithte hain. Yahi asli sukoon hai.",
        "caption": "GAON KI ZINDAGI"
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
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("FB credentials not set, skipping. Set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN")
        return None
    
    try:
        if is_short:
            # FB Reel endpoint
            print(f"Uploading to Facebook Page {FB_PAGE_ID} as REEL - Title: {title}")
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/video_reels"
            # Reel needs special params
            with open(video_path, 'rb') as f:
                files = {'video_file_chunk': f}
                # First try reels endpoint with chunk upload - fallback to simple
                data = {
                    'title': title[:120],
                    'description': f"{title}\n\n{description}\n#DesiLife #Reels #VillageLife",
                    'access_token': FB_PAGE_TOKEN
                }
                # Try reels
                response = requests.post(url, files={'video_file': f}, data=data, timeout=400)
                # Re-read file for fallback
            print(f"FB Reel Response: {response.status_code} {response.text[:800]}")
            
            if response.status_code != 200:
                print("Reel endpoint failed, trying normal video endpoint for short")
                url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
                with open(video_path, 'rb') as f:
                    files = {'source': f}
                    data = {
                        'title': title[:120],
                        'description': f"{title}\n\n{description}\n#DesiLife #Reels",
                        'access_token': FB_PAGE_TOKEN
                    }
                    response = requests.post(url, files=files, data=data, timeout=400)
                print(f"FB Video (short) Response: {response.status_code} {response.text[:500]}")
        else:
            print(f"Uploading to Facebook Page {FB_PAGE_ID} as LONG VIDEO - Title: {title}")
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
            with open(video_path, 'rb') as f:
                files = {'source': f}
                data = {
                    'title': title[:120],
                    'description': f"{title}\n\n{description}\n\n#DesiLife #VillageLife #Gaon #PakistanVillage\nFull video on YouTube: Desi Life Official",
                    'access_token': FB_PAGE_TOKEN
                }
                response = requests.post(url, files=files, data=data, timeout=400)
            print(f"FB Long Response: {response.status_code} {response.text[:800]}")
        
        if response.status_code == 200:
            result = response.json()
            fb_video_id = result.get('id') or result.get('post_id')
            print(f"FB SUCCESS ID: {fb_video_id}")
            return fb_video_id
        else:
            print(f"FB Upload failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Facebook upload error: {e}")
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
