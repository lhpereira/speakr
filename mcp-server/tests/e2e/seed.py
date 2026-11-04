"""Prepare a fresh Speakr for the end-to-end test. Runs inside the Speakr image.

Creates API tokens directly, because the web route needs a browser session, and
a finished recording with a transcript, so that reading does not wait for the
processing queue. Writes what the test needs to /shared/seed.json.
"""

import json
import secrets
import sys

sys.path.insert(0, "/app")

from src.app import app, db  # noqa: E402
from src.models import APIToken, Recording, User  # noqa: E402
from src.utils.token_auth import hash_token  # noqa: E402

TOKEN_SCOPES = {"full": None, "read_only": ["read"], "upload_only": ["upload"]}

SEGMENTS = [
    {
        "speaker": "SPEAKER_00" if i % 2 == 0 else "SPEAKER_01",
        "sentence": f"Trecho {i} da aula sobre orçamento e ação coletiva.",
        "start_time": float(i * 5),
        "end_time": float(i * 5 + 6),  # overlaps the next segment, as diarized speech does
    }
    for i in range(400)
]


def main():
    with app.app_context():
        user = User.query.filter_by(username="admin").one()
        tokens = {}
        for name, scopes in TOKEN_SCOPES.items():
            value = secrets.token_urlsafe(32)
            db.session.add(APIToken(
                user_id=user.id, token_hash=hash_token(value), name=f"mcp-e2e-{name}",
                scopes=json.dumps(scopes) if scopes else None,
            ))
            tokens[name] = value

        recording = Recording(
            user_id=user.id, title="Aula de orçamento", participants="Dana, Omar", status="COMPLETED",
            transcription=json.dumps(SEGMENTS, ensure_ascii=False), summary="## Resumo\n\nDecisões sobre orçamento.",
            notes="Anotações da aula.", original_filename="aula.mp3", mime_type="audio/mpeg", file_size=1024,
        )
        db.session.add(recording)
        db.session.commit()
        seed = {"tokens": tokens, "recording_id": recording.id, "segments": len(SEGMENTS)}

    with open("/shared/seed.json", "w", encoding="utf-8") as f:
        json.dump(seed, f)


if __name__ == "__main__":
    main()
