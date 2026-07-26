from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import json
import os
import urllib.request


LANG_NAMES = {
    "id": "Bahasa Indonesia",
    "en": "English",
    "ru": "Russian",
    "fil": "Filipino",
    "ar": "Arabic",
    "ms": "Malay",
    "th": "Thai",
    "pt": "Portuguese",
    "de": "German",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
}


def search_web(query):
    """Cari info soal artis lewat Google Custom Search, buat dijadiin konteks AI.
    Return None kalau key belum di-set atau pencarian gagal (biar fallback jalan)."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    if not api_key or not cx:
        return None
    try:
        params = urlencode({"key": api_key, "cx": cx, "q": query, "num": 5})
        url = f"https://www.googleapis.com/customsearch/v1?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "HidakaMusik/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("items", [])
        if not items:
            return None
        snippets = []
        for item in items[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if title or snippet:
                snippets.append(f"- {title}: {snippet}")
        return "\n".join(snippets) if snippets else None
    except Exception:
        return None


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        name = params.get("name", [None])[0]
        lang = params.get("lang", ["id"])[0]
        lang_name = LANG_NAMES.get(lang, "Bahasa Indonesia")

        if not name:
            self._send_json({"error": "Artist name required"}, 400)
            return

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            self._send_json({"error": "API key not configured"}, 500)
            return

        try:
            # Riset dulu lewat Google Search sebelum nulis bio, biar AI-nya
            # gak cuma ngarang dari training data doang (kalau key belum di-set,
            # ini otomatis di-skip dan fallback ke cara lama)
            search_context = search_web(f"{name} musician artist biography genre")

            if search_context:
                prompt = (
                    f'Here are some real search results about the music artist "{name}":\n\n'
                    f"{search_context}\n\n"
                    f"Based on this information, write an artist bio in {lang_name}, 3-4 long and "
                    "natural sentences. Describe their music genre, musical style, what makes them "
                    "unique, and their impact on listeners. Write only the bio itself, no intro, no "
                    f"mention of 'search results' or sources. Respond entirely in {lang_name}."
                )
            else:
                prompt = (
                    f'Write a music artist bio for "{name}" in {lang_name}, 3-4 long and natural sentences. '
                    "Describe their music genre, musical style, what makes them unique, and their impact on "
                    f"listeners. If this artist isn't well-known, write a plausible bio based on the name and "
                    f'likely genre. Never write "I don\'t know" or "no info available". '
                    "Write only the bio itself, no intro or preamble. Respond entirely in "
                    f"{lang_name}."
                )

            body = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            bio = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not bio:
                raise Exception("Empty response")

            self._send_json({"bio": bio, "grounded": bool(search_context)}, 200, cache=True)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, payload, status, cache=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control", "s-maxage=86400, stale-while-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
