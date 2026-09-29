"""
VaaniSetu - Serverless AI Document Reader
AWS Lambda backend (Python 3.12) behind Amazon API Gateway (HTTP API).

Routes
  POST /upload-url   -> returns a pre-signed S3 PUT URL for the document photo
  POST /process      -> Rekognition text check -> Bedrock (Amazon Nova) understanding
                        -> Polly speech -> S3 audio -> DynamoDB record
  GET  /history      -> latest processed documents from DynamoDB
"""
import json
import os
import re
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

REGION = os.environ.get("AWS_REGION", "ap-south-1")
BUCKET = os.environ["MEDIA_BUCKET"]
TABLE = os.environ["TABLE_NAME"]
MODEL_ID = os.environ.get("MODEL_ID", "global.amazon.nova-2-lite-v1:0")

s3 = boto3.client("s3", region_name=REGION,
                  config=boto3.session.Config(signature_version="s3v4",
                                              s3={"addressing_style": "virtual"}))
rekognition = boto3.client("rekognition", region_name=REGION)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)
polly = boto3.client("polly", region_name=REGION)
table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

# Output languages -> Amazon Polly neural voice
LANGUAGES = {
    "en": {"name": "English", "voice": "Kajal", "code": "en-IN"},
    "hi": {"name": "Hindi", "voice": "Kajal", "code": "hi-IN"},
    "es": {"name": "Spanish", "voice": "Lucia", "code": "es-ES"},
    "fr": {"name": "French", "voice": "Lea", "code": "fr-FR"},
    "de": {"name": "German", "voice": "Vicki", "code": "de-DE"},
    "ja": {"name": "Japanese", "voice": "Kazuha", "code": "ja-JP"},
    "ar": {"name": "Arabic", "voice": "Hala", "code": "ar-AE"},
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def respond(status, body):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json", **CORS},
            "body": json.dumps(body, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))}


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    if method == "OPTIONS":
        return respond(200, {})
    try:
        body = json.loads(event.get("body") or "{}") if method == "POST" else {}
        if path.endswith("/upload-url") and method == "POST":
            return create_upload_url(body)
        if path.endswith("/process") and method == "POST":
            return process_document(body)
        if path.endswith("/history") and method == "GET":
            return get_history()
        return respond(404, {"error": "Route not found"})
    except ValueError as e:
        return respond(400, {"error": str(e)})
    except Exception as e:  # logged to CloudWatch
        print("ERROR", repr(e))
        return respond(500, {"error": "Processing failed. Please try again."})


# ---------------------------------------------------------------- upload URL
def create_upload_url(body):
    content_type = body.get("contentType", "image/jpeg")
    if content_type not in ("image/jpeg", "image/png"):
        raise ValueError("Only JPEG or PNG photos are supported")
    doc_id = uuid.uuid4().hex[:12]
    ext = "png" if content_type == "image/png" else "jpg"
    key = f"uploads/{doc_id}.{ext}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=300,
    )
    return respond(200, {"docId": doc_id, "key": key, "uploadUrl": url})


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

    obj = s3.get_object(Bucket=BUCKET, Key=key)
    image_bytes = obj["Body"].read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image is larger than 5 MB")

    # 1. Amazon Rekognition - verify the photo actually contains readable text
    t = time.time()
    detected = rekognition.detect_text(Image={"S3Object": {"Bucket": BUCKET, "Name": key}})
    lines = [d for d in detected["TextDetections"] if d["Type"] == "LINE"]
    timings["rekognition"] = round(time.time() - t, 2)
    if len(lines) < 2:
        raise ValueError("No readable text found. Please upload a clearer photo of a document.")
    ocr_confidence = round(sum(l["Confidence"] for l in lines) / len(lines), 1)

    # 2. Amazon Bedrock (Amazon Nova) - read, understand, simplify and translate
    t = time.time()
    analysis = analyse_with_bedrock(image_bytes, "png" if key.endswith("png") else "jpeg", lang)
    timings["bedrock"] = round(time.time() - t, 2)

    # 3. Amazon Polly - convert the simplified explanation into speech
    t = time.time()
    voice = LANGUAGES[lang]
    speech = polly.synthesize_speech(
        Text=analysis["spoken_summary"][:2900], OutputFormat="mp3", Engine="neural",
        VoiceId=voice["voice"], LanguageCode=voice["code"],
    )
    audio_key = f"audio/{doc_id}-{lang}.mp3"
    s3.put_object(Bucket=BUCKET, Key=audio_key, Body=speech["AudioStream"].read(),
                  ContentType="audio/mpeg")
    timings["polly"] = round(time.time() - t, 2)

    # 4. Amazon DynamoDB - persist the result
    record = {
        "pk": "DOC",
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
        "ocrConfidence": Decimal(str(ocr_confidence)),
        "timings": {k: Decimal(str(v)) for k, v in timings.items()},
    }
    table.put_item(Item=record)
    return respond(200, with_urls(record))


PROMPT = """You are VaaniSetu, an assistant that helps visually impaired and low-literacy people understand documents.
Look at the photographed document and reply with ONLY a JSON object (no markdown) with these keys:
"document_type": short category in English (e.g. "Medical Prescription", "Electricity Bill", "Government Notice", "Bank Letter", "Exam Timetable", "Form", "Other"),
"title": a short title for the document in English (max 8 words),
"source_language": the language the document is written in (English name),
"extracted_text": the full text of the document, transcribed faithfully, preserving line breaks,
"spoken_summary": a warm, simple explanation of what the document says and what the reader must do, written in {language} for being READ ALOUD (plain sentences, no bullet symbols, no markdown, under 900 characters; say amounts and dates naturally, and read phone or ID numbers digit by digit),
"key_points": array of 3-5 short key facts in {language}, written with normal digits (e.g. 2,170.50, 10 October 2026),
"action_items": array of 0-3 things the reader must do (with deadlines if any) in {language}, written with normal digits.
Never invent information that is not in the document."""


def analyse_with_bedrock(image_bytes, fmt, lang):
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [
            {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
            {"text": PROMPT.replace("{language}", LANGUAGES[lang]["name"])},
        ]}],
        inferenceConfig={"maxTokens": 3000, "temperature": 0.2},
    )
    text = response["output"]["message"]["content"][0]["text"]
    match = re.search(r"\{.*\}", text, re.S)
    data = json.loads(match.group(0) if match else text)
    for field in ("document_type", "title", "source_language", "extracted_text", "spoken_summary"):
        data[field] = str(data.get(field) or "")
    data["key_points"] = [str(x) for x in data.get("key_points") or []][:5]
    data["action_items"] = [str(x) for x in data.get("action_items") or []][:3]
    if not data["spoken_summary"]:
        raise ValueError("Could not understand this document")
    return data


# ---------------------------------------------------------------- history
def get_history():
    result = table.query(KeyConditionExpression=Key("pk").eq("DOC"),
                         ScanIndexForward=False, Limit=12)
    return respond(200, {"items": [with_urls(i) for i in result["Items"]]})


def with_urls(item):
    item = dict(item)
    for src, dst in (("imageKey", "imageUrl"), ("audioKey", "audioUrl")):
        item[dst] = s3.generate_presigned_url(
            "get_object", Params={"Bucket": BUCKET, "Key": item[src]}, ExpiresIn=3600)
    item["languageName"] = LANGUAGES.get(item.get("language"), {}).get("name", "")
    return item
