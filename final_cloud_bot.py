
import os, json, tempfile, requests, time, random, hashlib
from datetime import datetime
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_KEY"]
PEXELS_KEY = os.environ["PEXELS_KEY"]

# History file to avoid repeat
HISTORY_FILE = "history.json"

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"used_titles": [], "used_queries": [], "used_video_ids": []}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"History save failed: {e}")

def get_gemini_data(is_short, history):
    client = genai.Client(api_key=GEMINI_KEY)
    
    # Avoid repeat - give history to Gemini
    used_titles_str = ", ".join(history["used_titles"][-10:]) if history["used_titles"] else "none"
    avoid_prompt = f"AVOID these already used titles: {used_titles_str}. Create TOTALLY NEW unique story."

    if is_short:
        prompt = f"""You are Desi Life Official. Write ONLY valid JSON in URDU/HINGLISH mix, no markdown.
        {avoid_prompt}
        Create SHORT 30 sec viral idea - {random.choice(['gaon ki shaadi', 'khet me kaam', 'desi khana', 'gaon ki subah', 'bail gadi', 'mitti ka chulha', 'gaon ka mela', 'barish me gaon'])} pe unique story.
        Use random date {datetime.now()} for uniqueness.
        JSON: {{"title":"... unique | Desi Life Official #shorts", "description":"... #shorts #desilife", "tags":["village","desi","pakistan"], "pexels_queries":["village morning pakistan", "old pakistani house", "green fields"], "urdu_voice":"30 sec ki kahani urdu me, emotional...", "caption":"Gaon Ki Zindagi 🌾"}}"""
    else:
        prompt = f"""You are Desi Life Official. Write ONLY valid JSON, no markdown.
        {avoid_prompt}
        Create LONG 3-4 min story on {random.choice(['gaon ki shaadi kaise hoti hai', 'gaon me fasal kaise ugate hain', 'desi khana kaise banta hai', 'gaon ki subah se shaam', 'gaon ke buzurg ki kahani', 'barish ke baad gaon', 'gaon ka bazaar', 'mitti ke ghar'])} - TOTALLY NEW ANGLE.
        Use seed {random.randint(1000,9999)} for uniqueness.
        JSON: {{"title":"... unique long title | Desi Life Official", "description":"Full description 3 lines + hashtags #desilife #villagelife #pakistan", "tags":["village life","desi","pakistan village"], "pexels_queries":["pakistan village house", "village field pakistan", "village people"], "urdu_voice":"Assalam-o-Alaikum doston! Aaj ki kahani... (150 words urdu story, emotional, unique)", "caption":"Gaon Ki Asli Zindagi"}}"""

    for model in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            print(f"Trying {model}")
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.replace("```json","").replace("```","").strip()
            data = json.loads(text)
            # Ensure lists
            if "pexels_queries" not in data:
                data["pexels_queries"] = [data.get("pexels_query", "village pakistan")]
            return data
        except Exception as e:
            print(f"{model} failed: {e}")
            continue

    # Fallback unique
    return {
        "title": f"Gaon ki kahani {random.randint(1,1000)} | Desi Life Official",
        "description": "#desilife #village",
        "tags": ["village"],
        "pexels_queries": [f"village pakistan {random.randint(1,50)}"],
        "urdu_voice": "Gaon ki zindagi bohat khoobsurat hoti hai.",
        "caption": "Gaon Ki Zindagi"
    }

