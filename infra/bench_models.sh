#!/usr/bin/env bash
# Times candidate Gemini models on the real VaaniSetu prompt with a sample image.
# Usage (Cloud Shell): bash infra/bench_models.sh [image] [language]
set -uo pipefail
IMG=${1:-frontend/samples/exam-notice.jpg}
LANG_NAME=${2:-Hindi}
PROJECT=${PROJECT:-$(gcloud config get-value project 2>/dev/null)}
TOKEN=$(gcloud auth print-access-token)
TMP=$(mktemp -d)

PROMPT=$(python3 - "$LANG_NAME" <<'PY'
import re, sys
src = open("backend/main.py", encoding="utf-8").read()
prompt = re.search(r'PROMPT = """(.*?)"""', src, re.S).group(1)
print(prompt.replace("{language}", sys.argv[1]))
PY
)

for m in ${MODELS:-gemini-3.8-flash gemini-3.5-flash gemini-3.5-flash-lite gemini-3.1-flash-lite gemini-2.5-flash gemini-2.5-flash-lite}; do
  for think in 0 default; do
    python3 - "$IMG" "$PROMPT" "$think" > "$TMP/req.json" <<'PY'
import base64, json, sys
img, prompt, think = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = {"temperature": 0.2, "maxOutputTokens": 4096, "responseMimeType": "application/json"}
if think == "0":
    cfg["thinkingConfig"] = {"thinkingBudget": 0}
print(json.dumps({"contents": [{"role": "user", "parts": [
    {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(open(img, "rb").read()).decode()}},
    {"text": prompt}]}], "generationConfig": cfg}))
PY
    start=$(date +%s.%N)
    curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/google/models/$m:generateContent" \
      -d @"$TMP/req.json" > "$TMP/out.json"
    secs=$(python3 -c "import time; print(round(time.time() - $start, 1))")
    python3 - "$m" "$think" "$secs" "$TMP/out.json" <<'PY'
import json, sys
m, think, secs, path = sys.argv[1:]
r = json.load(open(path))
if "error" in r:
    print(f"{m:24} think={think:7} ERROR {r['error'].get('message', '')[:70]}")
else:
    u = r.get("usageMetadata", {})
    text = r["candidates"][0]["content"]["parts"][-1].get("text", "")
    try:
        ok = bool(json.loads(text).get("spoken_summary"))
    except Exception:
        ok = False
    print(f"{m:24} think={think:7} {secs:>5}s  out={u.get('candidatesTokenCount')} "
          f"thoughts={u.get('thoughtsTokenCount', 0)} json_ok={ok}")
PY
  done
done
