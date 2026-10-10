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
FB_APP_ID = os.environ.get("FB_APP_ID", "")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET", "")
FB_USER_TOKEN = os.environ.get("FB_USER_TOKEN", "")
FB_ENABLED = False
TIKTOK_ENABLED = False
VOICE_GENDER = "male"
VOICE_NAME_MALE = "ur-PK-AsadNeural"
VOICE_NAME_FEMALE = "ur-PK-UzmaNeural"

def get_fresh_page_token():
    global FB_PAGE_TOKEN
    user_token_to_use = FB_USER_TOKEN if FB_USER_TOKEN else ""
    if FB_USER_TOKEN:
        try:
            if FB_APP_ID and FB_APP_SECRET:
                try:
                    exchange_url = f"https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id={FB_APP_ID}&client_secret={FB_APP_SECRET}&fb_exchange_token={FB_USER_TOKEN}"
                    ex_res = requests.get(exchange_url, timeout=20)
                    if ex_res.status_code == 200:
                        new_user_token = ex_res.json().get("access_token")
                        if new_user_token:
                            user_token_to_use = new_user_token
                except: pass
            url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={user_token_to_use}"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                data = res.json()
                for page in data.get("data", []):
                    if str(page["id"]) == str(FB_PAGE_ID):
                        return page["access_token"]
                if data.get("data"):
                    return data["data"][0]["access_token"]
        except: pass
    return FB_PAGE_TOKEN


def generate_azure_tts(text, output_path, voice_name="ur-PK-AsadNeural"):
    print("Azure removed - user wants ElevenLabs first")
    return False




def generate_gemini_tts(text, output_path):
    """
    Gemini 3.1 / 2.5 Pro TTS - FREE unlimited, emotional, Urdu support
    Model: gemini-2.5-pro-preview-tts or gemini-3.1-flash-tts-preview
    Supports Urdu (ur) - BCP-47 code
    Free in Google AI Studio, prompt-based style control
    """
    try:
        import re
        clean_text = re.sub(r'[😀-🙏🌀-🗿🚀-🛿🤐-🧿]', '', text)
        clean_text = clean_text[:4000]  # Gemini limit
        
        client = genai.Client(api_key=GEMINI_KEY)
        
        # Try Gemini TTS models - 2026 latest
        for model_name in ["gemini-2.5-pro-preview-tts", "gemini-3.1-flash-preview", "gemini-2.5-flash-preview-tts"]:
            try:
                print(f"Trying Gemini TTS model {model_name} with Urdu...")
                # Gemini TTS uses audio generation
                # Note: Actual API may vary, this is based on 2026 docs
                response = client.models.generate_content(
                    model=model_name,
                    contents=[f"Speak in Urdu (Pakistan), natural village style, emotional: {clean_text}"],
                )
                # If response contains audio, save it
                # Fallback: check if model supports TTS
                # For now, use text generation as placeholder - real implementation needs audio output
                print(f"Gemini TTS {model_name} response: {str(response)[:200]}")
                # TODO: Actual audio extraction depends on API - AI Studio free
                # For GitHub Actions, this may need additional setup
                continue
            except Exception as e:
                print(f"Gemini TTS {model_name} failed: {e}")
                continue
        
        return False
    except Exception as e:
        print(f"Gemini TTS error: {e}")
        return False

def generate_orpheus_tts(text, output_path):
    """
    Orpheus Urdu TTS - Open source, Llama-3B backbone, human-like with emotion
    Supports Urdu Nastaliq/Arabic script
    Requires GPU, self-hosted - best quality open source
    Model: canopylabs/orpheus-tts-0.1-pretrained or multilingual
    """
    try:
        # Check if orpheus-tts installed
        import orpheus_tts
        print(f"Trying Orpheus Urdu TTS with {len(text)} chars...")
        # Orpheus supports Urdu Nastaliq
        # Example: orpheus_tts.generate(text, voice="urdu_female", emotion="happy")
        # This is placeholder - actual implementation needs local model
        return False
    except ImportError:
        print("Orpheus TTS not installed - pip install orpheus-tts (needs GPU)")
        return False
    except Exception as e:
        print(f"Orpheus TTS error: {e}")
        return False


def generate_azure_tts_sdk(text, output_path, voice_name="ur-PK-AsadNeural"):
    """
    Alternative using Azure SDK (needs azure-cognitiveservices-speech pip package)
    Better for long texts
    """
    import os
    azure_key = os.environ.get("AZURE_SPEECH_KEY", "")
    azure_region = os.environ.get("AZURE_SPEECH_REGION", "eastus")
    
    if not azure_key:
        return False
    
    try:
        import azure.cognitiveservices.speech as speechsdk
        
        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        speech_config.speech_synthesis_voice_name = voice_name
        # Output to file
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        # For long text, use SSML
        ssml = f"<speak version='1.0' xml:lang='ur-PK'><voice name='{voice_name}'>{text}</voice></speak>"
        result = synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"✅ Azure SDK TTS SUCCESS")
            return True
        else:
            print(f"Azure SDK failed: {result.reason}")
            return False
    except Exception as e:
        print(f"Azure SDK error: {e}")
        return False

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)

# === VIRAL KEYWORDS DATABASE 2026 - Pakistan Village Niche ===
VIRAL_KEYWORDS_BASE = [
    # Top search terms 2026
    "village vlog pakistan",
    "pakistani village life",
    "desi village life",
    "rural pakistan",
    "punjabi village life",
    "gaon ki zindagi",
    "desi life official",
    "village life pakistan 2026",
    "gaon ka desi life",
    "pakistan village vlog 2026",
]

VIRAL_KEYWORDS_LONG = [
    "village vlog pakistan 8 min",
    "pakistani village life full video",
    "gaon ki zindagi 2026",
    "desi village life long video",
    "rural pakistan lifestyle",
    "punjabi village life 2026",
    "village cooking chulha",
    "gandum ka khet pakistan",
    "sarson ka khet village",
    "bhains ka doodh village",
    "chulhe par desi khana",
    "mitti ka chulha village",
    "gaon ka kuwa",
    "khet me kisan",
    "village mela pakistan",
    "desi life official long",
    "gaon me kamai 2026",
    "1 acre se 1 lakh",
    "sasti zindagi gaon",
    "village life pakistan viral",
]

VIRAL_KEYWORDS_SHORT = [
    "village shorts viral",
    "desi shorts pakistan",
    "gaon shorts",
    "village life shorts",
    "punjabi village shorts",
    "desi village shorts",
    "pakistani village shorts",
    "village cooking shorts",
    "gaon ki subah shorts",
    "chulha shorts",
    "khet shorts",
    "bhains shorts",
    "sarson shorts",
    "gandum shorts",
    "village vlog shorts 2026",
]

VIRAL_HASHTAGS = [
    "#VillageVlog", "#VillageLife", "#PakistanVillage", "#DesiLife",
    "#GaonKiZindagi", "#RuralPakistan", "#PunjabiVillage", "#DesiVillage",
    "#VillageCooking", "#ChulhaCooking", "#GandumKaKhet", "#SarsonKaKhet",
    "#DesiLifeOfficial", "#VillageLifePakistan", "#GaonKaDesiLife",
    "#VillageVlog2026", "#PakistaniVillageLife", "#DesiVillageLife",
    "#RuralLifePakistan", "#VillageMela", "#KhetBadi", "#KisanLife",
]

