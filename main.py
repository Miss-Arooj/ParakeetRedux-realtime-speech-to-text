
import os
import re
import time
import wave
import asyncio
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher

import numpy as np
import moondream as md
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ui import HTML_PAGE


# ============================================================
# CONFIGURATION
# ============================================================

# These settings are loaded from .env (or the process environment).
# Keep .env private and never commit database credentials.
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "").strip()
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "").strip()


HOST = os.getenv("HOST", "127.0.0.1").strip()
PORT = int(os.getenv("PORT", "5005"))

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # PCM16

PARTIAL_INTERVAL = 0.5
MIN_AUDIO_FOR_TRANSCRIPTION = 0.5
SILENCE_TO_FINALIZE = 1.0
MIN_UTTERANCE_LENGTH = 0.4
SPEECH_RMS_THRESHOLD = 0.015
MAX_BUFFER_SIZE = SAMPLE_RATE * SAMPLE_WIDTH * 60

FUZZY_MATCH_THRESHOLD = 0.70
MIN_FUZZY_TERM_LENGTH = 8
MAX_LENGTH_DIFFERENCE_RATIO = 0.30
# Candidates beginning or ending with these words are skipped to reduce
# accidental matches against ordinary conversational context.
BOUNDARY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by",
    "for", "from", "how", "i", "if", "in", "is", "it", "of",
    "on", "or", "so", "that", "the", "this", "to", "was",
    "were", "what", "when", "where", "which", "who", "why", "with",
}
# Audit details are generated internally only; they are not exposed to the
# dashboard or WebSocket clients.
MIN_AUDIT_SCORE = 0.50


# ============================================================
# APPLICATION STATE
# ============================================================

speech_context = None
speech = None
mongo_client = None
vocabulary_collection = None



def utc_now():
    return datetime.now(timezone.utc)


def normalize_term(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def compact_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold(), flags=re.UNICODE)


def serialize_vocabulary(document: dict) -> dict:
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")

    return {
        "id": str(document["_id"]),
        "correct_term": document.get("correct_term", ""),
        "recognized_variations": document.get(
            "recognized_variations", []
        ),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }



# ============================================================
# MONGODB
# ============================================================

async def get_active_vocabulary() -> list:
    """Read current entries so vocabulary edits take effect dynamically."""
    if vocabulary_collection is None:
        return []

    return await vocabulary_collection.find({}).sort(
        "correct_term", ASCENDING
    ).to_list(length=5000)


# ============================================================
# EXPLICIT VARIATION CORRECTION
# ============================================================

def apply_explicit_variations(text: str, documents: list) -> str:
    replacements = []

    for document in documents:
        correct_term = document.get("correct_term", "").strip()

        if not correct_term:
            continue

        for variation in document.get("recognized_variations", []):
            variation = str(variation).strip()

            if not variation:
                continue

            if variation.casefold() == correct_term.casefold():
                continue

            replacements.append((variation, correct_term))

    # Longer phrases first to avoid replacing part of a longer variation.
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    for variation, correct_term in replacements:
        pattern = (
            r"(?<!\w)"
            + r"\s+".join(
                re.escape(word) for word in variation.split()
            )
            + r"(?!\w)"
        )

        text = re.sub(
            pattern,
            lambda _match, replacement=correct_term: replacement,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        )

    return text


# ============================================================
# FUZZY CORRECTION WITH RECOGNIZED VARIATIONS
# ============================================================

def build_fuzzy_vocabulary(vocabulary: list) -> list:
    """Prebuild compact canonical/variation forms for fuzzy comparison."""
    term_data = []

    for item in vocabulary:
        correct_term = str(item.get("correct_term", "")).strip()
        if not correct_term:
            continue

        if len(compact_text(correct_term)) < MIN_FUZZY_TERM_LENGTH:
            continue

        aliases = [correct_term]
        aliases.extend(item.get("recognized_variations", []) or [])
        unique_aliases = {}

        for alias in aliases:
            alias = str(alias).strip()
            alias_compact = compact_text(alias)
            if alias_compact:
                # Keep the compact form as the comparison key.
                unique_aliases[alias_compact] = alias

        if not unique_aliases:
            continue

        term_data.append({
            "correct_term": correct_term,
            "aliases": list(unique_aliases.keys()),
            "max_alias_words": max(
                len(re.findall(r"\w+", alias, flags=re.UNICODE))
                for alias in unique_aliases.values()
            ),
        })

    return term_data


