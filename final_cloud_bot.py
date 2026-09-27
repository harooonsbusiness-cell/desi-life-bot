
import os, json, tempfile, requests, time
from google import genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ["GEMINI_KEY"]
PEXELS_KEY = os.environ["PEXELS_KEY"]

def get_gemini_data(is_short):
    client = genai.Client(api_key=GEMINI_KEY)
    prompt = f"""You are Desi Life Official writer. Return ONLY JSON, no markdown.
    {"SHORT 30sec idea" if is_short else "LONG 8 min story"} on village life in Pakistan.
    JSON format: {{"title":"... | Desi Life Official","description":"...","tags":["..."],"pexels_query":"old village house pakistan"}}"""
    
    # Latest models as per Google 2026
    for model_name in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            print(f"Trying Gemini model: {model_name}")
            resp = client.models.generate_content(model=model_name, contents=prompt)
            text = resp.text.replace("```json","").replace("```","").strip()
            data = json.loads(text)
            print(f"Success with {model_name}: {data['title']}")
            return data
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    
    print("All Gemini models failed, using fallback")
    if is_short:
        return {"title":"Gaon ki subah | Desi Life Official #shorts","description":"Gaon ki khoobsurat subah #desilife #village","tags":["village","desi","shorts"],"pexels_query":"village morning"}
    else:
        return {"title":f"Gaon ki subah kaise hoti hai - village morning | Desi Life Official","description":"Aaj ki kahani gaon ki subah ki.\n\n#desilife #villagelife #pakistan","tags":["village life","desi life","pakistan village"],"pexels_query":"old village house pakistan"}

def download_pexels(query):
    headers={"Authorization": PEXELS_KEY}
    r = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page=1", headers=headers, timeout=30)
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos:
        raise Exception(f"No Pexels video for {query}")
    video = videos[0]
    # prefer smaller file to avoid 300MB+ upload
    mp4s = [f for f in video["video_files"] if f["file_type"]=="video/mp4"]
    # sort by width ascending to get smaller file
    file_link = sorted(mp4s, key=lambda x: x["width"])[0]["link"]
    if any(f["width"]>=1280 for f in mp4s):
        file_link = [f for f in mp4s if f["width"]>=1280][0]["link"]
    print(f"Downloading {file_link}...")
    data = requests.get(file_link, timeout=180).content
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(data); tmp.close()
    print(f"Saved to {tmp.name} size {len(data)}")
    return tmp.name

def upload_to_youtube(file_path, title, desc, tags, is_short):
    creds = Credentials(
        None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube","v3", credentials=creds)
    body = {
        "snippet": {"title": title[:95], "description": desc, "tags": tags, "categoryId": "22"},
        "status": {"privacyStatus":"public", "selfDeclaredMadeForKids": False}
    }
    print(f"Uploading {title}...")
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress()*100)}%")
        time.sleep(1)
    
    print(f"UPLOAD SUCCESS! Video ID: {response.get('id')} URL: https://youtu.be/{response.get('id')}")
    return response

def run_once(is_short=False):
    print(f"--- Starting {'SHORT' if is_short else 'LONG'} ---")
    data = get_gemini_data(is_short)
    print(f"Title: {data['title']}")
    clip = download_pexels(data['pexels_query'])
    upload_to_youtube(clip, data['title'], data['description'], data['tags'], is_short)

if __name__ == "__main__":
    mode = os.environ.get("MODE","long")
    run_once(is_short=(mode=="short"))