def get_viral_keywords_for_topic(topic, is_short=False):
    """Get viral keywords based on topic - 2026 trending"""
    base = VIRAL_KEYWORDS_SHORT if is_short else VIRAL_KEYWORDS_LONG
    topic_lower = topic.lower()
    
    # Topic-specific viral keywords
    topic_keywords = []
    
    # Mapping topic keywords to viral terms
    if "shaadi" in topic_lower or "shadi" in topic_lower:
        topic_keywords = ["gaon ki shaadi viral", "village wedding pakistan", "desi shaadi vlog", "3 din ki shaadi"]
    elif "gandum" in topic_lower:
        topic_keywords = ["gandum ka khet pakistan", "wheat field village", "gandum ki katai", "1 acre gandum kamai"]
    elif "sarson" in topic_lower:
        topic_keywords = ["sarson ka khet pakistan", "mustard field village", "peela samandar", "sarson ki kheti"]
    elif "chulha" in topic_lower or "chulhe" in topic_lower:
        topic_keywords = ["chulhe par khana pakistan", "mitti ka chulha", "desi chulha cooking", "chulha viral"]
    elif "bhains" in topic_lower or "doodh" in topic_lower or "lassi" in topic_lower:
        topic_keywords = ["bhains ka doodh village", "desi lassi pakistan", "fresh milk village", "20 liter doodh"]
    elif "mitti" in topic_lower:
        topic_keywords = ["mitti ke ghar pakistan", "bina cement ghar", "mitti ka ghar viral", "kumhar ki kala"]
    elif "khet" in topic_lower or "kisan" in topic_lower:
        topic_keywords = ["khet me kisan pakistan", "kheti badi pakistan", "1 acre kamai", "kisan ki mehnat"]
    elif "pani" in topic_lower or "kuwa" in topic_lower or "nalka" in topic_lower:
        topic_keywords = ["gaon me pani", "kuwa ka raaz", "nalka thanda pani", "village water system"]
    elif "bazaar" in topic_lower or "mandi" in topic_lower:
        topic_keywords = ["gaon ka bazaar", "sabzi mandi sasti", "village market pakistan", "sasti sabzi"]
    elif "mela" in topic_lower:
        topic_keywords = ["gaon ka mela viral", "village mela pakistan", "mela raunaq", "desi mela"]
    elif "machhli" in topic_lower:
        topic_keywords = ["nehar se machhli", "10 kg machhli", "village fishing pakistan", "machhli pakadna"]
    elif "biryani" in topic_lower or "khana" in topic_lower:
        topic_keywords = ["chulhe wali biryani", "desi khana village", "chulhe par khana", "village cooking viral"]
    elif "subah" in topic_lower or "shaam" in topic_lower or "raat" in topic_lower:
        topic_keywords = ["gaon ki subah 5 baje", "village morning pakistan", "gaon ki shaam sukoon", "chand sitare gaon"]
    else:
        topic_keywords = [f"{topic} pakistan viral", f"{topic} village vlog", f"{topic} desi life"]
    
    # Combine base + topic-specific + base viral
    all_keywords = topic_keywords + base[:10] + VIRAL_KEYWORDS_BASE[:5]
    
    # Remove duplicates, keep order, limit to 15 tags (YouTube limit)
    seen = set()
    unique = []
    for k in all_keywords:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)
        if len(unique) >= 15:
            break
    
    return unique


def fetch_live_trending_keywords(topic, is_short=False):
    """
    LIVE TRENDING SEARCH - Har dafa real-time viral keywords nikalta hai
    3 sources: YouTube Autocomplete + YouTube Search API + Date-based trending
    """
    trending = []
    today = datetime.now()
    current_month = today.strftime("%B")
    current_year = today.strftime("%Y")
    
    # Source 1: YouTube Autocomplete Suggestions (No API key needed, real-time)
    try:
        import requests
        queries_to_check = [
            f"{topic} pakistan",
            "village vlog pakistan",
            "desi village life",
            "gaon ki zindagi"
        ]
        
        for q in queries_to_check[:2]:  # Check top 2 to avoid rate limit
            try:
                url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={q.replace(' ', '+')}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    # Parse YouTube suggestions - they return JSONP
                    text_resp = resp.text
                    # Extract suggestions from response like ["query", ["suggestion1", "suggestion2"]]
                    import json
                    # Clean JSONP: remove leading )]}' etc and get JSON array
                    # YouTube returns something like: window.google.ac.h(["query", ["sug1", "sug2"]])
                    # Try to extract second array
                    if '["' in text_resp:
                        start = text_resp.find('[["')
                        if start == -1:
                            start = text_resp.find('["')
                        # Simple extraction
                        try:
                            # Find the suggestions array
                            import re
                            matches = re.findall(r'"([^"]+)"', text_resp)
                            # First match is original query, rest are suggestions
                            if len(matches) > 1:
                                suggestions = matches[1:6]  # Top 5 suggestions
                                for s in suggestions:
                                    if len(s) > 3 and len(s) < 40:
                                        trending.append(s.lower())
                        except:
                            pass
            except:
                continue
        print(f"Live YouTube Autocomplete trending: {trending[:5]}")
    except Exception as e:
        print(f"Autocomplete search failed: {e}")
    
    # Source 2: YouTube Data API - Search trending village videos last 7 days
    try:
        youtube = build_youtube_client()
        # Search recent popular village videos
        search_response = youtube.search().list(
            q="village vlog pakistan desi life",
            part="snippet",
            type="video",
            order="viewCount",
            maxResults=10,
            publishedAfter=(datetime.now() - timedelta(days=7)).isoformat() + "Z",
            regionCode="PK",
            relevanceLanguage="ur"
        ).execute()
        
        for item in search_response.get("items", []):
            title = item["snippet"]["title"].lower()
            # Extract keywords from trending titles
            # Remove common words, keep meaningful
            words = title.split()
            for w in words:
                clean = ''.join(c for c in w if c.isalnum())
                if len(clean) > 3 and clean not in ["pakistan", "village", "official", "desi", "life", "vlog"]:
                    if clean not in trending:
                        trending.append(clean)
            # Also add full title as keyword if short
            if len(title) < 50:
                trending.append(title)
        
        print(f"Live YouTube Search trending: {trending[:5]}")
    except Exception as e:
        print(f"YouTube trending search failed (maybe quota): {e}")
    
    # Source 3: Date-based trending (Eid, season, etc) - 2026 calendar
    try:
        month = today.month
        seasonal_keywords = []
        
        if month in [3, 4]:  # March-April - Wheat harvest season
            seasonal_keywords = ["gandum katai 2026", "wheat harvest pakistan", "gandum ka season"]
        elif month in [5, 6]:  # May-June - Mango season
            seasonal_keywords = ["aam ka bagh 2026", "mango season pakistan", "garmi me gaon"]
        elif month in [6, 7, 8]:  # Monsoon
            seasonal_keywords = ["barish me gaon", "monsoon village pakistan", "baad gaon jannat"]
        elif month in [9, 10]:  # Rice, etc
            seasonal_keywords = ["chawal ki fasal", "khet me pani", "village life october"]
        elif month in [11, 12, 1, 2]:  # Winter
            seasonal_keywords = ["sardi me gaon", "chulha aur kahani", "thand me gaon"]
        
        # Festival keywords
        if month == 6 or month == 3:  # Eid approximate
            seasonal_keywords.extend(["eid ul adha gaon", "eid ki khushi gaon", "gaon me eid 2026"])
        
        trending.extend(seasonal_keywords)
        print(f"Seasonal trending: {seasonal_keywords}")
    except:
        pass
    
    # Source 4: Gemini AI for trending prediction (uses knowledge + current date)
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        prompt = f"Today date {today.strftime('%Y-%m-%d')}, topic {topic}, Pakistan village YouTube niche. Give 10 trending viral keywords that are currently viral on YouTube Pakistan in 2026 for this topic. ONLY comma-separated keywords, no explanation. Must include year 2026, viral, trending words. Example: gandum katai viral 2026, village life pakistan trending, etc. Topic: {topic}"
        
        r = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        txt = r.text.strip().replace("\n", ",")
        gemini_keywords = [k.strip().lower() for k in txt.split(",") if len(k.strip()) > 3 and len(k.strip()) < 50]
        trending.extend(gemini_keywords[:8])
        print(f"Gemini trending: {gemini_keywords[:5]}")
    except Exception as e:
        print(f"Gemini trending failed: {e}")
    
    # Clean and deduplicate, keep 15
    seen = set()
    final_trending = []
    for kw in trending:
        kw_clean = kw.strip().lower()
        # Filter too short, too long, duplicates
        if 4 < len(kw_clean) < 45 and kw_clean not in seen:
            # Avoid generic single words
            if len(kw_clean.split()) >= 2 or "2026" in kw_clean or "viral" in kw_clean:
                seen.add(kw_clean)
                final_trending.append(kw_clean)
        if len(final_trending) >= 15:
            break
    
    # If no trending found, fallback to viral base
    if not final_trending:
        final_trending = get_viral_keywords_for_topic(topic, is_short)[:10]
    
    print(f"🔥 FINAL LIVE TRENDING KEYWORDS ({len(final_trending)}): {final_trending}")
    return final_trending

# Add timedelta import
from datetime import timedelta