def fuzzy_match_with_audit(text: str, vocabulary: list, threshold=None):
    """Apply fuzzy vocabulary corrections and return internal audit details.

    Audit details are returned to the caller for debugging/testing only. They
    are deliberately not included in dashboard API responses or WebSocket data.
    """
    if threshold is None:
        threshold = FUZZY_MATCH_THRESHOLD

    if not text or not vocabulary:
        return text, []

    term_data = build_fuzzy_vocabulary(vocabulary)
    if not term_data:
        return text, []

    # Keep original offsets so punctuation outside corrected phrases survives.
    tokens = list(re.finditer(
        r"\b[\w]+(?:['’.-][\w]+)*\b",
        text,
        flags=re.UNICODE,
    ))

    candidates = []
    audit = []
    seen_audit = set()

    for start_index in range(len(tokens)):
        for item in term_data:
            max_words = item["max_alias_words"] + 1

            for word_count in range(1, max_words + 1):
                end_index = start_index + word_count - 1
                if end_index >= len(tokens):
                    break

                start = tokens[start_index].start()
                end = tokens[end_index].end()
                phrase = text[start:end]
                phrase_words = re.findall(r"\w+", phrase, flags=re.UNICODE)

                if not phrase_words:
                    continue

                # Avoid matching a phrase whose first or last word is common
                # conversational context, e.g. "is AML Watcher" as a whole.
                if (
                    phrase_words[0].casefold() in BOUNDARY_STOPWORDS
                    or phrase_words[-1].casefold() in BOUNDARY_STOPWORDS
                ):
                    continue

                phrase_compact = compact_text(phrase)
                if not phrase_compact:
                    continue

                canonical_compact = compact_text(item["correct_term"])
                # Preserve exact canonical wording; only normalize its spacing
                # or punctuation when the compact form is identical.
                if phrase_compact == canonical_compact:
                    if phrase != item["correct_term"]:
                        candidates.append({
                            "start": start,
                            "end": end,
                            "score": 1.0,
                            "length": end - start,
                            "replacement": item["correct_term"],
                        })
                    continue

                # Do not fuzzy-match a fragment of a multiword term (for
                # example, "Watcher" alone must not become "AML Watcher").
                canonical_word_count = len(re.findall(
                    r"\w+", item["correct_term"], flags=re.UNICODE
                ))
                if len(phrase_words) < canonical_word_count:
                    continue

                best_score = -1.0
                best_alias = None

                for alias_compact in item["aliases"]:
                    alias_length = len(alias_compact)
                    phrase_length = len(phrase_compact)
                    max_difference = max(
                        1,
                        int(alias_length * MAX_LENGTH_DIFFERENCE_RATIO),
                    )

                    if abs(phrase_length - alias_length) > max_difference:
                        continue

                    score = SequenceMatcher(
                        None, phrase_compact, alias_compact
                    ).ratio()

                    if score > best_score:
                        best_score = score
                        best_alias = alias_compact

                if best_alias is None or best_score < MIN_AUDIT_SCORE:
                    continue

                accepted = best_score >= threshold
                audit_key = (start, end, item["correct_term"], best_alias)

                if audit_key not in seen_audit:
                    seen_audit.add(audit_key)
                    audit.append({
                        "original_phrase": phrase,
                        "correct_term": item["correct_term"],
                        "matched_vocabulary_form": best_alias,
                        "similarity_score": round(best_score, 4),
                        "threshold": threshold,
                        "accepted": accepted,
                    })

                # Canonical spelling is the replacement, even when a variation
                # was the best comparison form.
                if (
                    accepted
                    and phrase_compact != compact_text(item["correct_term"])
                ):
                    candidates.append({
                        "start": start,
                        "end": end,
                        "score": best_score,
                        "length": end - start,
                        "replacement": item["correct_term"],
                    })

    # Prefer the strongest match; on ties, prefer the longer phrase.
    candidates.sort(
        key=lambda candidate: (candidate["score"], candidate["length"]),
        reverse=True,
    )

    selected = []
    occupied = []
    for candidate in candidates:
        overlaps = any(
            candidate["start"] < other_end and candidate["end"] > other_start
            for other_start, other_end in occupied
        )
        if not overlaps:
            selected.append(candidate)
            occupied.append((candidate["start"], candidate["end"]))

    corrected_text = text
    for candidate in sorted(selected, key=lambda candidate: candidate["start"], reverse=True):
        corrected_text = (
            corrected_text[:candidate["start"]]
            + candidate["replacement"]
            + corrected_text[candidate["end"]:]
        )

    return corrected_text, audit


