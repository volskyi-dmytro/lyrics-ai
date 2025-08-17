from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import base64, os
from datetime import datetime, timezone
import logging
import hashlib
import json
import asyncio
import uuid

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

try:
    import redis
except Exception:
    redis = None  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- REDIS SETUP ----------
redis_client = None
if redis:
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        redis_client.ping()
        logger.info(f"Redis connected successfully: {redis_url}")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Caching disabled.")
        redis_client = None

# ---------- PROGRESS TRACKING ----------
# Store progress data (in production, use Redis or database)
progress_store = {}

class ProgressTracker:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.progress = 0
        self.status = "Starting..."
        self.start_time = datetime.now()
        self.result = None
        self.error = None
        progress_store[request_id] = self
    
    async def update(self, progress: int, status: str):
        self.progress = min(progress, 100)
        self.status = status
        logger.info(f"Progress {self.request_id}: {progress}% - {status}")
    
    def to_dict(self):
        data = {
            "request_id": self.request_id,
            "progress": self.progress,
            "status": self.status,
            "elapsed_time": (datetime.now() - self.start_time).total_seconds()
        }
        if self.result:
            data["result"] = {
                "summary": self.result.summary,
                "imageUrl": self.result.imageUrl
            }
        if self.error:
            data["error"] = self.error
        return data

# ---------- CACHE UTILITIES ----------
# Cache statistics
cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "errors": 0
}

def get_cache_key(prefix: str, *args) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [prefix] + [str(arg).lower().strip() for arg in args]
    return ":".join(key_parts)

