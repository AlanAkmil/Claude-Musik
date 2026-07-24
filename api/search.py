from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
from ytmusicapi import YTMusic

# ===== BLACKLIST/WHITELIST ===== (sama persis kayak versi JS sebelumnya, biar filtering-nya konsisten)
BLACKLIST_PATTERNS = [
    r"\bgameplay\b", r"\blet'?s play\b", r"\bplaythrough\b", r"\bwalkthrough\b",
    r"\bspeedrun\b", r"\bno commentary\b", r"\bgaming session\b", r"\bstream highlight\b",
    r"\btwitch (highlight|clip)\b", r"\branked (game|match|gameplay)\b",
    r"\b(fps|moba|pvp|pve) gameplay\b", r"\bbattle royale gameplay\b",
    r"\breacts? to\b", r"\breacting to\b", r"\bunboxing\b",
    r"\b(phone|laptop|gpu|cpu|pc) (review|build)\b",
    r"\bdaily vlog\b", r"\bweekly vlog\b", r"\b#vlog\b",
]

WHITELIST_PATTERNS = [
    r"\bost\b", r"\boriginal soundtrack\b", r"\bsoundtrack\b", r"\bgame (music|ost|bgm|theme)\b",
    r"\bbgm\b", r"\blyrics?\b", r"\bcover\b", r"\bacoustic\b", r"\bpiano\b", r"\borchestral\b",
    r"\bremix\b", r"\bfeat\b", r"\bft\.\b", r"\bprod\.\b", r"\baudio\b",
    r"\bdubbing\b", r"\bdub\b", r"\bsub indo\b", r"\bkaraoke\b",
]

_blacklist_re = [re.compile(p, re.I) for p in BLACKLIST_PATTERNS]
_whitelist_re = [re.compile(p, re.I) for p in WHITELIST_PATTERNS]


def is_music_content(title):
    title = title or ""
    if any(p.search(title) for p in _whitelist_re):
        return True
    if any(p.search(title) for p in _blacklist_re):
        return False
    return True


# Client ytmusicapi di-cache di scope module, biar gak re-init tiap request
# (selama serverless function instance-nya masih "warm")
_yt_client = None


def get_client():
    global _yt_client
    if _yt_client is None:
        _yt_client = YTMusic()
    return _yt_client


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        q = params.get("q", [None])[0]
        max_results = int(params.get("max", ["12"])[0])

        if not q:
            self._send_json({"error": "Query required"}, 400)
            return

        try:
            yt = get_client()
            # search() dengan filter='songs' manggil endpoint internal
            # music.youtube.com/youtubei/v1/search (ini core teknik ytmusicapi)
            results = yt.search(q, filter="songs", limit=max_results * 2)

            tracks = []
            for r in results:
                video_id = r.get("videoId")
                if not video_id:
                    continue
                title = r.get("title", "")
                if not is_music_content(title):
                    continue

                artists = r.get("artists") or []
                channel = artists[0]["name"] if artists else ""

                thumbs = r.get("thumbnails") or []
                thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"

                tracks.append({
                    "id": video_id,
                    "title": title,
                    "channel": channel,
                    "thumb": thumb,
                })
                if len(tracks) >= max_results:
                    break

            self._send_json(tracks, 200, cache=True)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, payload, status, cache=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control", "s-maxage=60, stale-while-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