async def correct_custom_vocabulary(text: str) -> str:
    """Correct recognized text using the latest MongoDB dictionary."""
    if not text or vocabulary_collection is None:
        return text

    try:
        documents = await get_active_vocabulary()
    except Exception as exc:
        print(f"Vocabulary lookup failed: {exc}")
        # Keep transcription available during a temporary DB failure.
        return text

    # First apply exact saved variations, then fuzzy-match the remaining text
    # against both canonical terms and recognized variations.
    corrected = apply_explicit_variations(text, documents)
    corrected, _audit = fuzzy_match_with_audit(corrected, documents)

    # Audit scores stay internal and are not returned to the dashboard/client.
    return corrected


# ============================================================
# PARakeet REDUX TRANSCRIPTION
# ============================================================

def run_transcription(pcm_audio: bytes) -> str:
    if speech is None:
        raise RuntimeError("Parakeet Redux model is not loaded")

    if not pcm_audio:
        return ""

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name

        with wave.open(temp_path, "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(pcm_audio)

        result = speech.transcribe(audio=temp_path)

        if isinstance(result, dict):
            recognized_text = result.get("text", "")
        else:
            recognized_text = getattr(result, "text", "")

        return str(recognized_text or "").strip()

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


async def transcribe_audio(
    websocket: WebSocket,
    pcm_audio: bytes,
    result_type: str,
    transcription_number: int,
):
    raw_text = await asyncio.to_thread(run_transcription, pcm_audio)
    corrected_text = await correct_custom_vocabulary(raw_text)

    if corrected_text:
        await websocket.send_json({
            "type": result_type,
            "text": corrected_text,
            "number": transcription_number,
        })


async def transcribe_audio_background(
    websocket: WebSocket,
    pcm_audio: bytes,
    result_type: str,
    transcription_number: int,
):
    """Run a partial transcription without blocking audio-frame reception."""
    try:
        await transcribe_audio(
            websocket,
            pcm_audio,
            result_type,
            transcription_number,
        )
    except Exception as exc:
        # A client may disconnect while inference is running.
        print(f"{result_type.capitalize()} transcription failed: {exc}")


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global speech_context, speech
    global mongo_client, vocabulary_collection

    missing_settings = [
        name
        for name, value in (
            ("MONGODB_URI", MONGODB_URI),
            ("MONGODB_DATABASE", MONGODB_DATABASE),
            ("MONGODB_COLLECTION", MONGODB_COLLECTION),
        )
        if not value
    ]
    if missing_settings:
        raise RuntimeError(
            "Missing MongoDB settings in .env: " + ", ".join(missing_settings)
        )

    print("Connecting to MongoDB...")

    mongo_client = AsyncIOMotorClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000,
        tz_aware=True,
    )

    try:
        await mongo_client.admin.command("ping")

        database = mongo_client[MONGODB_DATABASE]
        vocabulary_collection = database[MONGODB_COLLECTION]

        await vocabulary_collection.create_index(
            [("normalized_term", ASCENDING)],
            unique=True,
            name="unique_normalized_term",
            partialFilterExpression={
                "normalized_term": {"$type": "string"}
            },
        )

        print("MongoDB connected successfully.")

    except Exception:
        mongo_client.close()
        mongo_client = None
        vocabulary_collection = None
        raise

    print("Loading Parakeet Redux model...")

    try:
        speech_context = md.photon(
            "moondream/parakeet-redux",
            device="cpu",
        )
        speech = speech_context.__enter__()
        print("Parakeet Redux model loaded successfully.")

    except Exception:
        if mongo_client is not None:
            mongo_client.close()

        mongo_client = None
        vocabulary_collection = None
        raise

    yield

    print("Shutting down Speech-to-Text...")

    if speech_context is not None:
        try:
            speech_context.__exit__(None, None, None)
        except Exception as exc:
            print(f"Model shutdown warning: {exc}")

    if mongo_client is not None:
        mongo_client.close()


