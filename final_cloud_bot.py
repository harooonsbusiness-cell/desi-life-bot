
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

def get_gemini_data(is_short, history):
    client = genai.Client(api_key=GEMINI_KEY)
    used = ", ".join(history["used_titles"][-8:]) if history["used_titles"] else "none"
    if is_short:
        topic = random.choice(['gaon ki subah', 'desi khana chulhe par', 'khet me kaam', 'bail gadi', 'mitti ka chulha', 'gaon ka mela'])
        prompt = f"""ONLY valid JSON no markdown SHORT 32 sec Topic {topic} Avoid {used} Seed {random.randint(1,99999)}
        JSON: {{"title":"{topic.title()} | Desi Life Official #shorts", "description":"{topic} #shorts #desilife", "tags":["village","desi","shorts"], "pexels_queries":["{topic} pakistan", "village pakistan"], "urdu_voice":"Gaon ki subah bohat khoobsurat hoti hai. Kisan khet me jata hai.", "caption":"{topic.upper()}"}}"""
    else:
        topics = ['gaon ki shaadi kaise hoti hai', 'gandum ki fasal kaise ugate hain', 'desi khana mitti ke chulhe par', 'gaon ki subah se shaam', 'barish ke baad gaon', 'gaon ke mele ki raunaq']
        topic = random.choice(topics)
        prompt = f"""ONLY valid JSON no markdown LONG 3.5min Topic {topic} Avoid {used} Rand {random.randint(1,99999)}
        Write 400 words urdu_voice 3 paras desi style
        JSON: {{"title":"{topic.title()} - Gaon Ki Asli Kahani | Desi Life Official", "description":"Aaj {topic} dekhte hain. Gaon ki zindagi khoobsurat hai. #desilife #villagelife #DesiLifeOfficial", "tags":["village life","desi life"], "pexels_queries":["{topic} pakistan village", "pakistan village house", "village life pakistan"], "urdu_voice":"Assalam-o-Alaikum doston! Desi Life Official me khush amdeed. Aaj hum baat karenge {topic} ke bare me. Gaon me subah sukoon hota hai. Kisan khet jata hai, aurtein chulhe par nashta banati hain. Gaon ki zindagi me alag maza hai. {topic} gaon ki pehchan hai. Yahan sab mil jul kar kaam karte hain. Doston agar gaon pasand hai to like subscribe karen. Shukriya!", "caption":"{topic.title()}"}}"""
    for m in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-1.5-flash-latest", "gemini-1.5-flash"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:]
            data = json.loads(txt)
            print(f"Gemini {m} success")
            return data
        except Exception as e:
            print(f"{m} fail {str(e)[:120]}")
            continue
    return {
        "title": f"Gaon Ki Kahani {random.randint(1,9999)} | Desi Life Official",
        "description": "#desilife #village #DesiLifeOfficial",
        "tags": ["village"],
        "pexels_queries": ["village pakistan", "pakistan village"],
        "urdu_voice": "Gaon ki zindagi khoobsurat hoti hai.",
        "caption": "GAON KI ZINDAGI"
    }

def download_pexels(queries, history, count):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used = set(history.get("used_video_ids", []))
    for q in (queries + ["village pakistan", "pakistan village"])[:6]:
        if len(clips) >= count: break
        try:
            page = random.randint(1,4)
            res = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=15&page={page}", headers=headers, timeout=30)
            if res.status_code != 200: continue
            vids = res.json().get("videos", [])
            fresh = [v for v in vids if v["id"] not in used]
            pool = fresh if fresh else vids
            for v in random.sample(pool, min(2, len(pool))):
                if len(clips) >= count: break
                mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4" and 640 <= f["width"] <= 1280]
                if not mp4s: mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4" and f["width"] <= 1920]
                if not mp4s: continue
                link = sorted(mp4s, key=lambda x: x["width"])[-1]["link"]
                print(f"BG {len(clips)+1}: {q} ID {v['id']}")
                data = requests.get(link, timeout=120).content
                if len(data) < 80000: continue
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp.write(data); tmp.close()
                clips.append(tmp.name)
                history["used_video_ids"].append(v["id"])
                history["used_video_ids"] = history["used_video_ids"][-200:]
        except: continue
    if len(clips)==1 and count>1:
        clips = clips*count
    return clips

