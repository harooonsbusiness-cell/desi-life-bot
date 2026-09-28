
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
    today = datetime.now().strftime("%Y-%m-%d-%H-%M")
    seed = random.randint(1, 9999999)
    used = ", ".join(history["used_titles"][-5:]) if history["used_titles"] else "none"
    
    SHORT_TOPICS = [
        "gaon ki subah 5 baje", "chulhe par desi chai", "khet me bail gadi", "mitti ka chulha kaise jalate hain", "gaon ka nalka", "dadi ka charkha", "gaon ke bachche khelte hue", "khet me pani lagana", "gaon ki masjid", "sarson ka khet",
        "gandum ki katai", "bhains ka doodh nikalna", "gaon ka mela", "desi lassi banana", "khet me tractor chalana", "gaon ki shaam", "mitti ke ghar", "gaon ka kuwa", "desi khana chulhe par", "khet me parinde",
        "gaon ka bazar", "mitti ki khushbu", "gaon ki barish", "kisan ki subah", "desi charpai", "gaon ka school", "khet me dhan", "gaon ka chand", "desi achaar banana", "gaon ki eid"
    ]
    
    LONG_TOPICS = [
        "gaon ki shaadi kaise hoti hai - poora riwaj", "gandum ki fasal ugane ka poora tarika", "chulhe par desi khana kaise banta hai", "gaon ki subah se shaam tak ki zindagi", "barish ke baad gaon ka khoobsurat manzar",
        "gaon ke mele ki raunaq aur khail", "kisan ki mehnat - khet se mandi tak", "mitti ke ghar kaise bante hain", "gaon me Eid kaise manate hain", "desi lassi aur makhan kaise banta hai",
        "gaon me pani ka intezam - kuwe aur nalke", "garmi me gaon ki thandi shaam", "sardi me gaon ka chulha aur kahani", "gaon ki aurat ki din bhar ki mehnat", "gaon ke bachchon ka school jana",
        "bail gadi se khet tak safar", "sarson ke khet ki khoobsurati", "aam ke bagh me garmi ka maza", "gaon ki biryani aur desi zaiqa", "mitti ke bartan kaise bante hain",
        "gaon me machhli pakadna", "gaon ka bazaar - sabzi mandi", "gaon me shadi ki taiyariyan", "khet me hal chalana - purana tareeqa", "gaon ki raat - chand aur sitare",
        "desi murgi palna gaon me", "gaon me bhains palna aur doodh", "gaon ka desi ilaj - jari bootiyan", "gaon ki kahani - buzurgon ki zuban se", "sheher aur gaon ki zindagi me farq"
    ]
    
    if is_short:
        random.seed(f"{today}-{seed}")
        topic = random.choice(SHORT_TOPICS)
        random.seed()
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

    # Try NEW SDK first (google-genai)
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        # Try with 001 suffix which is valid
        for m in ["gemini-2.0-flash-001", "gemini-2.0-flash-lite-001", "gemini-1.5-flash-002", "gemini-1.5-flash-001", "gemini-2.0-flash"]:
            try:
                print(f"Trying Gemini model {m}")
                r = client.models.generate_content(model=m, contents=prompt)
                txt = r.text.replace("```json","").replace("```","").strip()
                if txt.lower().startswith("json"): txt = txt[4:].strip()
                data = json.loads(txt)
                if "urdu_voice" in data and len(data["urdu_voice"]) > 25:
                    print(f"Gemini {m} SUCCESS - Topic: {topic}")
                    return data
            except Exception as e:
                print(f"{m} fail {str(e)[:150]}")
                continue
    except Exception as e:
        print(f"genai Client error {e}")

    # Try OLD SDK (google.generativeai) as fallback
    try:
        import google.generativeai as genai_old
        genai_old.configure(api_key=GEMINI_KEY)
        for m in ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]:
            try:
                print(f"Trying OLD SDK model {m}")
                model = genai_old.GenerativeModel(m)
                r = model.generate_content(prompt)
                txt = r.text.replace("```json","").replace("```","").strip()
                if txt.lower().startswith("json"): txt = txt[4:].strip()
                data = json.loads(txt)
                if "urdu_voice" in data and len(data["urdu_voice"]) > 25:
                    print(f"OLD SDK {m} SUCCESS - Topic: {topic}")
                    return data
            except Exception as e:
                print(f"OLD {m} fail {str(e)[:120]}")
                continue
    except Exception as e:
        print(f"OLD SDK not available {e}")

    # Final fallback with date-unique topic - NO REPEAT
    print(f"Using FALLBACK unique topic: {topic} {today}")
    return {
        "title": f"{topic.title()} {today} | Desi Life Official",
        "description": f"{topic} - Gaon ki khoobsurat kahani #{today} #desilife #villagelife",
        "tags": ["village life", f"gaon {seed}", "desi life"],
        "pexels_queries": [f"{topic} pakistan {'vertical' if is_short else 'horizontal'}", "village pakistan"],
        "urdu_voice": f"Assalam-o-Alaikum doston! Aaj hum baat karenge {topic} ke bare me. Gaon ki zindagi bohat khoobsurat hai. Yahan subah thandi hawa chalti hai, kisan khet me kaam karta hai, aur sham ko sab mil kar baithte hain. {topic} hamari pehchan hai. Video pasand aaye to Like Subscribe zaroor karen. Gaon ki mitti me sukoon hai, sheher me nahi.",
        "caption": topic.upper()[:40]
    }


def download_pexels
