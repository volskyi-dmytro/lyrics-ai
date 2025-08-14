from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import base64, os
from datetime import datetime, timezone
import logging

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.post("/analyze", response_model=SongResponse)
async def analyze(req: SongRequest):
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

# ---- Lyrics fetching with Genius ----
async def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    genius_token = os.getenv("GENIUS_API_TOKEN")
    if not genius_token:
        demo = {
            ("Metallica", "Nothing Else Matters"): "[Demo lyrics - configure GENIUS_API_TOKEN for real lyrics]",
            ("Океан Ельзи", "Без бою"): "[Demo lyrics - configure GENIUS_API_TOKEN for real lyrics]",
        }
        return demo.get((artist, title))
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
                    return lyrics
            lyrics_pattern = r'"lyrics":"([^"]*)"'
            lyrics_match = re.search(lyrics_pattern, html_content)
            if lyrics_match:
                lyrics = lyrics_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                return lyrics.strip()
        return None
    except Exception as e:
        logger.error(f"Error fetching lyrics: {e}", exc_info=True)
        return None

# ---- Summarization ----
async def summarize_lyrics(lyrics: str, artist: str, title: str, language: str = "en") -> str:
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
            return chat.choices[0].message.content.strip()
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
async def generate_song_artwork(artist: str, title: str, summary: str, style: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not OpenAI or not api_key:
        return make_svg_data_uri(artist, title, style)
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
        return response.data[0].url
    except Exception as e:
        logger.error(f"Error generating image: {e}", exc_info=True)
        return make_svg_data_uri(artist, title, style)

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
