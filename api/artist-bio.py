from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import urllib.request


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

        if not name:
            self._send_json({"error": "Artist name required"}, 400)
            return

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            self._send_json({"error": "API key not configured"}, 500)
            return

        try:
            prompt = (
                f'Tulis bio artis musik "{name}" dalam bahasa Indonesia, 3-4 kalimat yang panjang dan natural. '
                "Ceritakan genre musiknya, gaya bermusik, hal unik yang membuat mereka berbeda, dan dampaknya "
                'terhadap pendengar. Kalau artis ini tidak terkenal, buat bio yang masuk akal berdasarkan nama '
                'dan kemungkinan genre musiknya. Jangan tulis "saya tidak tahu" atau "tidak ada info". '
                "Langsung tulis bionya saja tanpa intro atau kata pembuka."
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

            self._send_json({"bio": bio}, 200, cache=True)
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