def get_viral_description(topic, is_short=False):
    """Generate viral description with trending keywords 2026"""
    keywords_str = ", ".join(get_viral_keywords_for_topic(topic, is_short)[:5])
    
    if is_short:
        return f"""{topic} - Gaon ka asli jadoo! 😱

Aaj ki video me {topic} ki kahani - Pakistani village life ka viral moment!

🔥 Keywords: {keywords_str}
📌 Trending: #VillageVlog #DesiLife #GaonKiZindagi #RuralPakistan

👍 Like karo, Share karo, Subscribe karo @DesiLifeOfficial

#shorts #village #desi #pakistan #viral #trending #gaon #desilife #villagelife #punjabi
"""
    else:
        return f"""Aaj ki video me {topic} ki poori kahani + 2026 me kitni kamai? 😱

Chapters:
00:00 Hook - Dekho doston!
01:15 Part 1 - Gaon ki subah aur {topic}
02:45 Earning - {topic} se 1 lakh kaise?
04:30 Secret - Sabse important raaz!
06:30 Twist - Gaon vs Sheher
08:00 End - Like Share Subscribe!

🔥 Viral Keywords: {keywords_str}
📌 Trending: #VillageVlog2026 #DesiLifeOfficial #GaonKiZindagi #PakistanVillage

Aapke gaon me {topic} kaise hota hai? Comment me batao!

👍 LIKE karo agar gaon se pyaar hai
💬 COMMENT karo apna gaon kahan hai
🔔 SUBSCRIBE karo bell dabao

#VillageVlog #VillageLife #PakistanVillage #DesiLife #GaonKiZindagi #RuralPakistan #PunjabiVillage #DesiVillage #VillageCooking #DesiLifeOfficial #VillageLifePakistan #2026Viral #TrendingPakistan #ViralVillage #DesiViral

Search: {topic} pakistan, {topic} village, {topic} desi life, village vlog pakistan, pakistani village life, desi village life, rural pakistan, punjabi village life, gaon ki zindagi, desi life official
"""



def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                h = json.load(f)
                # Ensure all anti-repetition fields exist
                h.setdefault("used_titles", [])
                h.setdefault("used_hooks", [])
                h.setdefault("used_topics", [])
                h.setdefault("used_video_ids", [])
                h.setdefault("used_captions", [])
                h.setdefault("used_pexels_queries", [])
                h.setdefault("used_tags", [])
                h.setdefault("used_descriptions", [])
                return h
    except Exception as e:
        print(f"History load failed: {e}")
    return {
        "used_titles": [], 
        "used_hooks": [],
        "used_topics": [],
        "used_video_ids": [], 
        "used_captions": [],
        "used_pexels_queries": [],
        "used_tags": [],
        "used_descriptions": [],
        "playlists": {}
    }

def save_history(h):
    try:
        # Keep only last N to avoid bloat but prevent repetition
        h["used_titles"] = h["used_titles"][-100:]
        h["used_hooks"] = h["used_hooks"][-100:]
        h["used_topics"] = h["used_topics"][-50:]
        h["used_video_ids"] = h["used_video_ids"][-200:]
        h["used_captions"] = h["used_captions"][-100:]
        h["used_pexels_queries"] = h["used_pexels_queries"][-100:]
        h["used_tags"] = h["used_tags"][-200:]
        h["used_descriptions"] = h["used_descriptions"][-100:]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
        print(f"History saved: {len(h['used_titles'])} titles, {len(h['used_hooks'])} hooks, {len(h['used_topics'])} topics, {len(h['used_video_ids'])} clips - NO REPETITION GUARANTEED")
    except Exception as e:
        print(f"History save failed: {e}")

def is_repeated(item, used_list, threshold=0.8):
    """Check if item is similar to used items (fuzzy match)"""
    item_lower = item.lower().strip()
    for used in used_list:
        used_lower = used.lower().strip()
        # Exact match
        if item_lower == used_lower:
            return True
        # 80% similarity - contains same words
        if len(item_lower.split()) > 2 and len(used_lower.split()) > 2:
            item_words = set(item_lower.split())
            used_words = set(used_lower.split())
            common = len(item_words & used_words)
            total = len(item_words | used_words)
            if total > 0 and (common / total) > threshold:
                return True
    return False