def download_multiple_pexels(queries, history, count=3):
    """Download 2-3 DIFFERENT background videos, no repeat"""
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used_ids = set(history.get("used_video_ids", []))
    
    for query in queries[:count]:
        try:
            # Random page to get different images every time
            page = random.randint(1, 5)
            r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=10&page={page}", headers=headers, timeout=30)
            r.raise_for_status()
            videos = r.json().get("videos", [])
            
            # Filter out already used video IDs
            fresh_videos = [v for v in videos if v["id"] not in used_ids]
            if not fresh_videos:
                fresh_videos = videos  # if all used, reuse oldest
            
            if not fresh_videos:
                continue
                
            video = random.choice(fresh_videos[:5])  # random from top 5
            history["used_video_ids"].append(video["id"])
            # Keep only last 100 IDs
            history["used_video_ids"] = history["used_video_ids"][-100:]
            
            # Pick 720p
            mp4s = [f for f in video["video_files"] if f["file_type"]=="video/mp4" and f["width"]<=1280 and f["width"]>=640]
            if not mp4s:
                mp4s = [f for f in video["video_files"] if f["file_type"]=="video/mp4"]
            link = sorted(mp4s, key=lambda x: x["width"])[-1]["link"]
            
            print(f"Downloading BG {len(clips)+1}: {query} - ID {video['id']}")
            data = requests.get(link, timeout=120).content
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp.write(data); tmp.close()
            clips.append(tmp.name)
            
            if len(clips) >= count:
                break
        except Exception as e:
            print(f"Pexels error for {query}: {e}")
            continue
    
    return clips

def make_video_with_voice_and_caption(pexels_paths, urdu_text, caption, is_short):
    # 1. Urdu Voice
    tts = gTTS(text=urdu_text, lang='ur', slow=False)
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    tts.save(audio_path)
    audio = AudioFileClip(audio_path)
    
    # 2. Multiple backgrounds - concatenate 2-3 videos
    video_clips = []
    target_duration = audio.duration
    per_clip_duration = target_duration / len(pexels_paths)
    
    for p in pexels_paths:
        try:
            vc = VideoFileClip(p).subclip(0, min(per_clip_duration+1, VideoFileClip(p).duration))
            # Resize to 720p for consistency
            vc = vc.resize(height=720)
            video_clips.append(vc)
        except Exception as e:
            print(f"Clip error: {e}")
    
    if not video_clips:
        raise Exception("No valid video clips")
    
    final_video = concatenate_videoclips(video_clips, method="compose")
    # Loop if still short
    if final_video.duration < target_duration:
        final_video = final_video.loop(duration=target_duration)
    else:
        final_video = final_video.subclip(0, target_duration)
    
    # 3. Caption
    if is_short:
        txt = TextClip(caption, fontsize=70, color='white', font='Arial-Bold', stroke_color='black', stroke_width=3, method='caption', size=(final_video.w*0.9, None)).set_position('center').set_duration(target_duration)
    else:
        txt = TextClip(caption, fontsize=50, color='white', font='Arial-Bold', bg_color='black', method='caption', size=(final_video.w*0.85, None)).set_position(('center', 0.82), relative=True).set_duration(target_duration)
    
    final = CompositeVideoClip([final_video, txt]).set_audio(audio)
    final_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final.write_videofile(final_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast')
    return final_path

def upload_to_youtube(file_path, title, desc, tags, is_short):
    creds = Credentials(None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"], scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube","v3", credentials=creds)
    body = {"snippet":{"title":title[:95],"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response=None
    while response is None:
        status, response = request.next_chunk()
        if status: print(f"Upload {int(status.progress()*100)}%")
    print(f"SUCCESS https://youtu.be/{response.get('id')}")
    return response

def run_once(is_short=False):
    history = load_history()
    print(f"--- Starting {'SHORT' if is_short else 'LONG'} - History: {len(history['used_titles'])} titles used ---")
    data = get_gemini_data(is_short, history)
    print(f"Title: {data['title']}")
    
    # Save title to history to avoid repeat
    history["used_titles"].append(data["title"])
    history["used_titles"] = history["used_titles"][-50:]  # keep last 50
    
    # Download 2-3 DIFFERENT backgrounds
    pexels_clips = download_multiple_pexels(data["pexels_queries"], history, count=3 if not is_short else 2)
    print(f"Downloaded {len(pexels_clips)} backgrounds: {data['pexels_queries']}")
    
    final_clip = make_video_with_voice_and_caption(pexels_clips, data["urdu_voice"], data["caption"], is_short)
    upload_to_youtube(final_clip, data["title"], data["description"], data["tags"], is_short)
    
    save_history(history)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
