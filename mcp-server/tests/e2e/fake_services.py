"""Stand-ins for the two services Speakr calls, for the end-to-end test.

One port serves an ASR endpoint (POST /asr) and an OpenAI-compatible chat
endpoint, so the test needs no GPU, API key or model download. Standard
library only: it runs in a bare Python image.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEGMENTS = [
    {"start": 0.0, "end": 1.0, "text": "Bom dia, vamos começar a reunião.", "speaker": "SPEAKER_00"},
    {"start": 1.0, "end": 2.0, "text": "Certo, o orçamento foi aprovado.", "speaker": "SPEAKER_01"},
]
ANSWER = "Resposta do modelo de teste."


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": "test-model", "object": "model"}]})
        if path == "/health":
            return self._send(200, {"status": "ok"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        path = self.path.split("?")[0].rstrip("/")
        if path == "/asr":
            text = " ".join(segment["text"] for segment in SEGMENTS)
            return self._send(200, {"text": text, "language": "pt", "segments": SEGMENTS})
        if path.endswith("/chat/completions"):
            return self._chat(json.loads(body or b"{}"))
        return self._send(404, {"error": "not found"})

    def _chat(self, request):
        content = "{}" if request.get("response_format") else ANSWER
        if request.get("stream"):
            chunk = {"id": "c1", "object": "chat.completion.chunk", "created": int(time.time()), "model": "test-model",
                     "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
            end = dict(chunk, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
            stream = f"data: {json.dumps(chunk)}\n\ndata: {json.dumps(end)}\n\ndata: [DONE]\n\n".encode()
            return self._send(200, stream, "text/event-stream")
        return self._send(200, {
            "id": "c1", "object": "chat.completion", "created": int(time.time()), "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