def create_caption_image(caption_text, is_short, video_width=1280):
    from PIL import Image, ImageDraw, ImageFont
    caption_text = caption_text.upper()[:45]
    if is_short:
        img_w, img_h = int(video_width*0.88), 130
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        except:
            font = ImageFont.load_default()
        for dx in (-3,-2,-1,0,1,2,3):
            for dy in (-3,-2,-1,0,1,2,3):
                draw.text((img_w//2+dx, img_h//2+dy), caption_text, font=font, fill=(0,0,0,230), anchor="mm", align="center")
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    else:
        img_w, img_h = int(video_width*0.84), 80
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,165))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def make_video(paths, urdu_text, caption, is_short):
    print(f"Making video caption={caption}")
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
    print(f"Audio {audio.duration:.1f}s")
    vcs = []
    per = audio.duration / len(paths) if paths else audio.duration
    for p in paths:
        try:
            vc = VideoFileClip(p).resize((1280, 720))
            s = random.uniform(0, max(0, vc.duration - per - 0.2))
            vc = vc.subclip(s, s+per+0.4)
            vcs.append(vc)
        except Exception as e:
            print(f"clip err {e}")
    if not vcs:
        raise Exception("No clips")
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration:
        final_v = final_v.loop(duration=audio.duration)
    else:
        final_v = final_v.subclip(0, audio.duration)
    cap_path = create_caption_image(caption, is_short, video_width=1280)
    cap_clip = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip = cap_clip.set_position('center' if is_short else ('center', 0.80), relative=True if not is_short else False)
    final = CompositeVideoClip([final_v, cap_clip], size=(1280,720)).set_audio(audio)
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final.write_videofile(out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"], logger=None)
    print(f"Final video {out}")
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
    """Upload video to Facebook Page"""
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("FB credentials not set, skipping FB upload. Set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN")
        return None
    
    try:
        print(f"Uploading to Facebook Page {FB_PAGE_ID} - Title: {title}")
        # Facebook Graph API for Page video upload
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos"
        
        # For short videos -> Reels, for long -> Video
        # Use same endpoint, FB auto detects
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {
                'title': title[:120],
                'description': f"{title}\n\n{description}\n\n#DesiLife #VillageLife #Gaon #PakistanVillage",
                'access_token': FB_PAGE_TOKEN
            }
            # Add reel specific if short
            if is_short:
                # For reels, use video upload then share as reel - simple video post works as reel if <90s and vertical-ish but ours is horizontal so will be video
                print("Uploading as FB Video (short will appear as Reel if <90s)")
            
            response = requests.post(url, files=files, data=data, timeout=300)
        
        print(f"FB Response: {response.status_code} {response.text[:500]}")
        
        if response.status_code == 200:
            result = response.json()
            fb_video_id = result.get('id')
            print(f"FB SUCCESS Video ID: {fb_video_id} https://www.facebook.com/{FB_PAGE_ID}/videos/{fb_video_id}")
            return fb_video_id
        else:
            print(f"FB Upload failed: {response.text}")
            # Try fallback to feed video
            return None
            
    except Exception as e:
        print(f"Facebook upload error: {e}")
        return None

def upload_to_youtube_and_fb(file_path, title, desc, tags, is_short, history):
    youtube = build_youtube_client()
    body = {"snippet":{"title":title[:95],"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"YouTube Upload {int(st.progress()*100)}%")
    vid = resp.get('id')
    print(f"YouTube SUCCESS https://youtu.be/{vid}")
    
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
        print(f"Dual upload complete! YT: https://youtu.be/{vid} FB: https://fb.com/{fb_id}")
    else:
        print(f"YouTube done, Facebook skipped or failed. YT: https://youtu.be/{vid}")
    
    return resp

def run_once(is_short=False):
    h = load_history()
    print(f"--- {'SHORT' if is_short else 'LONG'} START - FB + YT Dual ---")
    data = get_gemini_data(is_short, h)
    print(f"Title: {data['title']} Caption: {data['caption']}")
    h["used_titles"].append(data["title"])
    h["used_titles"] = h["used_titles"][-60:]
    clips = download_pexels(data["pexels_queries"], h, count=2 if is_short else 3)
    if not clips:
        raise Exception("No Pexels clips")
    print(f"Clips {len(clips)}")
    final = make_video(clips, data["urdu_voice"], data["caption"], is_short)
    upload_to_youtube_and_fb(final, data["title"], data["description"], data["tags"], is_short, h)
    save_history(h)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