def get_content_hash(content: str) -> str:
    """Generate SHA256 hash of content for cache keys."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

async def get_from_cache(key: str) -> Optional[str]:
    """Get value from Redis cache."""
    if not redis_client:
        return None
    try:
        value = redis_client.get(key)
        if value:
            cache_stats["hits"] += 1
            logger.info(f"Cache HIT: {key[:50]}...")
            return value
        cache_stats["misses"] += 1
        logger.info(f"Cache MISS: {key[:50]}...")
        return None
    except Exception as e:
        cache_stats["errors"] += 1
        logger.error(f"Cache get error: {e}")
        return None

async def set_cache(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """Set value in Redis cache with TTL."""
    if not redis_client:
        return False
    try:
        redis_client.setex(key, ttl_seconds, value)
        cache_stats["sets"] += 1
        logger.info(f"Cache SET: {key[:50]}... (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        cache_stats["errors"] += 1
        logger.error(f"Cache set error: {e}")
        return False

async def get_cache_info() -> dict:
    """Get Redis cache information and statistics."""
    cache_info = {
        "redis_connected": redis_client is not None,
        "cache_stats": cache_stats.copy(),
        "redis_info": None
    }
    
    if redis_client:
        try:
            # Get Redis server info
            redis_info = redis_client.info()
            cache_info["redis_info"] = {
                "redis_version": redis_info.get("redis_version"),
                "used_memory_human": redis_info.get("used_memory_human"),
                "connected_clients": redis_info.get("connected_clients"),
                "total_commands_processed": redis_info.get("total_commands_processed"),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0),
                "uptime_in_seconds": redis_info.get("uptime_in_seconds")
            }
            
            # Calculate hit rate
            total_requests = cache_stats["hits"] + cache_stats["misses"]
            if total_requests > 0:
                cache_info["hit_rate"] = round(cache_stats["hits"] / total_requests * 100, 2)
            else:
                cache_info["hit_rate"] = 0.0
                
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            cache_info["redis_error"] = str(e)
    
    return cache_info

# lyricsgenius library removed - using direct API calls instead

def sanitize_input(text: str) -> str:
    """Sanitize and normalize input text by replacing fancy Unicode characters and normalizing whitespace."""
    if not text:
        return ""
    # Replace various Unicode dashes with simple dash
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2015', '-').replace('\u2212', '-')
    # Replace fancy quotes with simple ones
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    # Normalize whitespace
    import re
    text = re.sub(r'\s+', ' ', text.strip())
    return text

app = FastAPI(title="Song Meaning AI")

class SongRequest(BaseModel):
    artist: str
    title: str
    style: Optional[str] = None
    language: Optional[str] = "en"  # "en" for English, "uk" for Ukrainian

class SongResponse(BaseModel):
    summary: str
    imageUrl: str

class SummaryResponse(BaseModel):
    summary: str

class ImageResponse(BaseModel):
    imageUrl: str

class AnalyzeStartResponse(BaseModel):
    request_id: str

# ---------- GLOBAL EXCEPTION HANDLER ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        },
    )

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/cache/health")
async def cache_health():
    """Get cache health status and statistics."""
    return await get_cache_info()

@app.get("/progress/{request_id}")
async def progress_stream(request_id: str):
    """Server-Sent Events endpoint for progress updates."""
    async def event_generator():
        # Send initial connection event
        yield f"data: {json.dumps({'status': 'Connected to progress stream', 'progress': 0})}\n\n"
        
        sent_progress_steps = set()  # Track which progress steps we've sent
        
        while True:
            if request_id in progress_store:
                tracker = progress_store[request_id]
                current_progress = tracker.progress
                
                # Always send current state
                data = json.dumps(tracker.to_dict())
                yield f"data: {data}\n\n"
                
                # Track progress milestones to ensure they're sent
                progress_key = f"{current_progress}:{tracker.status}"
                sent_progress_steps.add(progress_key)
                
                # If completed, send final event and cleanup
                if tracker.progress >= 100:
                    yield f"data: {json.dumps({'status': 'completed', 'progress': 100})}\n\n"
                    # Clean up after 30 seconds
                    await asyncio.sleep(30)
                    progress_store.pop(request_id, None)
                    break
            else:
                yield f"data: {json.dumps({'error': 'Request not found'})}\n\n"
                break
            
            await asyncio.sleep(0.3)  # More frequent updates - every 300ms
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.post("/analyze/start", response_model=AnalyzeStartResponse)
async def analyze_start(req: SongRequest):
    """Start song analysis and return request ID for progress tracking."""
    artist = sanitize_input(req.artist)
    title = sanitize_input(req.title)
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title are required.")
    
    request_id = str(uuid.uuid4())
    
    # Start analysis in background
    asyncio.create_task(analyze_song_background(request_id, req))
    
    return AnalyzeStartResponse(request_id=request_id)

@app.post("/analyze", response_model=SongResponse)
async def analyze(req: SongRequest):
    """Legacy synchronous analyze endpoint (kept for compatibility)."""
    try:
        artist = sanitize_input(req.artist)
        title = sanitize_input(req.title)
        if not artist or not title:
            raise HTTPException(status_code=400, detail="Artist and title are required.")

        lyrics = await fetch_lyrics(artist, title)
        if not lyrics:
            raise HTTPException(status_code=404, detail=f"Lyrics not found for '{artist} - {title}'. Try another song.")

        summary = await summarize_lyrics(lyrics, artist, title, req.language or "en")
        image_url = await generate_song_artwork(artist, title, summary, req.style or "album cover")
        return SongResponse(summary=summary, imageUrl=image_url)

    except HTTPException as http_exc:
        raise http_exc  # let FastAPI handle known errors
    except Exception as e:
        logger.error(f"Error in /analyze endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.post("/summarize", response_model=SummaryResponse)
async def summarize_only(req: SongRequest):
    """Summarize song lyrics only (no image generation)."""
    try:
        artist = sanitize_input(req.artist)
        title = sanitize_input(req.title)
        if not artist or not title:
            raise HTTPException(status_code=400, detail="Artist and title are required.")

        lyrics = await fetch_lyrics(artist, title)
        if not lyrics:
            raise HTTPException(status_code=404, detail=f"Lyrics not found for '{artist} - {title}'. Try another song.")

        summary = await summarize_lyrics(lyrics, artist, title, req.language or "en")
        return SummaryResponse(summary=summary)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in /summarize endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@app.post("/generate", response_model=ImageResponse)
async def generate_only(req: SongRequest):
    """Generate AI artwork only (requires summary in request body)."""
    try:
        artist = sanitize_input(req.artist)
        title = sanitize_input(req.title)
        if not artist or not title:
            raise HTTPException(status_code=400, detail="Artist and title are required.")

        # For image generation, we need lyrics to create a meaningful summary
        lyrics = await fetch_lyrics(artist, title)
        if not lyrics:
            raise HTTPException(status_code=404, detail=f"Lyrics not found for '{artist} - {title}'. Try another song.")

        summary = await summarize_lyrics(lyrics, artist, title, req.language or "en")
        image_url = await generate_song_artwork(artist, title, summary, req.style or "album cover")
        return ImageResponse(imageUrl=image_url)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in /generate endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

async def analyze_song_background(request_id: str, req: SongRequest):
    """Background task for song analysis with progress tracking."""
    tracker = ProgressTracker(request_id)
    
    try:
        artist = sanitize_input(req.artist)
        title = sanitize_input(req.title)
        
        # Step 1: Fetch lyrics (0-30%)
        await tracker.update(5, "Searching for lyrics...")
        lyrics = await fetch_lyrics_with_progress(artist, title, tracker)
        if not lyrics:
            await tracker.update(100, f"Error: Lyrics not found for '{artist} - {title}'")
            return
        
        # Step 2: Generate summary (30-70%)
        await tracker.update(35, "Analyzing song meaning...")
        summary = await summarize_lyrics_with_progress(lyrics, artist, title, req.language or "en", tracker)
        
        # Step 3: Generate artwork (70-100%)
        await tracker.update(75, "Generating AI artwork...")
        image_url = await generate_song_artwork_with_progress(artist, title, summary, req.style or "album cover", tracker)
        
        await tracker.update(100, "Analysis complete!")
        
        # Store final result in tracker
        tracker.result = SongResponse(summary=summary, imageUrl=image_url)
        
    except Exception as e:
        logger.error(f"Background analysis error: {e}", exc_info=True)
        await tracker.update(100, f"Error: {str(e)}")

# ---- Lyrics fetching with Genius ----
async def fetch_lyrics_with_progress(artist: str, title: str, tracker: ProgressTracker) -> Optional[str]:
    """Fetch lyrics with progress updates."""
    await tracker.update(10, "Searching lyrics database...")
    await asyncio.sleep(0.5)  # Small delay to show progress
    
    result = await fetch_lyrics(artist, title)
    
    if result:
        await tracker.update(30, "Lyrics found!")
        await asyncio.sleep(0.3)  # Brief pause before next step
    return result

async def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    # Check cache first
    cache_key = get_cache_key("lyrics", artist, title)
    cached_lyrics = await get_from_cache(cache_key)
    if cached_lyrics:
        return cached_lyrics
    
    genius_token = os.getenv("GENIUS_API_TOKEN")
    if not genius_token:
        demo = {
            ("Metallica", "Nothing Else Matters"): "[Demo lyrics - configure GENIUS_API_TOKEN for real lyrics]",
            ("Океан Ельзи", "Без бою"): "[Demo lyrics - configure GENIUS_API_TOKEN for real lyrics]",
        }
        lyrics = demo.get((artist, title))
        if lyrics:
            # Cache demo lyrics for 24 hours
            await set_cache(cache_key, lyrics, 24 * 3600)
        return lyrics
    try:
        import httpx, re
        search_query = f"{title} {artist}"
        search_url = f"https://api.genius.com/search?q={search_query}"
        headers = {"Authorization": f"Bearer {genius_token}"}
        async with httpx.AsyncClient() as client:
            search_response = await client.get(search_url, headers=headers)
            search_response.raise_for_status()
            search_data = search_response.json()
            hits = search_data.get("response", {}).get("hits", [])
            if not hits:
                return None
            song_data = None
            for hit in hits:
                result = hit.get("result", {})
                if title.lower() in result.get("title", "").lower() and artist.lower() in result.get("primary_artist", {}).get("name", "").lower():
                    song_data = result
                    break
            if not song_data:
                song_data = hits[0].get("result", {})
            song_path = song_data.get("path")
            if not song_path:
                return None
            song_url = f"https://genius.com{song_path}"
            page_response = await client.get(song_url)
            page_response.raise_for_status()
            html_content = page_response.text
            lyrics_match = re.search(r'<div[^>]*data-lyrics-container[^>]*>(.*?)</div>', html_content, re.DOTALL)
            if lyrics_match:
                lyrics_html = lyrics_match.group(1)
                lyrics = re.sub(r'<[^>]+>', '\n', lyrics_html)
                lyrics = re.sub(r'\[.*?\]', '', lyrics)
                lyrics = re.sub(r'\n+', '\n', lyrics).strip()
                if lyrics:
                    # Cache lyrics for 7 days (lyrics don't change)
                    await set_cache(cache_key, lyrics, 7 * 24 * 3600)
                    return lyrics
            lyrics_pattern = r'"lyrics":"([^"]*)"'
            lyrics_match = re.search(lyrics_pattern, html_content)
            if lyrics_match:
                lyrics = lyrics_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                if lyrics.strip():
                    # Cache lyrics for 7 days 
                    await set_cache(cache_key, lyrics.strip(), 7 * 24 * 3600)
                    return lyrics.strip()
        return None
    except Exception as e:
        logger.error(f"Error fetching lyrics: {e}", exc_info=True)
        return None

# ---- Summarization ----
async def summarize_lyrics_with_progress(lyrics: str, artist: str, title: str, language: str, tracker: ProgressTracker) -> str:
    """Summarize lyrics with progress updates."""
    await tracker.update(40, "Processing with AI...")
    await asyncio.sleep(0.8)  # Show processing step
    
    await tracker.update(60, "Generating analysis...")
    await asyncio.sleep(0.5)  # Show generation step
    
    result = await summarize_lyrics(lyrics, artist, title, language)
    
    await tracker.update(70, "Analysis complete!")
    await asyncio.sleep(0.3)  # Brief pause
    return result

async def summarize_lyrics(lyrics: str, artist: str, title: str, language: str = "en") -> str:
    # Check cache first using lyrics hash + language
    lyrics_hash = get_content_hash(lyrics)
    cache_key = get_cache_key("summary", lyrics_hash, language)
    cached_summary = await get_from_cache(cache_key)
    if cached_summary:
        return cached_summary
    
    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI and api_key:
        try:
            client = OpenAI(api_key=api_key)
            if language == "uk":
                prompt = (
                    "Проаналізуй основний зміст та тему цієї пісні у 3-5 реченнях. "
                    "Уникай цитування рядків; Також поясни культурний та історичний контекст, фактичне значення пісні українською мовою.\n\n"
                    f"Виконавець: {artist}\nНазва: {title}\nТекст пісні:\n{lyrics}"
                )
            else:
                prompt = (
                    "Summarize the core meaning/themes of these song lyrics in 3-5 sentences. "
                    "Also explain cultural and historical context, the actual meaning of the song.\n\n"
                    f"Artist: {artist}\nTitle: {title}\nLyrics:\n{lyrics}"
                )
            chat = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=500,
            )
            summary = chat.choices[0].message.content.strip()
            # Cache summary for 7 days
            await set_cache(cache_key, summary, 7 * 24 * 3600)
            return summary
        except Exception as e:
            logger.error(f"Error summarizing lyrics: {e}", exc_info=True)

    # Fallback summaries
    return (
        f"'{title}' виконавця {artist} розповідає про зв'язок та рішучість. Оповідач балансує між сумнівами та вірністю, "
        f"шукаючи чесність та прийняття. Загалом, тон інтроспективний та щирий."
        if language == "uk" else
        f"'{title}' by {artist} reflects on connection and resolve. The narrator balances doubt with loyalty, "
        f"seeking honesty and acceptance. Overall, the tone is introspective and sincere."
    )

# ---- AI Image generation ----
async def generate_song_artwork_with_progress(artist: str, title: str, summary: str, style: str, tracker: ProgressTracker) -> str:
    """Generate artwork with progress updates."""
    await tracker.update(80, "Creating AI artwork...")
    await asyncio.sleep(0.8)  # Show creation step
    
    await tracker.update(90, "Finalizing image...")
    await asyncio.sleep(0.5)  # Show finalization step
    
    result = await generate_song_artwork(artist, title, summary, style)
    
    await tracker.update(95, "Artwork ready!")
    await asyncio.sleep(0.3)  # Brief pause
    return result

async def generate_song_artwork(artist: str, title: str, summary: str, style: str) -> str:
    # Check cache first using summary content hash + style for unique key
    summary_hash = get_content_hash(summary)
    cache_key = get_cache_key("image", artist, title, summary_hash, style.lower())
    cached_image_url = await get_from_cache(cache_key)
    if cached_image_url:
        return cached_image_url
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not OpenAI or not api_key:
        fallback_svg = make_svg_data_uri(artist, title, style)
        # Cache fallback SVG for 1 hour to avoid regenerating
        await set_cache(cache_key, fallback_svg, 3600)
        return fallback_svg
    try:
        client = OpenAI(api_key=api_key)
        style_descriptions = {
            "album cover": "professional album cover art",
            "cinematic": "cinematic movie poster style",
            "watercolor": "soft watercolor painting",
            "grunge": "gritty grunge aesthetic with distressed textures",
            "minimalist": "clean minimalist design",
            "vintage": "retro vintage poster style",
            "psychedelic": "vibrant psychedelic art",
            "dark": "dark moody atmosphere",
            "bright": "bright colorful design",
            "abstract": "abstract artistic interpretation"
        }
        style_prompt = style_descriptions.get(style.lower(), f"{style} style")
        summary_excerpt = summary[:200] + "..." if len(summary) > 200 else summary
        prompt = (
            f"Create {style_prompt} artwork inspired by the song '{title}' by {artist}. "
            f"Based on the song's meaning: {summary_excerpt} "
            f"The artwork should visually capture the mood, themes, and emotions described. "
            f"Style: {style_prompt}. No text or lyrics in the image. "
            f"High quality, artistic, suitable for music album artwork."
        )
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        # Cache DALL-E image URLs for 30 days (images are expensive to generate)
        await set_cache(cache_key, image_url, 30 * 24 * 3600)
        return image_url
    except Exception as e:
        logger.error(f"Error generating image: {e}", exc_info=True)
        fallback_svg = make_svg_data_uri(artist, title, style)
        # Cache fallback for shorter time when API fails
        await set_cache(cache_key, fallback_svg, 1800)  # 30 minutes
        return fallback_svg

# ---- Fallback SVG generation ----
def make_svg_data_uri(artist: str, title: str, style: str) -> str:
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "&apos;"))
    svg = f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'>
  <defs>
    <linearGradient id='g' x1='0' x2='1'>
      <stop offset='0' stop-color='#1f2937'/>
      <stop offset='1' stop-color='#0ea5e9'/>
    </linearGradient>
  </defs>
  <rect width='100%' height='100%' fill='url(#g)'/>
  <text x='50%' y='50%' fill='#e5e7eb' font-size='46' text-anchor='middle' font-family='Arial,Helvetica,sans-serif'>{esc(artist)} — {esc(title)}</text>
  <text x='50%' y='585' fill='#cbd5e1' font-size='22' text-anchor='middle' font-family='Arial,Helvetica,sans-serif'>AI artwork ({esc(style)}) • {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</text>
</svg>"""
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"
