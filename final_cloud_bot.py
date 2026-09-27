
import os, json, tempfile, requests, time, random
from datetime import datetime

# FIX for PIL ANTIALIAS error in moviepy 1.0.3 + Pillow 10+
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_KEY"]
PEXELS_KEY = os.environ["PEXELS_KEY"]
HISTORY_FILE = "history.json"

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"used_titles": [], "used_video_ids": []}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"History save failed: {e}")

def get_gemini_data(is_short, history):
    client = genai.Client(api_key=GEMINI_KEY)
    used_titles_str = ", ".join(history["used_titles"][-10:]) if history["used_titles"] else "none"
    avoid_prompt = f"AVOID: {used_titles_str}"
    
    topics_long = ['gaon ki shaadi', 'khet me fasal', 'desi khana chulhe par', 'gaon ki subah', 'barish me gaon', 'gaon ka mela', 'mitti ke ghar', 'bail gadi ki sawari']
    topics_short = ['gaon ki subah', 'desi khana', 'khet', 'bail gadi', 'mitti ka chulha']
    
    if is_short:
        topic = random.choice(topics_short)
        prompt = f"""ONLY JSON, no markdown. SHORT 30 sec. Topic: {topic}. {avoid_prompt}. Seed {random.randint(1,9999)}.
        JSON: {{"title":"... unique | Desi Life Official #shorts", "description":"... #shorts", "tags":["village","desi"], "pexels_queries":["{topic} pakistan", "village pakistan", "green fields pakistan"], "urdu_voice":"Gaon ki subah bohat khoobsurat hoti hai. Kisan subah jaldi uth kar khet me jata hai.", "caption":"Gaon Ki Subah"}}"""
    else:
        topic = random.choice(topics_long)
        prompt = f"""ONLY JSON, no markdown. LONG 3 min. Topic: {topic}. {avoid_prompt}. Seed {random.randint(1,9999)} {datetime.now()}.
        JSON: {{"title":"{topic.title()} Ki Kahani - unique | Desi Life Official", "description":"Gaon ki zindagi ki kahani... #desilife #villagelife", "tags":["village life","desi"], "pexels_queries":["{topic} pakistan village", "pakistan village house", "village life pakistan"], "urdu_voice":"Assalam-o-Alaikum doston! Aaj hum baat karenge {topic} ke bare me. Gaon me ye kaise hota hai, chaliye dekhte hain.", "caption":"{topic.title()} Ki Kahani"}}"""

    # Try all possible models with fallback
    models_to_try = ["gemini-3.8-flash", "gemini-2.0-flash-001", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
    for model in models_to_try:
        try:
            print(f"Trying {model}")
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.replace("```json","").replace("```","").strip()
            data = json.loads(text)
            if "pexels_queries" not in data:
                data["pexels_queries"] = [data.get("pexels_query", "village pakistan")]
            print(f"Success with {model}")
            return data
        except Exception as e:
            print(f"{model} failed: {e}")
            time.sleep(1)
            continue

    print("All Gemini failed, using fallback unique")
    return {
        "title": f"Gaon Ki Kahani {random.randint(1,9999)} | Desi Life Official",
        "description": "Gaon ki khoobsurat zindagi #desilife #village",
        "tags": ["village","desi"],
        "pexels_queries": [f"village pakistan {random.randint(1,50)}", "pakistan village house", "green field pakistan"],
        "urdu_voice": "Gaon ki zindagi bohat sukoon bhari hoti hai. Yahan subah jaldi hoti hai.",
        "caption": "Gaon Ki Zindagi"
    }

def download_multiple_pexels(queries, history, count=3):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used_ids = set(history.get("used_video_ids", []))
    
    all_queries = queries + ["village pakistan", "pakistan village", "green fields"]
    
    for query in all_queries:
        if len(clips) >= count:
            break
        try:
            page = random.randint(1, 4)
            r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=15&page={page}", headers=headers, timeout=30)
            if r.status_code != 200:
                print(f"Pexels API {r.status_code} for {query}")
                continue
            videos = r.json().get("videos", [])
            if not videos:
                continue
            
            # Prefer unused
            fresh = [v for v in videos if v["id"] not in used_ids]
            pool = fresh if fresh else videos
            
            for video in random.sample(pool, min(3, len(pool))):
                if len(clips) >= count:
                    break
                if video["id"] in [c.get('id') for c in []]:  # avoid dup in this run
                    continue
                mp4s = [f for f in video["video_files"] if f["file_type"]=="video/mp4" and 640 <= f["width"] <= 1280]
                if not mp4s:
                    mp4s = [f for f in video["video_files"] if f["file_type"]=="video/mp4" and f["width"] <= 1920]
                if not mp4s:
                    continue
                link = sorted(mp4s, key=lambda x: x["width"])[-1]["link"]
                print(f"Downloading BG {len(clips)+1}: {query} ID {video['id']} width {sorted(mp4s, key=lambda x: x['width'])[-1]['width']}")
                data = requests.get(link, timeout=120).content
                if len(data) < 100000:  # too small, skip
                    continue
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp.write(data); tmp.close()
                clips.append(tmp.name)
                history["used_video_ids"].append(video["id"])
                history["used_video_ids"] = history["used_video_ids"][-150:]
                
        except Exception as e:
            print(f"Pexels error {query}: {e}")
            continue
    
    # Fallback - if only 1 clip, duplicate it
    if len(clips) == 1 and count > 1:
        print(f"Only 1 clip found, duplicating to {count}")
        clips = clips * count
    
    return clips

def make_video_with_voice_and_caption(pexels_paths, urdu_text, caption, is_short):
    # Urdu Voice
    print(f"Generating Urdu voice: {urdu_text[:60]}...")
    tts = gTTS(text=urdu_text, lang='ur', slow=False)
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    tts.save(audio_path)
    audio = AudioFileClip(audio_path)
    print(f"Audio duration: {audio.duration}s")
    
    # Multiple backgrounds
    video_clips = []
    target_duration = audio.duration + 0.5
    per_clip = target_duration / len(pexels_paths)
    
    for idx, p in enumerate(pexels_paths):
        try:
            vc = VideoFileClip(p)
            # Take random middle part
            start = random.uniform(0, max(0, vc.duration - per_clip - 0.5))
            vc = vc.subclip(start, start + per_clip + 0.5)
            vc = vc.resize(height=720)
            print(f"Clip {idx+1} processed: {vc.duration}s")
            video_clips.append(vc)
        except Exception as e:
            print(f"Clip {idx} error: {e}")
            continue
    
    if not video_clips:
        raise Exception("No valid video clips after processing")
    
    final_video = concatenate_videoclips(video_clips, method="compose")
    if final_video.duration < target_duration:
        final_video = final_video.loop(duration=target_duration)
    else:
        final_video = final_video.subclip(0, target_duration)
    
    # Caption - FIXED for Pillow compatibility
    try:
        if is_short:
            txt = TextClip(caption, fontsize=65, color='white', font='Arial-Bold', stroke_color='black', stroke_width=2, method='label').set_position('center').set_duration(target_duration)
        else:
            txt = TextClip(caption, fontsize=42, color='white', font='Arial-Bold', method='label').set_position(('center', 0.82), relative=True).set_duration(target_duration)
        final = CompositeVideoClip([final_video, txt]).set_audio(audio)
    except Exception as e:
        print(f"TextClip failed {e}, using video without caption")
        final = final_video.set_audio(audio)
    
    final_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final.write_videofile(final_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
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
    print(f"--- Starting {'SHORT' if is_short else 'LONG'} - History {len(history['used_titles'])} titles ---")
    data = get_gemini_data(is_short, history)
    print(f"Title: {data['title']}")
    history["used_titles"].append(data["title"])
    history["used_titles"] = history["used_titles"][-50:]
    pexels_clips = download_multiple_pexels(data["pexels_queries"], history, count=2 if is_short else 3)
    print(f"Downloaded {len(pexels_clips)} clips")
    if not pexels_clips:
        raise Exception("Failed to download any Pexels video - check PEXELS_KEY")
    final_clip = make_video_with_voice_and_caption(pexels_clips, data["urdu_voice"], data["caption"], is_short)
    upload_to_youtube(final_clip, data["title"], data["description"], data["tags"], is_short)
    save_history(history)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
