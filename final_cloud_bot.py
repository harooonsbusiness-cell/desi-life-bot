import os, random, requests, tempfile, json, time
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

GEMINI_KEY = os.environ.get("GEMINI_KEY")
PEXELS_KEY = os.environ.get("PEXELS_KEY")
YT_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

client = genai.Client(api_key=GEMINI_KEY)

TOPICS = [
    "Gaon ki subah kaise hoti hai - village morning",
    "Mitti ke chulhe par khana - village cooking",
    "Gaon ke khet aur fasal - wheat fields",
    "Desi ghar ki kahani - old village house",
    "Gaon ki shaam aur chai - village evening"
]

def generate_script(is_short=False):
    topic = random.choice(TOPICS)
    length = "Shorts 60 sec viral hook" if is_short else "Long 8 min vlog emotional"
    prompt = f"""
    You are writer for YouTube channel 'Desi Life Official'.
    Topic: {topic}
    Type: {length}
    Language: Hindi/Urdu simple desi.
    Output ONLY valid JSON: {{"title":"catchy SEO title","description":"3 lines + 10 hashtags","tags":["tag1","tag2","tag3"]}}
    Title for long must end with " | Desi Life Official", for short add " #Shorts" at end.
    Description must be emotional.
    """
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = response.text.replace("```json","").replace("```","").strip()
        data = json.loads(text)
    except Exception as e:
        print(f"Gemini parse failed {e}, using fallback")
        suffix = " #Shorts" if is_short else " | Desi Life Official"
        data = {
            "title": topic + suffix,
            "description": f"{topic}\nGaon ki zindagi ka asli sukoon\n#DesiLife #VillageVlog #Gaon #DesiLifeOfficial #PakistanVillage #IndianVillage",
            "tags": ["desi life", "village vlog", "gaon", "desi life official"]
        }
    return data

def download_pexels_video(query, is_short):
    headers = {"Authorization": PEXELS_KEY}
    orientation = "portrait" if is_short else "landscape"
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation={orientation}"
    r = requests.get(url, headers=headers, timeout=30).json()
    videos = r.get("videos")
    if not videos:
        r = requests.get(f"https://api.pexels.com/videos/search?query=village&per_page=5&orientation={orientation}", headers=headers, timeout=30).json()
        videos = r.get("videos", [])
    if not videos:
        raise Exception("No Pexels video found - check PEXELS_KEY")
    # pick best quality
    files = sorted(videos[0]["video_files"], key=lambda x: x["width"], reverse=True)
    video_url = files[0]["link"]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    print(f"Downloading {video_url[:80]}...")
    with requests.get(video_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(tmp, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
    print(f"Saved to {tmp} size {os.path.getsize(tmp)}")
    return tmp

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
            "title": title[:95],
            "description": description,
            "tags": tags[:15],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    print(f"Uploading {title}...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress()*100)}%")
    print(f"SUCCESS Uploaded ID: {response['id']}")
    return response

def run_once(is_short):
    print(f"--- Starting {'SHORTS' if is_short else 'LONG'} ---")
    data = generate_script(is_short)
    print(f"Title: {data['title']}")
    clip = download_pexels_video("indian village field nature", is_short)
    upload_to_youtube(clip, data['title'], data['description'], data['tags'], is_short)
    # cleanup
    try:
        os.remove(clip)
    except:
        pass

if __name__ == "__main__":
    mode = os.environ.get("MODE", "long")
    run_once(is_short=(mode=="short"))