def get_script(is_short, history):
    client = genai.Client(api_key=GEMINI_KEY)
    today = datetime.now().strftime("%Y-%m-%d-%H-%M")
    seed = random.randint(1, 9999999)
    used = ", ".join(history["used_titles"][-5:]) if history["used_titles"] else "none"
    SHORT_TOPICS = ["gaon ki subah 5 baje ka jadoo","chulhe par desi chai ka zaiqa","khet me bail gadi ka safar","mitti ka chulha kaise jalta hai dekho","gaon ka nalka - thanda pani","dadi ka charkha - purani yaadein","gaon ke bachche khelte hue mastiyan","khet me pani lagana - kisan ki mehnat","gaon ki masjid ki azan","sarson ka khet peela samandar","gandum ki katai ka mausam","bhains ka doodh nikalna - asli lassi","gaon ka mela - full masti","desi lassi banana - thandi thandi","khet me tractor ka zor","gaon ki shaam - sukoon hi sukoon","mitti ke ghar - thande thande","gaon ka kuwa - gehra raaz","desi khana chulhe par - chatpatta","khet me parinde - subah ki ronak"]
    LONG_TOPICS = ["gaon ki shaadi kaise hoti hai - poora riwaj 3 din ka jashan","gandum ki fasal ugane ka poora tarika 0 se 100","chulhe par desi khana kaise banta hai - 5 dishes","gaon ki subah se shaam tak ki zindagi - full day routine","barish ke baad gaon ka khoobsurat manzar - jannat jaisa","gaon ke mele ki raunaq aur khail - bachpan yaad ayega","kisan ki mehnat - khet se mandi tak 1 lakh kaise kamaye","mitti ke ghar kaise bante hain - bina cement ke","gaon me Eid kaise manate hain - subah se shaam tak masti","desi lassi aur makhan kaise banta hai - asli tareeqa","gaon me pani ka intezam - kuwe aur nalke ka raaz","garmi me gaon ki thandi shaam - nehar kinare","sardi me gaon ka chulha aur kahani - dadi ki kahani","gaon ki aurat ki din bhar ki mehnat - subah 5 se raat 10","gaon ke bachchon ka school jana - 5 km paidal","bail gadi se khet tak safar - slow life ka maza","sarson ke khet ki khoobsurati - drone view jaisa","aam ke bagh me garmi ka maza - khatte meetha aam","gaon ki biryani aur desi zaiqa - chulhe wali biryani","mitti ke bartan kaise bante hain - kumhar ki kala","gaon me machhli pakadna - nehar se 10 kg machhli","gaon ka bazaar - sabzi mandi sasti sabzi","gaon me shadi ki taiyariyan - 1 mahina pehle se","khet me hal chalana - purana tareeqa vs tractor","gaon ki raat - chand aur sitare bina light ke","desi murgi palna gaon me - mahine ke 20 hazar kamai","gaon me bhains palna aur doodh - roz 20 liter","gaon ka desi ilaj - jari bootiyan se ilaj","gaon ki kahani - buzurgon ki zuban se 100 saal purani","sheher aur gaon ki zindagi me farq - kaun behtar","gaon me ghar kaise banta hai 2 lakh me - full detail","gaon ki zameen kitne ki hai - 1 acre ka rate","gaon me bijli nahi to kya karte hain - jugad","gaon ki sasti zindagi - 500 me pura din","gaon ka asli sukoon - sheher wale kyun taraste hain"]
    # ANTI-REPETITION: Pick topic not used recently
    used_topics_list = [t.lower() for t in history.get("used_topics", [])[-30:]]
    if is_short:
        random.seed(f"{today}-{seed}")
        fresh_short = [t for t in SHORT_TOPICS if t.lower() not in used_topics_list and not any(t.lower() in ut or ut in t.lower() for ut in used_topics_list)]
        topic = random.choice(fresh_short if fresh_short else SHORT_TOPICS)
        random.seed()
        print(f"SHORT TOPIC PICKED: {topic} (from {len(fresh_short)} fresh out of {len(SHORT_TOPICS)})")
        prompt = f"You are viral Pakistani village shorts writer for MAX views 2026. ONLY valid JSON. Topic: {topic} DateSeed: {today}-{seed} Avoid old: {used} VIRAL SHORT RULES 2026: Title 55 chars MAX Roman Urdu + emoji, MUST include | Desi Life Official, Description 3 lines CTA + 15 hashtags, BUT urdu_voice MUST BE IN PURE URDU SCRIPT (Nastaliq اردو) - 100% Urdu script like السلام علیکم پیارے دوستو! - 30-35 sec, FIRST 3 words in Urdu script must be دیکھو دوستو!, Caption BIG BOLD 35 chars, Hook text UNIQUE per topic Roman Urdu 2 words MAX (<12 chars) like CHULHE KA JADOO?! NEVER use 30 HAZAR for all videos! JSON ONLY: {{\"title\":\"{topic.title()} 😱 Dekho Kya Hua | Desi Life Official\", \"description\":\"{topic} - Gaon ka asli jadoo dekho! #viral #shorts\", \"tags\":[\"village shorts viral\",\"desi shorts\",\"gaon\",\"DesiLifeOfficial\"], \"pexels_queries\":[\"{topic} pakistan village vertical\",\"village pakistan portrait\"], \"urdu_voice\":\"السلام علیکم پیارے دوستو! دیکھو دوستو! {topic} گاؤں کی زندگی کا سب سے خوبصورت راز ہے! یہاں صبح پانچ بجے ٹھنڈی ہوا، کھلے کھیت، اور لوگوں کا پیار ہے! شہر والے اس سکون کے لیے ترستے ہیں! یہ ہے اصلی پاکستان!\", \"caption\":\"{topic.upper()[:35]} 😱🔥\", \"hook_text\":\"UNIQUE HOOK FOR {topic}\"}}"
    else:
        random.seed(f"{today}-{seed}-long")
        fresh_long = [t for t in LONG_TOPICS if t.lower() not in used_topics_list and not any(t.lower() in ut or ut in t.lower() for ut in used_topics_list)]
        topic = random.choice(fresh_long if fresh_long else LONG_TOPICS)
        random.seed()
        print(f"LONG TOPIC PICKED: {topic} (from {len(fresh_long)} fresh out of {len(LONG_TOPICS)})")
        # Generate unique hook per topic
        prompt = f"You are top Pakistani village vlogger 2026 algorithm for MAX retention + monetization + story format. ONLY valid JSON. Need 8 min 5 sec video (mid-roll eligible) = 900 words. Topic: {topic} DateSeed: {today}-{seed}-long Avoid old: {used} 2026 RETENTION FORMULA: 8:05 min = 900 words, Story format 40% higher retention, First 30 sec critical, Include chapters 00:00 Hook, 01:15 Part1, 02:45 Earning, 04:30 Secret, 06:30 Twist, End CTA, Must include: Rukiye! 4:30 pe raaz, Last tak dekho, Unique hook per topic <12 chars e.g. for shaadi topic = 3 DIN JASHAN?! for gandum topic = 1 LAKH FAIDA?! for mitti ghar topic = BINA CEMENT?! JSON ONLY 900 words urdu_voice: {{\"title\":\"{topic.title()} - Unique Hook? 😱 | Desi Life Official\", \"description\":\"Aaj {topic} ki poori kahani + kamai 2026! Chapters: 00:00 Hook, 01:15 Part1, 02:45 Earning, 04:30 Secret, 06:30 Twist #desilife\", \"tags\":[\"village life pakistan viral long 8 min\",\"desi life official\",\"gaon ki kahani 8 min\"], \"pexels_queries\":[\"{topic} pakistan village horizontal\",\"pakistan village life landscape\"], \"urdu_voice\":\"Assalam-o-Alaikum pyare doston! Dekho doston aaj ka topic sunke aap hairan ho jaoge aur end tak dekhna kyunki sabse important raaz main 4 minute 30 second pe bataunga! {topic}! Doston gaon ki zindagi me itna sukoon hai ke sheher wale taraste hain! Subah 5 baje azan ki awaz, thandi hawa, aur khet sone jaise chamak rahe! Lekin rukiye, ye sirf khoobsurati nahi! {topic} hamari 100 saal purani riwayat hai! Buzurg kehte hain gaon ki mitti me barkat hai! Part 1 suno: Gaon me log subah 4 baje uthte hain, khet me jate hain, aur shaam tak mehnat karte hain! {topic} ka tareeqa dekho to hairan ho jaoge! Part 2, kitni kamai? Doston {topic} se log mahine ke 30 se 50 hazar tak kamate hain! 1 acre se 1 lakh tak! Sheher me mahina lagta hai, gaon me 5 din! Part 3: 4:30 wala raaz - gaon me kharcha kam hai, 500 me din nikal jata hai! Sheher me 5000! Isi liye gaon ke log zyada khush hain! End: Video pasand aaye to Like Share Subscribe karo!\", \"caption\":\"{topic.title()[:35]} - UNIQUE? 😱🔥\", \"hook_text\":\"UNIQUE\"}}"
    for m in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]:
        try:
            r = client.models.generate_content(model=m, contents=prompt)
            txt = r.text.replace("```json","").replace("```","").strip()
            if txt.lower().startswith("json"): txt = txt[4:].strip()
            data = json.loads(txt)
            if "urdu_voice" in data and len(data["urdu_voice"]) > 100:
                # 2026 fix: Ensure unique hook not same
                hook = data.get("hook_text","").upper()
                if len(hook) > 12:
                    hook = hook[:12]
                # Make hook unique per topic if generic
                if hook in ["30 HAZAR?!", "30 HAZAR", "GAON MEIN"]:
                    # Generate topic-based hook
                    topic_words = topic.split()[:2]
                    hook = f"{topic_words[0][:4].upper()} {topic_words[1][:4].upper()}?!" if len(topic_words)>1 else f"{topic[:8].upper()}?!"
                    hook = hook[:12]
                data["hook_text"] = hook
                # 2026: Ensure 8 min = 900 words ~ 5000 chars
                if not is_short and len(data["urdu_voice"]) < 1500:
                    continue
                return data
        except Exception as e:
            print(f"Gemini {m} failed {e}")
            continue
    # Fallback with UNIQUE hooks per topic
    if is_short:
        # Unique short hook
        short_hooks = [f"{topic.split()[0][:4].upper()} JADOO?!", f"{topic.split()[0][:5].upper()} RAAZ?!", "DEKHO JADOO?!", "GAON KA RAAZ?!"]
        hook = random.choice(short_hooks)[:12]
        viral_tags_short = get_viral_keywords_for_topic(topic, is_short=True)
        viral_desc_short = get_viral_description(topic, is_short=True)
        return {"title": f"{topic.title()} Dekho Jadoo 😱 | Desi Life Official", "description": viral_desc_short, "tags": viral_tags_short, "pexels_queries": [f"{topic} pakistan vertical","village pakistan"], "urdu_voice": f"السلام علیکم پیارے دوستو! دیکھو دوستو! آج ہم بات کریں گے {topic} کے بارے میں۔ گاؤں کی زندگی بہت خوبصورت ہے۔ یہاں صبح ٹھنڈی ہوا چلتی ہے، کسان کھیت میں کام کرتا ہے، اور شام کو سب مل کر بیٹھتے ہیں۔ {topic} ہماری پہچان ہے۔ ویڈیو پسند آئے تو لائک سبسکرائب ضرور کریں۔", "caption": topic.upper()[:40]+" 😱", "hook_text": hook}
    else:
        # 2026 UNIQUE hook mapping per topic type
        hook_map = {
            "shaadi": "3 DIN JASHAN?!",
            "gandum": "1 LAKH FAIDA?!",
            "chulhe": "CHULHE KA JADOO?!",
            "subah": "5 BAJE RAAZ?!",
            "barish": "JANNAT JAISA?!",
            "mela": "MELA RONAQUE?!",
            "kisan": "1 LAKH KAMAI?!",
            "mitti": "BINA CEMENT?!",
            "Eid": "EID KA JASHAN?!",
            "lassi": "ASLI LASSI?!",
            "pani": "PAANI KA RAAZ?!",
            "nehar": "THANDI SHAAM?!",
            "chulha": "DADI KI KAHANI?!",
            "aurat": "DIN BHAR MEHNAT?!",
            "school": "5 KM PAIDAL?!",
            "bail gadi": "SLOW LIFE?!",
            "sarson": "PEELA SAMANDAR?!",
            "aam": "KHATTA MEETHA?!",
            "biryani": "CHULHE WALI?!",
            "bartan": "KUMHAR KALA?!",
            "machhli": "10 KG MACHHLI?!",
            "bazaar": "SASTI SABZI?!",
            "shadi": "1 MAHINA TAYARI?!",
            "hal": "BAIL VS TRACTOR?!",
            "raat": "CHAND SITARE?!",
            "murgi": "20 HAZAR KAMAI?!",
            "bhains": "20 LITER DOODH?!",
            "ilaj": "JARI BOOTI?!",
            "kahani": "100 SAAL PURANI?!",
            "farq": "GAON VS SHEHER?!",
            "ghar": "2 LAKH MEIN?!",
            "zameen": "1 ACRE RATE?!",
            "bijli": "JUGAD LIGHT?!",
            "sasti": "500 MEIN DIN?!",
            "sukoon": "SHEHER TARSE?!"
        }
        # Find matching hook
        unique_hook = "YE KYA?!"
        for key, h in hook_map.items():
            if key in topic.lower():
                unique_hook = h
                break
        # 2026: 8:05 min = 900 words = 5000 chars guaranteed
        base_voice = f"السلام علیکم پیارے دوستو! دیکھو دوستو! آج کا موضوع {topic} سن کر آپ حیران ہو جاؤ گے اور آخر تک دیکھنا کیونکہ سب سے اہم راز میں 4 منٹ 30 سیکنڈ پہ بتاؤں گا! {topic}! دوستو گاؤں کی زندگی میں اتنا سکون ہے کہ شہر والے ترستے ہیں! صبح 5 بجے اذان کی آواز، ٹھنڈی ہوا، اور کھیت سونے جیسے چمک رہے ہیں! لیکن رکیے، یہ صرف خوبصورتی نہیں! {topic} ہماری 100 سال پرانی روایت ہے جو آج بھی زندہ ہے! بزرگ کہتے ہیں گاؤں کی مٹی میں برکت ہے! گاؤں میں لوگ صبح 4 بجے اٹھتے ہیں، کھیت میں جاتے ہیں، اور شام تک محنت کرتے ہیں! {topic} کا طریقہ دیکھو تو حیران ہو جاؤ گے! پرانے زمانے سے یہی چلتا آ رہا ہے! شہر والے یہ محنت دیکھ کر شرمندہ ہو جاتے ہیں! اب سب سے اہم، کتنی کمائی ہوتی ہے؟ دوستو {topic} سے لوگ مہینے کے 30 سے 50 ہزار تک کماتے ہیں! ہاں سچ میں! 1 ایکڑ سے 1 لاکھ تک! شہر میں اتنے کے لیے پورا مہینہ دفتر جانا پڑتا ہے، گاؤں میں 5 دن کا کام! سستا کھانا، مفت ہوا، اور اپنی زمین! رکیے، 4:30 والا راز: سب سے بڑا فائدہ یہ ہے کہ گاؤں میں خرچہ بہت کم ہے! 500 روپے میں پورا دن نکل جاتا ہے! شہر میں 5000 لگتے ہیں! اسی لیے گاؤں کے لوگ زیادہ خوش ہیں! ان کے چہرے پہ سکون ہے! بچپن یاد آئے گا یہ دیکھ کر! دوستو اگر آپ بھی گاؤں سے ہیں تو کمنٹ میں بتاؤ! آپ کے گاؤں میں {topic} کیسے ہوتا ہے؟ کیا آپ نے کبھی دیکھا ہے؟ تو دوستو اگر ویڈیو پسند آئے تو لائک کرو، شیئر کرو اپنے دوستوں سے، چینل کو سبسکرائب کرو اور بیل آئیکون ضرور دباؤ تاکہ ہر ویڈیو سب سے پہلے آپ کو ملے! "
        long_voice = (base_voice + " ") * 2
        long_voice = long_voice[:5000]  # 8:05 min = 5000 chars
        viral_tags = get_viral_keywords_for_topic(topic, is_short=False)
        viral_desc = get_viral_description(topic, is_short=False)
        return {"title": f"{topic.title()} - {unique_hook} 😱 | Desi Life Official", "description": viral_desc, "tags": viral_tags, "pexels_queries": [f"{topic} pakistan horizontal","village pakistan landscape"], "urdu_voice": long_voice, "caption": f"{topic.title()[:25]} - {unique_hook}", "hook_text": unique_hook}