app = FastAPI(
    title="Speech-to-Text Dashboard",
    lifespan=lifespan,
)


# ============================================================
# DASHBOARD AND STATUS API
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(
):
    return HTML_PAGE


@app.get("/api/status")
async def api_status(
):
    database_connected = False
    term_count = 0

    try:
        if mongo_client is not None:
            await mongo_client.admin.command("ping")
            database_connected = True

        if vocabulary_collection is not None:
            term_count = await vocabulary_collection.count_documents({})

    except Exception as exc:
        print(f"Status check failed: {exc}")

    return {
        "api_status": "online",
        "model_status": "loaded" if speech is not None else "not_loaded",
        "database_status": (
            "connected" if database_connected else "disconnected"
        ),
        "vocabulary_count": term_count,
        "websocket_endpoint": "/ws",
    }


# ============================================================
# VOCABULARY CRUD API
# ============================================================

class VocabularyPayload(BaseModel):
    correct_term: str = Field(..., min_length=1, max_length=200)
    recognized_variations: list[str] = Field(default_factory=list)


def prepare_vocabulary_payload(payload: VocabularyPayload) -> dict:
    correct_term = payload.correct_term.strip()

    if not correct_term:
        raise HTTPException(
            status_code=422,
            detail="Correct Term is required.",
        )

    if len(payload.recognized_variations) > 100:
        raise HTTPException(
            status_code=422,
            detail="A maximum of 100 variations is allowed per term.",
        )

    variations = []
    seen = set()

    for item in payload.recognized_variations:
        variation = str(item).strip()

        if not variation:
            continue

        if len(variation) > 200:
            raise HTTPException(
                status_code=422,
                detail="Each variation must be 200 characters or fewer.",
            )

        key = variation.casefold()

        if key == correct_term.casefold() or key in seen:
            continue

        seen.add(key)
        variations.append(variation)

    return {
        "correct_term": correct_term,
        "normalized_term": normalize_term(correct_term),
        "recognized_variations": variations,
        "updated_at": utc_now(),
    }


@app.get("/api/vocabulary")
async def list_vocabulary(
    search: str = Query(default="", max_length=200),
):
    if vocabulary_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = {}

    if search.strip():
        safe_search = re.escape(search.strip())
        query = {
            "$or": [
                {
                    "correct_term": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
                {
                    "recognized_variations": {
                        "$regex": safe_search,
                        "$options": "i",
                    }
                },
            ]
        }

    documents = await vocabulary_collection.find(query).sort(
        "correct_term", ASCENDING
    ).to_list(length=5000)

    return {
        "items": [serialize_vocabulary(item) for item in documents],
        "count": len(documents),
    }


@app.post("/api/vocabulary", status_code=201)
async def create_vocabulary(
    payload: VocabularyPayload,
):
    if vocabulary_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    document = prepare_vocabulary_payload(payload)
    document["created_at"] = utc_now()

    try:
        result = await vocabulary_collection.insert_one(document)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="This Correct Term already exists.",
        )

    saved = await vocabulary_collection.find_one({"_id": result.inserted_id})
    return serialize_vocabulary(saved)




