from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from ytmusicapi import YTMusic

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
        playlist_id = params.get("list", [None])[0]

        if not playlist_id:
            self._send_json({"error": "Playlist ID required"}, 400)
            return

        try:
            yt = get_client()
            playlist = yt.get_playlist(playlist_id)

            tracks = []
            for v in playlist.get("tracks", []):
                video_id = v.get("videoId")
                if not video_id:
                    continue
                artists = v.get("artists") or []
                channel = artists[0]["name"] if artists else ""
                thumbs = v.get("thumbnails") or []
                thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                tracks.append({
                    "id": video_id,
                    "title": v.get("title", ""),
                    "channel": channel,
                    "thumb": thumb,
                })

            if not tracks:
                raise Exception("Playlist kosong atau tidak bisa diakses")

            self._send_json(
                {"title": playlist.get("title", "Playlist YouTube Music"), "tracks": tracks},
                200,
                cache=True,
            )
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _send_json(self, payload, status, cache=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control", "s-maxage=300, stale-while-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