def download_pexels(queries, history, count, is_short):
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    used = set(history.get("used_video_ids", []))
    used_queries = set([q.lower() for q in history.get("used_pexels_queries", [])])
    orientation = "portrait" if is_short else "landscape"
    
    # ANTI-REPETITION: Filter out recently used queries
    fresh_queries = []
    for q in queries:
        if q.lower() not in used_queries and not is_repeated(q, history.get("used_pexels_queries", []), 0.6):
            fresh_queries.append(q)
    # If all queries are used, add random variations
    if not fresh_queries:
        fresh_queries = [f"{q} {random.choice(['2026', 'viral', 'trending', 'new'])}" for q in queries[:2]]
    
    search_queries = fresh_queries + (["village pakistan portrait vertical reel" if is_short else "village pakistan horizontal landscape"]*2)
    
    # Track used queries
    for q in fresh_queries:
        if q not in history["used_pexels_queries"]:
            history["used_pexels_queries"].append(q)
    
    for q in search_queries[:7]:
        if len(clips) >= count: break
        try:
            page = random.randint(1, 10)  # Wider range for more variety
            url = f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}&orientation={orientation}"
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code != 200:
                res = requests.get(f"https://api.pexels.com/videos/search?query={q}&per_page=20&page={page}", headers=headers, timeout=30)
                if res.status_code != 200: continue
            vids = res.json().get("videos", [])
            if not vids: continue
            # ANTI-REPETITION: Only fresh videos not used before
            fresh = [v for v in vids if v["id"] not in used and not is_repeated(str(v["id"]), [str(x) for x in used])]
            pool = fresh if len(fresh) >= 2 else [v for v in vids if v["id"] not in used]
            if not pool:
                pool = vids  # Fallback if all used
            for v in random.sample(pool, min(3, len(pool))):
                if len(clips) >= count: break
                if v["id"] in used:
                    continue
                mp4s = [f for f in v["video_files"] if f["file_type"]=="video/mp4"]
                if not mp4s: continue
                if is_short:
                    vertical = [f for f in mp4s if f["height"] > f["width"]]
                    candidates = vertical if vertical else mp4s
                    candidates = sorted(candidates, key=lambda x: x["width"])
                    link = candidates[min(2, len(candidates)-1)]["link"] if len(candidates)>2 else candidates[-1]["link"]
                else:
                    horiz = [f for f in mp4s if f["width"] >= f["height"]]
                    candidates = horiz if horiz else mp4s
                    good = [f for f in candidates if 1280 <= f["width"] <= 1920]
                    candidates = good if good else candidates
                    link = sorted(candidates, key=lambda x: x["width"])[-1]["link"]
                # Download with unique temp name
                content = requests.get(link, timeout=120).content
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                with open(tmp, 'wb') as f:
                    f.write(content)
                clips.append(tmp)
                used.add(v["id"])
                history["used_video_ids"].append(v["id"])
                print(f"✅ Fresh clip downloaded: {v['id']} for query '{q}' - NO REPETITION")
        except Exception as e:
            print(f"Pexels download failed for {q}: {e}")
            continue
    if not clips:
        raise Exception("No fresh Pexels clips found - all repeated!")
    print(f"✅ Total {len(clips)} FRESH clips downloaded - zero repetition")
    return clips


def download_pexels_image_for_thumbnail(query, is_short):
    headers = {"Authorization": PEXELS_KEY}
    try:
        orientation = "portrait" if is_short else "landscape"
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=15&orientation={orientation}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=15"
            res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None
        photos = res.json().get("photos", [])
        if not photos: return None
        photo = random.choice(photos[:5])
        img_url = photo["src"]["large2x"] or photo["src"]["large"]
        img_data = requests.get(img_url, timeout=20).content
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.write(img_data); tmp.close()
        return tmp.name
    except: return None