@app.put("/api/vocabulary/{term_id}")
async def update_vocabulary(
    term_id: str,
    payload: VocabularyPayload,
):
    if vocabulary_collection is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    try:
        object_id = ObjectId(term_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid vocabulary ID",
        )

    # Validate and prepare the complete form data.
    document = prepare_vocabulary_payload(payload)

    try:
        saved = await vocabulary_collection.find_one_and_update(
            {"_id": object_id},
            {"$set": document},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Another entry already uses this Correct Term.",
        )

    if saved is None:
        raise HTTPException(
            status_code=404,
            detail="Vocabulary term not found",
        )

    return serialize_vocabulary(saved)


@app.delete("/api/vocabulary/{term_id}")
async def delete_vocabulary(
    term_id: str,
):
    if vocabulary_collection is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        object_id = ObjectId(term_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid vocabulary ID")

    result = await vocabulary_collection.delete_one({"_id": object_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vocabulary term not found")

    return {"success": True, "deleted_id": term_id}


# ============================================================
# EXISTING WEBSOCKET API
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("New speech-to-text session started")

    audio_buffer = bytearray()
    utterance_started_at = None
    last_speech_at = None
    last_partial_at = 0.0
    transcription_number = 0
    partial_task = None

    try:
        await websocket.send_json({
            "type": "status",
            "text": "Connected",
        })

        while True:
            audio_chunk = await websocket.receive_bytes()
            if not audio_chunk:
                continue

            if len(audio_chunk) % SAMPLE_WIDTH:
                print("Ignoring malformed PCM16 audio chunk")
                continue

            now = time.monotonic()
            samples = np.frombuffer(audio_chunk, dtype="<i2")
            if samples.size == 0:
                continue

            samples_float = samples.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples_float * samples_float)))
            is_speech = rms >= SPEECH_RMS_THRESHOLD

            if is_speech:
                if utterance_started_at is None:
                    utterance_started_at = now
                last_speech_at = now
                audio_buffer.extend(audio_chunk)
            elif utterance_started_at is not None:
                # Keep trailing silence so the model can finish the phrase.
                audio_buffer.extend(audio_chunk)

            if utterance_started_at is None:
                continue

            audio_duration = len(audio_buffer) / (
                SAMPLE_RATE * SAMPLE_WIDTH
            )
            silence_duration = (
                now - last_speech_at
                if last_speech_at is not None
                else 0.0
            )

            should_finalize = (
                silence_duration >= SILENCE_TO_FINALIZE
                and audio_duration >= MIN_UTTERANCE_LENGTH
            ) or len(audio_buffer) >= MAX_BUFFER_SIZE

            if should_finalize:
                # Keep message order stable: any in-flight partial finishes
                # before the final transcript is sent.
                if partial_task is not None:
                    await partial_task
                    partial_task = None

                transcription_number += 1
                try:
                    await transcribe_audio(
                        websocket,
                        bytes(audio_buffer),
                        "final",
                        transcription_number,
                    )
                except WebSocketDisconnect:
                    raise
                except Exception as exc:
                    print(f"Final transcription failed: {exc}")
                    await websocket.send_json({
                        "type": "error",
                        "text": "Final transcription failed.",
                    })

                audio_buffer.clear()
                utterance_started_at = None
                last_speech_at = None
                last_partial_at = 0.0
                continue

            # Partial inference runs in the background, so incoming audio
            # continues to be collected while Parakeet processes a snapshot.
            partial_is_available = (
                partial_task is None or partial_task.done()
            )
            if (
                is_speech
                and audio_duration >= MIN_AUDIO_FOR_TRANSCRIPTION
                and now - last_partial_at >= PARTIAL_INTERVAL
                and partial_is_available
            ):
                last_partial_at = now
                partial_task = asyncio.create_task(
                    transcribe_audio_background(
                        websocket,
                        bytes(audio_buffer),
                        "partial",
                        transcription_number + 1,
                    )
                )

    except WebSocketDisconnect:
        print("Speech-to-text client disconnected")
        if partial_task is not None and not partial_task.done():
            partial_task.cancel()
        audio_buffer.clear()

    except Exception as exc:
        print(f"WebSocket error: {exc}")
        if partial_task is not None and not partial_task.done():
            partial_task.cancel()
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )