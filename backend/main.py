"""
VaaniSetu - Serverless AI Document Reader
Cloud Run function (Python 3.12) behind Google Cloud API Gateway.

Routes
  POST /upload-url   -> returns a V4 signed Cloud Storage PUT URL for the document photo
  POST /process      -> Cloud Vision text check -> Vertex AI Gemini understanding
                        -> Cloud Text-to-Speech -> Cloud Storage audio -> Firestore record
  GET  /history      -> latest processed documents from Firestore
"""
import datetime
import json
import os
import re
import time
import uuid

import functions_framework
import google.auth
from google.auth.transport import requests as google_requests
from google.cloud import firestore, storage, texttospeech, vision
from google import genai
from google.genai import types

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or google.auth.default()[1]
BUCKET = os.environ["MEDIA_BUCKET"]
COLLECTION = os.environ.get("COLLECTION", "documents")
MODEL_ID = os.environ.get("MODEL_ID", "gemini-2.5-flash")
MODEL_LOCATION = os.environ.get("MODEL_LOCATION", "global")

credentials, _ = google.auth.default()
gcs = storage.Client()
bucket = gcs.bucket(BUCKET)
vision_client = vision.ImageAnnotatorClient()
tts = texttospeech.TextToSpeechClient()
db = firestore.Client()
gemini = genai.Client(vertexai=True, project=PROJECT, location=MODEL_LOCATION)