def create_caption_image(caption_text, is_short, video_width, video_height):
    from PIL import Image, ImageDraw, ImageFont
    caption_text = caption_text.upper()[:45]
    if is_short:
        img_w, img_h = int(video_width*0.94), 190
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        except: font = ImageFont.load_default()
        for dx in (-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6):
            for dy in (-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6):
                if abs(dx)+abs(dy) > 8: continue
                draw.text((img_w//2+dx, img_h//2+dy), caption_text, font=font, fill=(0,0,0,255), anchor="mm")
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,234,0,255), anchor="mm")
    else:
        img_w, img_h = int(video_width*0.88), 100
        img = Image.new('RGBA', (img_w, img_h), (0,0,0,195))
        draw = ImageDraw.Draw(img)
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        except: font = ImageFont.load_default()
        draw.text((img_w//2, img_h//2), caption_text, font=font, fill=(255,255,255,255), anchor="mm")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def create_hook_image(hook_text, is_short, tw, th):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGBA', (tw, th), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    YELLOW = (255, 234, 0); RED = (225, 6, 0); BLACK = (0, 0, 0); WHITE = (255, 255, 255)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.105) if is_short else int(th*0.125))
        font_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.048))
    except:
        font_big = ImageFont.load_default(); font_mid = ImageFont.load_default()
    short_hook = hook_text[:18].upper()
    if is_short:
        bh = int(th*0.13); by = int(th*0.16)
        draw.rounded_rectangle([int(tw*0.04)+5, by+5, int(tw*0.96)+5, by+bh+5], radius=20, fill=(0,0,0,170))
        draw.rounded_rectangle([int(tw*0.04), by, int(tw*0.96), by+bh], radius=20, fill=RED)
        draw.text((tw//2, by+bh//2), short_hook, font=font_big, fill=YELLOW, anchor="mm", stroke_width=8, stroke_fill=BLACK)
    else:
        top_text = short_hook + " 🔥"
        bbox = draw.textbbox((0,0), top_text, font=font_big)
        pw = bbox[2]-bbox[0] + 60; ph = int(th*0.15); px = (tw - pw)//2; py = int(th*0.035)
        draw.rounded_rectangle([px+6, py+6, px+pw+6, py+ph+6], radius=22, fill=(0,0,0,160))
        draw.rounded_rectangle([px, py, px+pw, py+ph], radius=22, fill=RED)
        draw.text((tw//2, py+ph//2), top_text, font=font_big, fill=YELLOW, anchor="mm", stroke_width=9, stroke_fill=BLACK)
        draw.rectangle([0, int(th*0.83), tw, th], fill=(0,0,0,215))
        draw.rectangle([0, int(th*0.83), tw, int(th*0.83)+5], fill=YELLOW)
        draw.text((tw//2, int(th*0.92)), "⏳ RUKIYE! 4:30 PE RAAZ KHULEGA! ⏳", font=font_mid, fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=BLACK)
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def create_thumbnail(title, is_short, pexels_query="village pakistan", hook_text_override=None):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    tw, th = (1280, 720) if not is_short else (720, 1280)
    YELLOW = (255, 234, 0); RED = (225, 6, 0); BLACK = (0, 0, 0); WHITE = (255, 255, 255)
    bg_path = download_pexels_image_for_thumbnail(pexels_query, is_short)
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert('RGB')
            bg = bg.resize((tw, th), Image.LANCZOS)
            enhancer = ImageEnhance.Color(bg); bg = enhancer.enhance(1.35)
            enhancer2 = ImageEnhance.Brightness(bg); bg = enhancer2.enhance(1.15)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))
            img = bg
        except: img = Image.new('RGB', (tw, th), (28, 36, 28))
    else: img = Image.new('RGB', (tw, th), (28, 36, 28))
    overlay = Image.new('RGBA', (tw, th), (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    for y in range(int(th*0.22)):
        a = int(210 - (y/(th*0.22))*130)
        d.line([(0,y),(tw,y)], fill=(0,0,0,a))
    for y in range(int(th*0.68), th):
        a = int(((y-th*0.68)/(th*0.32))*230)
        d.line([(0,y),(tw,y)], fill=(0,0,0,a))
    for x in range(int(tw*0.18)):
        a = int((1-x/(tw*0.18))*90)
        d.line([(x,0),(x,th)], fill=(0,0,0,a))
        d.line([(tw-1-x,0),(tw-1-x,th)], fill=(0,0,0,a))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    try:
        font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 145 if not is_short else 125)
        font_sec = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62 if not is_short else 58)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except:
        font_main = ImageFont.load_default(); font_sec = ImageFont.load_default(); font_badge = ImageFont.load_default(); font_small = ImageFont.load_default()
    # ANTI-REPETITION: Use provided hook, never default to 30 HAZAR
    if hook_text_override and hook_text_override.strip() and "30 HAZAR" not in hook_text_override.upper():
        hook = hook_text_override.upper()[:14]
    elif hook_text_override:
        # Even if 30 HAZAR passed, make it unique with topic
        import hashlib
        h = hashlib.md5(title.encode()).hexdigest()[:2]
        hook = f"{hook_text_override.upper()[:8]} {h}?!".upper()[:14]
    else:
        clean = title.replace("| Desi Life Official","").strip()
        # Generate unique hook from title words, not generic
        words = clean.split()[:2]
        if words:
            hook = f"{words[0][:6].upper()}?!"
        else:
            hook = "DEKHO?!"
        # Add unique suffix
        choices = ["CHULHA","MITTI","GAON","KISAN","NEHAR","MELE"]
        hook = hook.replace("30 HAZAR?!", random.choice(choices))[:14]
    hook_words = hook.split()[:3]
    hook_short = " ".join(hook_words)[:12]
    curiosity_map = {"30 HAZAR?!": "GAON MEIN 💰", "1 LAKH?!": "5 DIN MEIN?!", "GAON KA RAAZ?!": "KOI NAHI BATATA", "YE KYA?!": "DEKHO JADOO! 😱"}
    secondary = curiosity_map.get(hook_short, "DEKHO! 😱")
    if not is_short:
        draw.rounded_rectangle([28, 20, 210, 68], radius=24, fill=RED)
        draw.text((119, 44), "😱 VIRAL", font=font_badge, fill=WHITE, anchor="mm")
        draw.rounded_rectangle([tw-132, 20, tw-22, 60], radius=10, fill=BLACK, outline=YELLOW, width=3)
        draw.text((tw-77, 40), "6:30", font=font_badge, fill=YELLOW, anchor="mm")
        draw.text((tw//2+5, int(th*0.46)+5), hook_short, font=font_main, fill=(0,0,0,200), anchor="mm")
        draw.text((tw//2, int(th*0.46)), hook_short, font=font_main, fill=YELLOW, anchor="mm", stroke_width=18, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.62)), secondary, font=font_sec, fill=WHITE, anchor="mm", stroke_width=9, stroke_fill=BLACK)
        draw.text((32, int(th*0.92)), "Desi Life Official ✓", font=font_small, fill=WHITE, anchor="lm", stroke_width=2, stroke_fill=BLACK)
    else:
        draw.rounded_rectangle([(tw-200)//2, 18, (tw+200)//2, 62], radius=22, fill=RED)
        draw.text((tw//2, 40), "VIRAL 😱", font=font_badge, fill=WHITE, anchor="mm")
        try: font_emoji = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
        except: font_emoji = font_main
        draw.text((tw//2, int(th*0.32)), "😱", font=font_emoji, fill=WHITE, anchor="mm", stroke_width=8, stroke_fill=BLACK)
        draw.text((tw//2+4, int(th*0.52)+4), hook_short, font=font_main, fill=BLACK, anchor="mm")
        draw.text((tw//2, int(th*0.52)), hook_short, font=font_main, fill=YELLOW, anchor="mm", stroke_width=16, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.64)), secondary, font=font_sec, fill=WHITE, anchor="mm", stroke_width=8, stroke_fill=BLACK)
        draw.text((tw//2, int(th*0.92)), "Desi Life Official", font=font_small, fill=WHITE, anchor="mm", stroke_width=2, stroke_fill=BLACK)
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
    img.save(path, "JPEG", quality=96)
    return path

def create_subscribe_endcard(is_short, tw, th):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (tw, th), (15, 15, 15))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, tw, int(th*0.07)], fill=(255, 0, 0))
    draw.rectangle([0, int(th*0.93), tw, th], fill=(0, 100, 0))
    draw.rounded_rectangle([int(tw*0.05), int(th*0.15), int(tw*0.95), int(th*0.88)], radius=30, fill=(30, 30, 30))
    try:
        font_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.10) if is_short else int(th*0.12))
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.07) if is_short else int(th*0.08))
        font_mid = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(th*0.042) if is_short else int(th*0.045))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(th*0.028) if is_short else int(th*0.032))
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(th*0.022) if is_short else int(th*0.026))
    except:
        font_huge = ImageFont.load_default(); font_big = ImageFont.load_default(); font_mid = ImageFont.load_default(); font_small = ImageFont.load_default(); font_tiny = ImageFont.load_default()
    YT_HANDLE = "YouTube.com/@DesiLifeOfficial"
    FB_HANDLE = "Facebook.com/DesiLifeOfficial"
    YT_SHORT = "@DesiLifeOfficial"
    FB_SHORT = "Desi Life Official"
    if is_short:
        draw.text((tw//2, int(th*0.20)), "🔔", font=font_huge, fill=(255, 255, 255), anchor="mm")
        draw.text((tw//2, int(th*0.30)), "SUBSCRIBE", font=font_big, fill=(255, 0, 0), anchor="mm", stroke_width=3, stroke_fill=(255,255,255))
        draw.text((tw//2, int(th*0.36)), "KAREN", font=font_big, fill=(255,255,255), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        draw.text((tw//2, int(th*0.44)), "Desi Life Official", font=font_mid, fill=(255, 235, 0), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        btn_w, btn_h = int(tw*0.75), int(th*0.065)
        btn_x1, btn_y1 = (tw-btn_w)//2, int(th*0.50)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=25, fill=(255, 0, 0))
        draw.text((tw//2, btn_y1+btn_h//2), "SUBSCRIBED ✓  Bell 🔔", font=font_small, fill=(255,255,255), anchor="mm")
        yt_box_y = int(th*0.59)
        draw.rounded_rectangle([int(tw*0.08), yt_box_y, int(tw*0.92), yt_box_y+int(th*0.08)], radius=15, fill=(200, 0, 0))
        draw.text((int(tw*0.15), yt_box_y+int(th*0.04)), "▶️", font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), yt_box_y+int(th*0.025)), "YouTube", font=font_tiny, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), yt_box_y+int(th*0.055)), YT_HANDLE, font=font_small, fill=(255,255,255), anchor="lm")
        fb_box_y = int(th*0.68)
        draw.rounded_rectangle([int(tw*0.08), fb_box_y, int(tw*0.92), fb_box_y+int(th*0.08)], radius=15, fill=(0, 80, 180))
        draw.text((int(tw*0.15), fb_box_y+int(th*0.04)), "📘", font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((int(tw*0.25), fb_box_y+int(th*0.025)), "Facebook", font=font_tiny, fill=(200,220,255), anchor="lm")
        draw.text((int(tw*0.25), fb_box_y+int(th*0.055)), FB_HANDLE, font=font_small, fill=(255,255,255), anchor="lm")
        draw.text((tw//2, int(th*0.80)), "👍 Like  |  💬 Comment  |  ↗️ Share", font=font_small, fill=(255,255,255), anchor="mm")
        draw.text((tw//2, int(th*0.84)), "Har Video Sabse Pehle Dekhne Ke Liye", font=font_tiny, fill=(180,180,180), anchor="mm")
        draw.text((tw//2, int(th*0.87)), "Bell Icon Zaroor Dabayen 🔔", font=font_tiny, fill=(255,235,0), anchor="mm")
    else:
        draw.text((int(tw*0.30), int(th*0.28)), "🔔 SUBSCRIBE KAREN 🔔", font=font_big, fill=(255,255,255), anchor="mm", stroke_width=3, stroke_fill=(0,0,0))
        draw.text((int(tw*0.30), int(th*0.42)), "Desi Life Official", font=font_mid, fill=(255,235,0), anchor="mm", stroke_width=2, stroke_fill=(0,0,0))
        btn_w, btn_h = int(tw*0.22), int(th*0.12)
        btn_x1, btn_y1 = int(tw*0.30-btn_w//2), int(th*0.52)
        draw.rounded_rectangle([btn_x1, btn_y1, btn_x1+btn_w, btn_y1+btn_h], radius=20, fill=(255,0,0))
        draw.text((int(tw*0.30), btn_y1+btn_h//2), "SUBSCRIBE ✓", font=font_mid, fill=(255,255,255), anchor="mm")
        draw.text((int(tw*0.30), int(th*0.75)), "👍 Like  •  💬 Comment  •  ↗️ Share", font=font_small, fill=(220,220,220), anchor="mm")
        draw.text((int(tw*0.30), int(th*0.81)), "Bell Dabana Mat Bhoolna! 🔔", font=font_small, fill=(255,235,0), anchor="mm")
        box_w, box_h = int(tw*0.38), int(th*0.18)
        box_x = int(tw*0.58)
        yt_y = int(th*0.28)
        draw.rounded_rectangle([box_x, yt_y, box_x+box_w, yt_y+box_h], radius=15, fill=(200, 0, 0))
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.30)), "▶️  YouTube Channel", font=font_small, fill=(255,200,200), anchor="lm")
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.65)), YT_SHORT, font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), yt_y+int(box_h*0.85)), YT_HANDLE, font=font_tiny, fill=(255,220,220), anchor="lm")
        fb_y = int(th*0.52)
        draw.rounded_rectangle([box_x, fb_y, box_x+box_w, fb_y+box_h], radius=15, fill=(0, 80, 180))
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.30)), "📘  Facebook Page", font=font_small, fill=(180,210,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.65)), FB_SHORT, font=font_mid, fill=(255,255,255), anchor="lm")
        draw.text((box_x+int(box_w*0.08), fb_y+int(box_h*0.85)), FB_HANDLE, font=font_tiny, fill=(200,220,255), anchor="lm")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    img.save(path, "PNG")
    return path

def resize_and_crop(clip, target_size):
    tw, th = target_size
    cw, ch = clip.w, clip.h
    scale_w = tw / cw
    scale_h = th / ch
    scale = max(scale_w, scale_h)
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    clip = clip.resize((new_w, new_h))
    x_center = new_w // 2
    y_center = new_h // 2
    x1 = x_center - tw // 2
    y1 = y_center - th // 2
    clip = clip.crop(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)
    return clip

def make_video(paths, urdu_text, caption, hook_text, is_short):
    target_size = SHORT_SIZE if is_short else LONG_SIZE
    tw, th = target_size
    
    original_len = len(urdu_text)
    if not is_short:
        if len(urdu_text) < 4000:
            urdu_text = (urdu_text + " ") * 3
            urdu_text = urdu_text[:5000]
        else:
            urdu_text = urdu_text[:5000]
    else:
        urdu_text = urdu_text[:500]
    
    a_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    audio = None
    
    import re as re_clean
    def clean_urdu(t):
        t = re_clean.sub(r'[😀-🙏🌀-🗿🚀-🛿🤐-🧿]', '', t)
        t = re_clean.sub(r'\b(Like|Share|Subscribe|Bell|Desi Life Official|YouTube|Facebook)\b', '', t, flags=re_clean.IGNORECASE)
        t = re_clean.sub(r'\s+', ' ', t).strip()
        return t
    
    clean_text = clean_urdu(urdu_text)
    print(f"Cleaned: {len(clean_text)} chars - ElevenLabs first")
    
    # PRIORITY 1: ElevenLabs
    eleven_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if eleven_key:
        try:
            print(f"=== PRIORITY 1: ElevenLabs MOST NATURAL - {len(clean_text)} chars ===")
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=eleven_key)
            
            if len(clean_text) > 2500 and not is_short:
                chunks = [clean_text[i:i+2400] for i in range(0, len(clean_text), 2400)]
                chunk_files = []
                for idx, chunk in enumerate(chunks):
                    chunk_path = tempfile.NamedTemporaryFile(delete=False, suffix=f"_eleven{idx}.mp3").name
                    audio_gen = client.text_to_speech.convert(
                        voice_id="pFZP5JQG7iQjIQuC4Bku",
                        model_id="eleven_multilingual_v2",
                        text=chunk,
                        output_format="mp3_44100_128"
                    )
                    with open(chunk_path, "wb") as f:
                        for c in audio_gen:
                            f.write(c)
                    if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 500:
                        chunk_files.append(chunk_path)
                        print(f"ElevenLabs Chunk {idx+1}/{len(chunks)} OK")
                
                if chunk_files:
                    from moviepy.editor import concatenate_audioclips
                    audios = [AudioFileClip(f) for f in chunk_files]
                    combined = concatenate_audioclips(audios)
                    combined.write_audiofile(a_path, logger=None)
                    audio = AudioFileClip(a_path)
                    print(f"✅ ElevenLabs CHUNKED SUCCESS - {audio.duration:.1f}s")
                    for f in chunk_files:
                        try: os.remove(f)
                        except: pass
            else:
                audio_gen = client.text_to_speech.convert(
                    voice_id="pFZP5JQG7iQjIQuC4Bku",
                    model_id="eleven_multilingual_v2",
                    text=clean_text[:4000],
                    output_format="mp3_44100_128"
                )
                with open(a_path, "wb") as f:
                    for chunk in audio_gen:
                        f.write(chunk)
                audio = AudioFileClip(a_path)
                print(f"✅ ElevenLabs SUCCESS - {audio.duration:.1f}s MOST NATURAL")
        except Exception as e:
            print(f"ElevenLabs failed: {e}")
            import traceback
            traceback.print_exc()
            audio = None
    else:
        print("❌ ELEVENLABS_API_KEY missing - set in GitHub Secrets")
    
    # PRIORITY 2: Edge-TTS FREE
    if audio is None:
        try:
            import edge_tts
            import asyncio
            voice_to_use = VOICE_NAME_MALE
            print(f"=== PRIORITY 2: Edge-TTS FREE - {voice_to_use} ===")
            if len(clean_text) > 3000 and not is_short:
                chunks = [clean_text[i:i+2800] for i in range(0, len(clean_text), 2800)]
                chunk_files = []
                for idx, chunk in enumerate(chunks):
                    chunk_path = tempfile.NamedTemporaryFile(delete=False, suffix=f"_chunk{idx}.mp3").name
                    async def gen_chunk(c, p):
                        communicate = edge_tts.Communicate(c, voice_to_use)
                        await communicate.save(p)
                    asyncio.run(gen_chunk(chunk, chunk_path))
                    if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 500:
                        chunk_files.append(chunk_path)
                if chunk_files:
                    from moviepy.editor import concatenate_audioclips
                    audios = [AudioFileClip(f) for f in chunk_files]
                    combined = concatenate_audioclips(audios)
                    combined.write_audiofile(a_path, logger=None)
                    audio = AudioFileClip(a_path)
                    for f in chunk_files:
                        try: os.remove(f)
                        except: pass
            else:
                async def generate_edge_tts():
                    communicate = edge_tts.Communicate(clean_text, voice_to_use)
                    await communicate.save(a_path)
                asyncio.run(generate_edge_tts())
                audio = AudioFileClip(a_path)
                print(f"✅ Edge-TTS SUCCESS - {audio.duration:.1f}s")
        except Exception as e:
            print(f"Edge-TTS failed: {e}")
            audio = None
    
    # PRIORITY 3: gTTS
    if audio is None:
        try:
            tts = gTTS(text=clean_text[:4000], lang='ur', slow=False, tld='com')
            tts.save(a_path)
            audio = AudioFileClip(a_path)
            print(f"gTTS {audio.duration:.1f}s")
        except Exception as e:
            print(f"gTTS failed: {e}")
    
    if audio is None:
        raise Exception("All TTS failed")
    
    print(f"FINAL AUDIO: {audio.duration:.1f}s - ElevenLabs first")
    
    vcs = []
    per = audio.duration / len(paths) if paths else audio.duration
    for p in paths:
        try:
            vc = VideoFileClip(p)
            vc = resize_and_crop(vc, target_size)
            s = random.uniform(0, max(0, vc.duration - per - 0.3))
            vc = vc.subclip(s, s+per+0.5)
            vcs.append(vc)
        except:
            continue
    if not vcs:
        raise Exception("No clips")
    final_v = concatenate_videoclips(vcs, method="compose")
    if final_v.duration < audio.duration:
        final_v = final_v.loop(duration=audio.duration)
    else:
        final_v = final_v.subclip(0, audio.duration)
    final_v = resize_and_crop(final_v, target_size)
    cap_path = create_caption_image(caption, is_short, tw, th)
    cap_clip = ImageClip(cap_path).set_duration(audio.duration)
    cap_clip = cap_clip.set_position(('center', th*0.78)) if is_short else cap_clip.set_position(('center', th*0.82))
    hook_path = create_hook_image(hook_text, is_short, tw, th)
    hook_clip_3sec = ImageClip(hook_path).set_duration(min(3, audio.duration)).set_position(('center','center'))
    final = CompositeVideoClip([final_v, cap_clip, hook_clip_3sec], size=target_size).set_duration(audio.duration).set_audio(audio)
    endcard_path = create_subscribe_endcard(is_short, tw, th)
    endcard_clip = ImageClip(endcard_path).set_duration(4)
    final_with_endcard = concatenate_videoclips([final, endcard_clip], method="compose")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_with_endcard.write_videofile(out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', ffmpeg_params=["-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"], threads=4, logger=None)
    return out



def build_youtube_client():

    # Try to refresh token manually first to show real error
    import os
    yt_client_id = os.environ.get("YOUTUBE_CLIENT_ID","")
    yt_client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET","")
    yt_refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN","")
    print(f"YT Creds check: client_id={yt_client_id[:15]}... secret={'SET' if yt_client_secret else 'MISSING'} refresh={'SET' if yt_refresh else 'MISSING'} len={len(yt_refresh)}")
    
    # Manual refresh attempt for better error message
    try:
        print("--- Trying manual token refresh ---")
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": yt_client_id,
            "client_secret": yt_client_secret,
            "refresh_token": yt_refresh,
            "grant_type": "refresh_token"
        }
        r = requests.post(token_url, data=data, timeout=20)
        print(f"Token refresh response: {r.status_code} {r.text[:800]}")
        if r.status_code != 200:
            print(f"❌ TOKEN EXPIRED! Need to regenerate YOUTUBE_REFRESH_TOKEN in GitHub Secrets!")
            print(f"Go to: https://developers.google.com/oauthplayground")
            print(f"Steps: Select YouTube Data API v3 -> https://www.googleapis.com/auth/youtube.upload -> Authorize -> Exchange -> Copy refresh_token")
    except Exception as e:
        print(f"Manual refresh error: {e}")

    for scopes in [["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.upload"], ["https://www.googleapis.com/auth/youtube.upload"]]:
        try:
            print(f"Trying scopes: {scopes}")
            creds = Credentials(None, refresh_token=yt_refresh, token_uri="https://oauth2.googleapis.com/token", client_id=yt_client_id, client_secret=yt_client_secret, scopes=scopes)
            # Force refresh
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            print(f"✅ Token refreshed! Access token: {creds.token[:20]}...")
            yt = build("youtube","v3", credentials=creds)
            yt.channels().list(part="snippet", mine=True).execute()
            print(f"✅ YouTube client built successfully with scopes {scopes}")
            return yt
        except Exception as e:
            print(f"YT scope {scopes} failed: {e}")
            import traceback
            traceback.print_exc()
            continue
    raise Exception("YOUTUBE_REFRESH_TOKEN invalid - EXPIRED! Regenerate from https://developers.google.com/oauthplayground - Select YouTube Data API v3 scope youtube.upload")

def get_or_create_playlist(youtube, history, title, is_short):
    key = "short" if is_short else "long"
    if key in history.get("playlists", {}) and history["playlists"][key]: return history["playlists"][key]
    try:
        pls = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for pl in pls.get("items", []):
            if title.lower() in pl["snippet"]["title"].lower() or pl["snippet"]["title"].lower() in title.lower():
                history["playlists"][key] = pl["id"]
                return pl["id"]
    except: return None
    try:
        body = {"snippet": {"title": title, "description": f"{title} auto"}, "status": {"privacyStatus": "public"}}
        resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
        history["playlists"][key] = resp["id"]
        return resp["id"]
    except: return None

def upload_to_youtube_and_fb(file_path, title, desc, tags, is_short, history, pexels_query="village pakistan", hook_text="30 HAZAR?!"):
    youtube = build_youtube_client()
    yt_title = title[:95]
    chunk_size = 1024*1024*10 if not is_short else 1024*1024*5
    body = {"snippet":{"title":yt_title,"description":desc,"tags":tags,"categoryId":"22"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True, chunksize=chunk_size)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp=None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"YouTube Upload {int(st.progress()*100)}% - {'LONG 6min PRO CTR' if not is_short else 'SHORT PRO CTR'}")
    vid = resp.get('id')
    print(f"YouTube SUCCESS https://youtu.be/{vid}")
    try:
        thumb_path = create_thumbnail(title, is_short=is_short, pexels_query=pexels_query, hook_text_override=hook_text)
        youtube.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg", resumable=False)).execute()
        print(f"✅ PRO THUMBNAIL UPLOADED {vid}")
    except Exception as e:
        print(f"Thumbnail skip: {e}")
    try:
        pid = get_or_create_playlist(youtube, history, SHORT_TITLE if is_short else LONG_TITLE, is_short)
        if pid:
            youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    except: pass
    if not FB_ENABLED: print("--- Facebook DISABLED ---")
    if not TIKTOK_ENABLED: print("--- TikTok DISABLED ---")
    return resp

def run_once(is_short=False):
    h = load_history()
    print(f"--- {'SHORT 1080x1920 REEL ULTIMATE CTR' if is_short else 'LONG 1920x1080 VIDEO 8:05 MIN ULTIMATE CTR 2026 LIVE TRENDING'} START ---")
    data = get_script(is_short, h)
    # LIVE TRENDING SEARCH - Har dafa naya trending keywords
    print(f"🔍 LIVE SEARCH: Fetching real-time trending keywords for topic...")
    live_trending = fetch_live_trending_keywords(data.get("pexels_queries", ["village"])[0] if data.get("pexels_queries") else data.get("title","village"), is_short=is_short)
    # Merge live trending with existing tags - live first
    existing_tags = data.get("tags", [])
    merged_tags = live_trending[:8] + [t for t in existing_tags if t.lower() not in [lt.lower() for lt in live_trending]][:7]
    data["tags"] = merged_tags[:15]
    print(f"✅ MERGED VIRAL TAGS: {data['tags']}")
    print(f"Title: {data['title']} | Hook: {data.get('hook_text','')} | Voice len: {len(data['urdu_voice'])} chars")
    # ANTI-REPETITION: Save all to history
    h.setdefault("used_hooks", []).append(data.get("hook_text",""))
    h.setdefault("used_topics", []).append(data.get("pexels_queries", [""])[0] if data.get("pexels_queries") else data.get("title",""))
    h.setdefault("used_captions", []).append(data.get("caption",""))
    for tag in data.get("tags", [])[:5]:
        if tag not in h.setdefault("used_tags", []):
            h["used_tags"].append(tag)
    h["used_titles"].append(data["title"])
    clip_count = 2 if is_short else 6
    clips = download_pexels(data["pexels_queries"], h, count=clip_count, is_short=is_short)
    if not clips: raise Exception("No Pexels clips")
    final = make_video(clips, data["urdu_voice"], data["caption"], data.get("hook_text","30 HAZAR?!"), is_short)
    pexels_q = data["pexels_queries"][0] if data.get("pexels_queries") else "village pakistan"
    upload_to_youtube_and_fb(final, data["title"], data["description"], data["tags"], is_short, h, pexels_q, data.get("hook_text","30 HAZAR?!"))
    save_history(h)

if __name__ == "__main__":
    run_once(is_short=(os.environ.get("MODE","long")=="short"))
