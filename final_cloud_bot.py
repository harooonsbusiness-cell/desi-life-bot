import os
import random
import requests
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS
from moviepy.editor import *
import tempfile
import json

# --- CONFIG FROM SECRETS ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
PEXELS_KEY = os.environ.get("PEXELS_KEY")
YT_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

genai.configure(api_key=GEMINI_KEY)

TOPICS = [
    "Gaon ki subah kaise hoti hai | Desi village morning routine",
    "Mitti ke chulhe par khana | Village cooking",
    "Gaon ke khet aur fasal | Wheat fields life",
    "Desi ghar ki kahani | Old village house tour",
    "Gaon ki shaam aur chai | Village evening vibes"
]

def generate_script(is_short=False):
    model = genai.GenerativeModel('gemini-1.5-flash')
    topic = random.choice(TOPICS)
    length = "60 seconds, 150 words MAX" if is_short else "8 minutes, 1000 words"
    prompt = f"""
    You are script writer for YouTube channel 'Desi Life Official'.
    Topic: {topic}
    Type: {'YouTube Shorts - viral, hook in first 2 sec' if is_short else 'Long vlog - emotional, storytelling'}
    Length: {length}
    Language: Hindi + Urdu mix, simple desi language, emotional.
    Give output in JSON format: {{"title": "...", "description": "...", "script": "...", "tags": ["tag1", "tag2"]}}
    Title must be catchy and SEO friendly with | Desi Life Official at end for long.
    Description must have 3-4 lines + hashtags.
    """
    response = model.generate_content(prompt)
    text = response.text.replace("```json","").replace("```","").strip()
    try:
        data = json.loads(text)
    except:
        # fallback parsing
        data = {"title": topic + (" #Shorts" if is_short else " | Desi Life Official"), "description": topic + "\n#DesiLife #VillageVlog #Gaon", "script": text, "tags": ["desi life", "village vlog", "gaon"]}
    return data

def download_pexels_video(query, is_short):
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=3&orientation={'portrait' if is_short else 'landscape'}"
    r = requests.get(url, headers=headers).json()
    if not r.get("videos"):
        query = "village india"
        r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=3&orientation={'portrait' if is_short else 'landscape'}", headers=headers).json()
    video_url = r["videos"][0]["video_files"][0]["link"]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    with requests.get(video_url, stream=True) as resp:
        with open(tmp, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    return tmp

def make_video(script_text, pexels_clip_path, is_short):
    # TTS
    tts = gTTS(text=script_text[:4000], lang='hi', slow=False)
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    tts.save(audio_path)

    audio = AudioFileClip(audio_path)
    video = VideoFileClip(pexels_clip_path).subclip(0, min(audio.duration+1, 60 if is_short else 500))

    # Resize for Shorts
    if is_short:
        video = video.resize(height=1920)
        video = video.crop(x_center=video.w/2, width=1080, height=1920)
    else:
        video = video.resize((1920,1080))

    video = video.set_audio(audio)
    # Add watermark text
    txt = TextClip("Desi Life Official", fontsize=40, color='white', font='Arial-Bold', stroke_color='black', stroke_width=2).set_duration(video.duration).set_position(('center','bottom')).set_opacity(0.7)
    final = CompositeVideoClip([video, txt])

    out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24)
    return out_path

def upload_to_youtube(video_path, title, description, tags, is_short):
    creds = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/youtube.upload']
    )
    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        "snippet": {
            "title": title[:95] + (" #Shorts" if is_short and "#Shorts" not in title else ""),
            "description": description,
            "tags": tags,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/*')
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"Uploaded: {response['id']} - {title}")
    return response

def run_once(is_short):
    print(f"Starting {'SHORTS' if is_short else 'LONG'} automation")
    data = generate_script(is_short)
    print(f"Title: {data['title']}")
    clip = download_pexels_video("indian village field", is_short)
    video_path = make_video(data['script'], clip, is_short)
    upload_to_youtube(video_path, data['title'], data['description'], data['tags'], is_short)

if __name__ == "__main__":
    mode = os.environ.get("MODE", "long") # long or short
    run_once(is_short=(mode=="short"))