# Output languages -> Cloud Text-to-Speech voice
LANGUAGES = {
    "en": {"name": "English", "voice": "en-IN-Neural2-A", "code": "en-IN"},
    "hi": {"name": "Hindi", "voice": "hi-IN-Neural2-A", "code": "hi-IN"},
    "es": {"name": "Spanish", "voice": "es-ES-Neural2-A", "code": "es-ES"},
    "fr": {"name": "French", "voice": "fr-FR-Neural2-A", "code": "fr-FR"},
    "de": {"name": "German", "voice": "de-DE-Neural2-B", "code": "de-DE"},
    "ja": {"name": "Japanese", "voice": "ja-JP-Neural2-B", "code": "ja-JP"},
    "ar": {"name": "Arabic", "voice": "ar-XA-Wavenet-A", "code": "ar-XA"},
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def respond(status, body):
    return (json.dumps(body, default=str), status, {"Content-Type": "application/json", **CORS})


@functions_framework.http
def api(request):
    if request.method == "OPTIONS":
        return ("", 204, CORS)
    path = request.path
    try:
        body = (request.get_json(silent=True) or {}) if request.method == "POST" else {}
        if path.endswith("/upload-url") and request.method == "POST":
            return create_upload_url(body)
        if path.endswith("/process") and request.method == "POST":
            return process_document(body)
        if path.endswith("/history") and request.method == "GET":
            return get_history()
        return respond(404, {"error": "Route not found"})
    except ValueError as e:
        return respond(400, {"error": str(e)})
    except Exception as e:  # logged to Cloud Logging
        print("ERROR", repr(e))
        return respond(500, {"error": "Processing failed. Please try again."})


# ---------------------------------------------------------------- signed URLs
def signed_url(key, method, minutes, content_type=None):
    """V4 signed URL. Cloud Run has no private key, so signing goes through the
    IAM Credentials signBlob API using the function's own service account."""
    if not credentials.valid:
        credentials.refresh(google_requests.Request())
    return bucket.blob(key).generate_signed_url(
        version="v4", method=method, expiration=datetime.timedelta(minutes=minutes),
        content_type=content_type, service_account_email=credentials.service_account_email,
        access_token=credentials.token,
    )


def create_upload_url(body):
    content_type = body.get("contentType", "image/jpeg")
    if content_type not in ("image/jpeg", "image/png"):
        raise ValueError("Only JPEG or PNG photos are supported")
    doc_id = uuid.uuid4().hex[:12]
    ext = "png" if content_type == "image/png" else "jpg"
    key = f"uploads/{doc_id}.{ext}"
    return respond(200, {"docId": doc_id, "key": key,
                         "uploadUrl": signed_url(key, "PUT", 5, content_type)})


# ---------------------------------------------------------------- pipeline
def process_document(body):
    key = body.get("key", "")
    lang = body.get("language", "en")
    if not re.fullmatch(r"uploads/[0-9a-f]{12}\.(jpg|png)", key):
        raise ValueError("Invalid document key")
    if lang not in LANGUAGES:
        raise ValueError("Unsupported language")
    doc_id = key.split("/")[1].split(".")[0]
    timings = {}

    blob = bucket.blob(key)
    image_bytes = blob.download_as_bytes()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image is larger than 5 MB")

    # 1. Cloud Vision - verify the photo actually contains readable text
    t = time.time()
    result = vision_client.document_text_detection(
        image=vision.Image(source=vision.ImageSource(gcs_image_uri=f"gs://{BUCKET}/{key}")))
    if result.error.message:
        raise RuntimeError(result.error.message)
    text = result.full_text_annotation.text or ""
    lines = [l for l in text.split("\n") if l.strip()]
    blocks = [b for p in result.full_text_annotation.pages for b in p.blocks]
    timings["vision"] = round(time.time() - t, 2)
    if len(lines) < 2:
        raise ValueError("No readable text found. Please upload a clearer photo of a document.")
    ocr_confidence = round(100 * sum(b.confidence for b in blocks) / max(len(blocks), 1), 1)

    # 2. Vertex AI (Gemini) - read, understand, simplify and translate
    t = time.time()
    analysis = analyse_with_gemini(image_bytes, "image/png" if key.endswith("png") else "image/jpeg", lang)
    timings["gemini"] = round(time.time() - t, 2)

    # 3. Cloud Text-to-Speech - convert the simplified explanation into speech
    t = time.time()
    audio = synthesize(analysis["spoken_summary"][:2900], lang)
    audio_key = f"audio/{doc_id}-{lang}.mp3"
    bucket.blob(audio_key).upload_from_string(audio, content_type="audio/mpeg")
    timings["tts"] = round(time.time() - t, 2)

    # 4. Firestore - persist the result
    record = {
        "createdAt": int(time.time() * 1000),
        "docId": doc_id,
        "imageKey": key,
        "audioKey": audio_key,
        "language": lang,
        "documentType": analysis["document_type"],
        "title": analysis["title"],
        "sourceLanguage": analysis["source_language"],
        "extractedText": analysis["extracted_text"],
        "summary": analysis["spoken_summary"],
        "keyPoints": analysis["key_points"],
        "actionItems": analysis["action_items"],
        "ocrLines": len(lines),
        "ocrConfidence": ocr_confidence,
        "timings": timings,
    }
    db.collection(COLLECTION).document(f"{doc_id}-{lang}").set(record)
    return respond(200, with_urls(record))


PROMPT = """You are VaaniSetu, an assistant that helps visually impaired and low-literacy people understand documents.
Look at the photographed document and reply with ONLY a JSON object with these keys:
"document_type": short category in English (e.g. "Medical Prescription", "Electricity Bill", "Government Notice", "Bank Letter", "Exam Timetable", "Form", "Other"),
"title": a short title for the document in English (max 8 words),
"source_language": the language the document is written in (English name),
"extracted_text": the full text of the document, transcribed faithfully, preserving line breaks,
"spoken_summary": a warm, simple explanation of what the document says and what the reader must do, written in {language} for being READ ALOUD (plain sentences, no bullet symbols, no markdown, under 900 characters; say amounts and dates naturally, and read phone or ID numbers digit by digit),
"key_points": array of 3-5 short key facts in {language}, written with normal digits (e.g. 2,170.50, 10 October 2026),
"action_items": array of 0-3 things the reader must do (with deadlines if any) in {language}, written with normal digits.
Never invent information that is not in the document."""


def analyse_with_gemini(image_bytes, mime, lang):
    contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime),
                PROMPT.replace("{language}", LANGUAGES[lang]["name"])]
    base = dict(temperature=0.2, max_output_tokens=4096, response_mime_type="application/json")
    try:
        # Thinking off: transcription and summarising need no long reasoning, and
        # thinking tokens add latency and are billed as output tokens.
        response = gemini.models.generate_content(
            model=MODEL_ID, contents=contents,
            config=types.GenerateContentConfig(
                **base, thinking_config=types.ThinkingConfig(thinking_budget=0)))
    except Exception as e:  # model does not allow turning thinking off
        print("Gemini thinking_budget fallback", repr(e))
        response = gemini.models.generate_content(
            model=MODEL_ID, contents=contents, config=types.GenerateContentConfig(**base))
    text = response.text or ""
    match = re.search(r"\{.*\}", text, re.S)
    data = json.loads(match.group(0) if match else text)
    for field in ("document_type", "title", "source_language", "extracted_text", "spoken_summary"):
        data[field] = str(data.get(field) or "")
    data["key_points"] = [str(x) for x in data.get("key_points") or []][:5]
    data["action_items"] = [str(x) for x in data.get("action_items") or []][:3]
    if not data["spoken_summary"]:
        raise ValueError("Could not understand this document")
    return data


def synthesize(text, lang):
    voice = LANGUAGES[lang]
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    try:
        params = texttospeech.VoiceSelectionParams(language_code=voice["code"], name=voice["voice"])
        return tts.synthesize_speech(input=texttospeech.SynthesisInput(text=text),
                                     voice=params, audio_config=audio_config).audio_content
    except Exception as e:  # voice not available: fall back to the language's default voice
        print("TTS voice fallback", voice["voice"], repr(e))
        params = texttospeech.VoiceSelectionParams(language_code=voice["code"])
        return tts.synthesize_speech(input=texttospeech.SynthesisInput(text=text),
                                     voice=params, audio_config=audio_config).audio_content


# ---------------------------------------------------------------- history
def get_history():
    docs = (db.collection(COLLECTION).order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(12).stream())
    return respond(200, {"items": [with_urls(d.to_dict()) for d in docs]})


def with_urls(item):
    item = dict(item)
    item["imageUrl"] = signed_url(item["imageKey"], "GET", 60)
    item["audioUrl"] = signed_url(item["audioKey"], "GET", 60)
    item["languageName"] = LANGUAGES.get(item.get("language"), {}).get("name", "")
    return item
