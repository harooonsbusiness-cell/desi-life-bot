
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

# PLAYLIST IDS - will be auto created first time
LONG_PLAYLIST_TITLE = "Desi Life Official - Long Videos 🌾"
SHORT_PLAYLIST_TITLE = "Desi Life Official - Shorts 🔥"

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
    used = ", ".join(history["used_titles"][-10:]) if history["used_titles"] else "none"
    
    if is_short:
        topic = random.choice(['gaon ki subah', 'desi khana chulhe par', 'khet me kaam', 'bail gadi', 'mitti ka chulha'])
        prompt = f"""ONLY JSON. No markdown. SHORT 32 sec. Topic: {topic}. Avoid: {used}. Seed {random.randint(1,99999)}.
        JSON: {{"title":"... | Desi Life Official #shorts", "description":"... #shorts #desilife", "tags":["village","desi","shorts"], "pexels_queries":["{topic} pakistan", "village pakistan"], "urdu_voice":"Gaon ki subah bohat khoobsurat hoti hai. Kisan subah jaldi uth kar khet me jata hai.", "caption":"{topic.upper()} - GAON KI ZINDAGI"}}"""
    else:
        topics = ['gaon ki shaadi kaise hoti hai', 'gandum ki fasal kaise ugate hain', 'desi khana mitti ke chulhe par', 'gaon ki subah se shaam', 'barish ke baad gaon', 'gaon ke mele ki raunaq']
        topic = random.choice(topics)
        prompt = f"""ONLY JSON. No markdown. LONG 3.5 min (450 words). Topic: {topic}. Avoid: {used}. Random {random.randint(1,99999)}.
        Write 450 words urdu_voice - 3 paras.
        JSON: {{"title":"{topic.title()} - Gaon Ki Asli Kahani | Desi Life Official", "description":"Aaj ki video me {topic}.\n\n#desilife #villagelife", "tags":["village life","desi life"], "pexels_queries":["{topic} pakistan village", "pakistan village house", "village life pakistan"], "urdu_voice":"Assalam-o-Alaikum doston! Desi Life Official me khush amdeed. Aaj hum baat karenge {topic} ke bare me. Gaon me subah hoti hai to har taraf sukoon hota hai. Kisan apne khet ki taraf jata hai, aurtein chulhe par nashta bana rahi hoti hain. Gaon ki zindagi me ek alag hi maza hai. {topic} gaon ki pehchan hai. Yahan sab mil jul kar kaam karte hain. Doston agar apko gaon ki zindagi pasand hai to video ko like karen aur channel ko subscribe karen. Shukriya!", "caption":"{topic.title()} - Gaon Ki Asli Kahani"}}"""

    for m in ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-001", "gemini-3.8-flash"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            data = json.loads(txt)
            if "pexels_queries" not in data:
                data["pexels_queries"] = [data.get("pexels_query","village pakistan")]
            return data
        except Exception as e:
            print(f"{m} failed: {e}")
            continue
    return {
        "title": f"Gaon Ki Kahani {random.randint(1,9999)} | Desi Life Official",
        "description": "Gaon ki zindagi #desilife",
        "tags": ["village"],
        "pexels_queries": ["village pakistan", "pakistan village house"],
        "urdu_voice": "Assalam-o-Alaikum doston! Gaon ki zindagi bohat khoobsurat hoti hai.",
        "caption": "GAON KI ZINDAGI"
    }

def download_pexels(queries, history, count):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used = set(history.get("used_video_ids", []))
    all_q = queries + ["village pakistan", "pakistan village"]
    for q in all_q:
        if len(clips) >= count: break
        try:
            page = random.randint(1,5)
            res = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=15&page={page}", headers=headers, timeout=30)
            if res.status_code != 200: continue
            vids = res.json().get("videos", [])
            fresh = [v for v in vids if v["id"] not in used]
            pool = fresh if fresh else vids
            if not pool: continue
            for v in random.sample(pool, min(3, len(pool))):
                if len(clips) >= count: break
                mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4" and 640 <= f["width"] <= 1280]
                if not mp4s:
                    mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4" and f["width"] <= 1920]
                if not mp4s: continue
                link = sorted(mp4s, key=lambda x: x["width"])[-1]["link"]
                print(f"BG {len(clips)+1}: {q} ID {v['id']}")
                data = requests.get(link, timeout=120).content
                if len(data) < 100000: continue
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
    caption_text = caption_text.upper()[:55]
    if is_short:
        img_w, img_h = int(video_width*0.9), 160
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            except:
                font = ImageFont.load_default()
        for dx in [-3,-2,-1,0,1,2,3]:
            for dy in [-3,-2,-1,0,1,2,3]:
                draw.text((img_w//2 + dx, img_h//2 + dy), caption_text, font=font, fill=(0,0,0,255), anchor="mm", align="center")
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    else:
        img_w, img_h = int(video_width*0.85), 90
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,180))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm", align="center")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def make_video(paths, urdu_text, caption, is_short):
    tts = gTTS(text=urdu_text, lang='ur', slow=False)
    a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    tts.save(a_path)
    audio = AudioFileClip(a_path)
    vcs = []
    per = audio.duration / len(paths)
    for i,p in enumerate(paths):
        try:
            vc = VideoFileClip(p)
            s = random.uniform(0, max(0, vc.duration - per - 0.2))
            vc = vc.subclip(s, s+per+0.3).resize(height=720)
            vcs.append(vc)
        except: continue
    if not vcs:
        raise Exception("No clips")
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration:
        final_v = final_v.loop(duration=audio.duration)
    else:
        final_v = final_v.subclip(0, audio.duration)
    caption_path = create_caption_image(caption, is_short, video_width=final_v.w)
    caption_clip = ImageClip(caption_path).set_duration(audio.duration)
    if is_short:
        caption_clip = caption_clip.set_position('center')
    else:
        caption_clip = caption_clip.set_position(('center', 0.82), relative=True)
    final = CompositeVideoClip([final_v, caption_clip]).set_audio(audio)
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final.write_videofile(out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
    return out

def get_or_create_playlist(youtube, history, title, is_short):
    # Check history first
    key = "short" if is_short else "long"
    if key in history.get("playlists", {}) and history["playlists"][key]:
        return history["playlists"][key]
    
    # Search existing playlists
    try:
        print(f"Searching playlist: {title}")
        playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for pl in playlists.get("items", []):
            if pl["snippet"]["title"].strip() == title.strip():
                print(f"Found existing playlist: {title} -> {pl['id']}")
                history["playlists"][key] = pl["id"]
                return pl["id"]
    except Exception as e:
        print(f"Playlist search failed: {e}")
    
    # Create new playlist
    try:
        print(f"Creating new playlist: {title}")
        body = {
            "snippet": {
                "title": title,
                "description": f"{title} - Auto created by Desi Life Bot. All {'shorts' if is_short else 'long videos'} will be added here automatically.",
            },
            "status": {"privacyStatus": "public"}
        }
        resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
        pid = resp["id"]
        print(f"Created playlist {title} -> {pid}")
        if "playlists" not in history:
            history["playlists"] = {}
        history["playlists"][key] = pid
        return pid
    except Exception as e:
        print(f"Playlist creation failed: {e}")
        return None

def upload_and_add_to_playlist(file_path, title, desc, tags, is_short, history):
    creds = Credentials(None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"], scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"])
    youtube = build("youtube","v3", credentials=creds)
    
    # 1. Upload video
    body = {"snippet":{"title":title[:95],"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"Upload {int(st.progress()*100)}%")
    video_id = resp.get('id')
    print(f"UPLOAD SUCCESS https://youtu.be/{video_id}")
    
    # 2. Get or create playlist
    playlist_title = SHORT_PLAYLIST_TITLE if is_short else LONG_PLAYLIST_TITLE
    playlist_id = get_or_create_playlist(youtube, history, playlist_title, is_short)
    
    # 3. Add to playlist
    if playlist_id:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}
                    }
                }
            ).execute()
            print(f"Added video {video_id} to playlist {playlist_title} ({playlist_id})")
        except Exception as e:
            print(f"Failed to add to playlist: {e}")
            # If already exists, ignore
            if "already" in str(e).lower():
                print("Video already in playlist")
    else:
        print("No playlist ID, skipping playlist add")
    
    return resp

def run_once(is_short=False):
    h = load_history()
    print(f"--- {'SHORT -> Shorts Playlist' if is_short else 'LONG -> Long Playlist'} ---")
    data = get_gemini_data(is_short, h)
    print(f"Title: {data['title']}")
    h["used_titles"].append(data["title"])
    h["used_titles"] = h["used_titles"][-60:]
    clips = download_pexels(data["pexels_queries"], h, count=2 if is_short else 3)
    if not clips:
        raise Exception("No Pexels clips")
    final = make_video(clips, data["urdu_voice"], data["caption"], is_short)
    upload_and_add_to_playlist(final, data["title"], data["description"], data["tags"], is_short, h)
    save_history(h)
    print(f"History saved with playlists: {h.get('playlists')}")

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
