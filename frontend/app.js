// VaaniSetu front-end: talks to Amazon API Gateway, uploads directly to Amazon S3
const API = window.VAANI_CONFIG.apiUrl;
const LANGS = [
  ["en", "English"], ["hi", "हिन्दी", "Hindi"], ["es", "Español"], ["fr", "Français"],
  ["de", "Deutsch"], ["ja", "日本語"], ["ar", "العربية"],
];
const $ = (id) => document.getElementById(id);
let selectedLang = localStorage.getItem("vaani-lang") || "hi";
let imageBlob = null;

// ---------- language chips
LANGS.forEach(([code, label]) => {
  const b = document.createElement("button");
  b.type = "button";
  b.setAttribute("role", "radio");
  b.dataset.code = code;
  b.textContent = label;
  b.onclick = () => selectLang(code);
  $("langs").appendChild(b);
});
function selectLang(code) {
  selectedLang = code;
  try { localStorage.setItem("vaani-lang", code); } catch (e) {}
  document.querySelectorAll("#langs button").forEach((b) =>
    b.setAttribute("aria-checked", String(b.dataset.code === code)));
}
selectLang(selectedLang);

// ---------- choosing an image
$("file").addEventListener("change", (e) => e.target.files[0] && useImage(e.target.files[0]));
const drop = $("drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("drag")));
drop.addEventListener("drop", (e) => { e.preventDefault(); e.dataTransfer.files[0] && useImage(e.dataTransfer.files[0]); });
document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", async () => {
  const res = await fetch(b.dataset.sample);
  useImage(await res.blob());
}));

async function useImage(file) {
  hideError();
  if (!/image\/(jpeg|png)/.test(file.type)) return showError("Please choose a JPEG or PNG photo.");
  imageBlob = await downscale(file, 1800);
  $("preview").src = URL.createObjectURL(imageBlob);
  $("preview").hidden = false;
  $("dropText").hidden = true;
  $("go").disabled = false;
}

// Resize large phone photos in the browser so uploads stay small and fast
function downscale(file, maxSide) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      c.toBlob((b) => resolve(b), "image/jpeg", 0.88);
    };
    img.src = URL.createObjectURL(file);
  });
}

// ---------- pipeline
const STEPS = ["upload", "rekognition", "bedrock", "polly", "dynamo"];
function setStep(active) {
  const idx = STEPS.indexOf(active);
  document.querySelectorAll("#pipeline li").forEach((li) => {
    const i = STEPS.indexOf(li.dataset.step);
    li.classList.toggle("done", idx === -1 ? active === "all" : i < idx);
    li.classList.toggle("active", i === idx);
  });
}

$("go").addEventListener("click", async () => {
  if (!imageBlob) return;
  hideError();
  $("go").disabled = true;
  $("result").hidden = true;
  $("empty").hidden = false;
  $("empty").classList.add("busy");
  $("empty").querySelector("p").textContent = "Reading your document…";
  let ticker;
  try {
    setStep("upload");
    const up = await api("/upload-url", { contentType: "image/jpeg" });
    const put = await fetch(up.uploadUrl, { method: "PUT", headers: { "Content-Type": "image/jpeg" }, body: imageBlob });
    if (!put.ok) throw new Error("Upload to S3 failed");

    // The server runs the remaining stages in one call; animate them while we wait.
    setStep("rekognition");
    ticker = [setTimeout(() => setStep("bedrock"), 1200), setTimeout(() => setStep("polly"), 9000)];
    const result = await api("/process", { key: up.key, language: selectedLang });
    ticker.forEach(clearTimeout);
    setStep("all");
    showResult(result, true);
    loadHistory();
  } catch (err) {
    (ticker || []).forEach(clearTimeout);
    setStep("none");
    showError(err.message);
    $("empty").querySelector("p").textContent = "Your explanation will appear and play here.";
  } finally {
    $("go").disabled = false;
    $("empty").classList.remove("busy");
  }
});

async function api(path, body) {
  const res = await fetch(API + path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : {});
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.message || `Request failed (${res.status})`);
  return data;
}

function showResult(r, autoplay) {
  $("empty").hidden = true;
  $("result").hidden = false;
  $("rType").textContent = r.documentType;
  $("rMeta").textContent = `${r.sourceLanguage} → ${r.languageName} · ${new Date(r.createdAt).toLocaleString()}`;
  $("rTitle").textContent = r.title;
  $("rSummary").textContent = r.summary;
  const rtl = r.language === "ar";
  $("rSummary").dir = rtl ? "rtl" : "ltr";
  fillList("rPoints", r.keyPoints);
  fillList("rActions", r.actionItems);
  $("rActionsWrap").hidden = !(r.actionItems || []).length;
  $("rText").textContent = r.extractedText;
  const t = r.timings || {};
  $("rTimings").innerHTML = "";
  [["Rekognition", t.rekognition], ["Bedrock", t.bedrock], ["Polly", t.polly], ["OCR lines", r.ocrLines, ""], ["OCR confidence", r.ocrConfidence, "%"]]
    .forEach(([k, v, unit = "s"]) => {
      if (v === undefined) return;
      const span = document.createElement("span");
      span.textContent = `${k}: ${v}${unit}`;
      $("rTimings").appendChild(span);
    });
  $("rAudio").src = r.audioUrl;
  if (autoplay) $("rAudio").play().catch(() => {});
  $("result").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function fillList(id, items) {
  $(id).innerHTML = "";
  (items || []).forEach((x) => { const li = document.createElement("li"); li.textContent = x; $(id).appendChild(li); });
}

// ---------- history
async function loadHistory() {
  try {
    const { items } = await api("/history");
    const grid = $("historyGrid");
    grid.innerHTML = "";
    if (!items.length) { grid.innerHTML = '<p class="muted">Nothing read yet. Try a sample above.</p>'; return; }
    items.forEach((it) => {
      const card = document.createElement("button");
      card.className = "card";
      card.type = "button";
      card.innerHTML = `<img alt="" loading="lazy"><div><b></b><small></small></div>`;
      card.querySelector("img").src = it.imageUrl;
      card.querySelector("b").textContent = it.title;
      card.querySelector("small").textContent = `${it.documentType} · ${it.languageName} · ${new Date(it.createdAt).toLocaleDateString()}`;
      card.onclick = () => { showResult(it, false); setStep("all"); document.getElementById("read").scrollIntoView({ behavior: "smooth" }); };
      grid.appendChild(card);
    });
  } catch (e) {
    $("historyGrid").innerHTML = '<p class="muted">History unavailable right now.</p>';
  }
}
$("refresh").addEventListener("click", loadHistory);

function showError(msg) { $("error").textContent = msg; $("error").hidden = false; }
function hideError() { $("error").hidden = true; }

loadHistory();
