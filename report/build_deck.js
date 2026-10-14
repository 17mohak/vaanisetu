// Builds the presentation: node report/build_deck.js <output.pptx>
// Requires pptxgenjs, react, react-dom, react-icons and sharp (resolve via NODE_PATH).
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = path.resolve(__dirname, "..");
const SHOT = (f) => path.join(ROOT, "report", "screenshots", f);
const OUT = process.argv[2] || path.join(ROOT, "deliverables", "VaaniSetu_Presentation.pptx");

const C = {
  ink: "1F1A17", ink2: "5B524B", accent: "C2410C", accentSoft: "FBE6D9",
  teal: "0F766E", tealSoft: "D8EFEC", card: "F3F4F6", white: "FFFFFF", line: "E5E7EB",
};
const HEAD = "Cambria";
const BODY = "Calibri";

async function icon(Comp, color, size = 256) {
  const svg = renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

function title(slide, text, sub) {
  slide.addText(text, { x: 0.5, y: 0.35, w: 9, h: 0.6, fontFace: HEAD, fontSize: 30, bold: true,
    color: C.ink, margin: 0, isTextBox: true });
  if (sub) slide.addText(sub, { x: 0.5, y: 0.95, w: 9, h: 0.35, fontFace: BODY, fontSize: 14,
    color: C.ink2, margin: 0, isTextBox: true });
}

function footer(slide, n) {
  slide.addText(`VaaniSetu  ·  CAP 303 Mini-Project  ·  ${n}`, { x: 0.5, y: 5.25, w: 9, h: 0.25,
    fontFace: BODY, fontSize: 9, color: "9CA3AF", align: "right", margin: 0, isTextBox: true });
}

async function iconCircle(slide, Comp, x, y, d, bg, fg) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg } });
  const pad = d * 0.26;
  slide.addImage({ data: await icon(Comp, fg), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
}

function shot(slide, file, x, y, w, ratio = 784 / 1540) {
  slide.addImage({ path: SHOT(file), x, y, w, h: w * ratio,
    shadow: { type: "outer", color: "000000", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "VaaniSetu: AI-Powered Multilingual Document Reader on Google Cloud";
  let n = 0;

  // 1. Title ---------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    s.background = { color: C.ink };
    for (let i = 0; i < 9; i++) {
      const h = [0.35, 0.8, 1.3, 0.9, 1.6, 1.1, 0.6, 1.0, 0.45][i];
      s.addShape("roundRect", { x: 7.3 + i * 0.26, y: 2.1 - h / 2, w: 0.13, h, rectRadius: 0.06,
        fill: { color: i % 2 ? "E26A35" : C.accent }, line: { type: "none" } });
    }
    s.addText("वाणी सेतु  ·  a bridge of voice", { x: 0.6, y: 0.7, w: 6, h: 0.35, fontFace: BODY,
      fontSize: 14, color: "F4A57C", margin: 0, isTextBox: true });
    s.addText("VaaniSetu", { x: 0.6, y: 1.1, w: 6.5, h: 1.0, fontFace: HEAD, fontSize: 54, bold: true,
      color: C.white, margin: 0, isTextBox: true });
    s.addText("A multilingual AI document reader on Google Cloud", { x: 0.6, y: 2.1, w: 6.5, h: 0.5,
      fontFace: BODY, fontSize: 18, color: "E5E7EB", margin: 0, isTextBox: true });
    s.addText("Vertex AI Gemini  ·  Cloud Vision  ·  Text-to-Speech  ·  Cloud Run functions  ·  API Gateway  ·  Cloud Storage  ·  Firestore",
      { x: 0.6, y: 2.65, w: 6.4, h: 0.55, fontFace: BODY, fontSize: 11, color: "9CA3AF", valign: "top", margin: 0, isTextBox: true });
    s.addText([
      { text: "Presented by: ", options: { bold: true, color: C.white } },
      { text: "Mohak Mandwani (App ID: 2406506)", options: { breakLine: true } },
      { text: "Supervisor: ", options: { bold: true, color: C.white } },
      { text: "Dr. Kunal Meher (Assistant Professor)", options: { breakLine: true } },
      { text: "Cloud Application Development (CAP 303)  ·  TY B.Tech Sem V  ·  uGDX School of Technology  ·  AY 2026-27" },
    ], { x: 0.6, y: 3.7, w: 8.8, h: 1.1, fontFace: BODY, fontSize: 12, color: "D1D5DB", margin: 0,
      paraSpaceAfter: 4, isTextBox: true });
    s.addNotes("Introduce yourself and the project. VaaniSetu means 'bridge of voice'. It turns a photo of any document into a spoken explanation in the listener's own language, built entirely on serverless Google Cloud services.");
  }

  // 2. Problem -------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "The problem", "Everyday life runs on paper, but not everyone can read it comfortably");
    const cards = [
      [fa.FaEye, "Low vision & elderly", "Small print on prescriptions and bills is hard to read, and mistakes with doses or due dates have real consequences."],
      [fa.FaBookOpen, "Limited literacy", "Official notices and forms use formal, technical language that is hard to understand even when it can be read."],
      [fa.FaLanguage, "Language barrier", "Migrants and students often receive documents in a language they do not read, such as a Hindi bill for a non-Hindi reader."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      s.addShape("roundRect", { x, y: 1.6, w: 2.85, h: 3.3, rectRadius: 0.12, fill: { color: C.card }, line: { type: "none" } });
      await iconCircle(s, cards[i][0], x + 0.3, 1.9, 0.75, C.accentSoft, C.accent);
      s.addText(cards[i][1], { x: x + 0.3, y: 2.8, w: 2.35, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true,
        color: C.ink, margin: 0, isTextBox: true });
      s.addText(cards[i][2], { x: x + 0.3, y: 3.3, w: 2.35, h: 1.4, fontFace: BODY, fontSize: 13,
        color: C.ink2, margin: 0, valign: "top", isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Three groups struggle with printed documents: people with low vision or the elderly, people with limited literacy, and people facing a language barrier. The cost of misunderstanding is high: a missed bill deadline or a wrong dosage.");
  }

  // 3. Solution ------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Our solution: VaaniSetu", "Photograph a document and hear it explained in your language in about 10 seconds");
    const steps = [
      [fa.FaCamera, "Snap", "Take a photo of a prescription, bill, notice or form"],
      [fa.FaBrain, "Understand", "AI reads it and explains what it means and what to do"],
      [fa.FaVolumeUp, "Listen", "A natural neural voice reads the explanation aloud"],
    ];
    for (let i = 0; i < 3; i++) {
      const y = 1.6 + i * 1.12;
      await iconCircle(s, steps[i][0], 0.5, y, 0.7, i === 1 ? C.teal : C.accent, C.white);
      s.addText(steps[i][1], { x: 1.4, y: y + 0.02, w: 2.8, h: 0.35, fontFace: HEAD, fontSize: 17, bold: true,
        color: C.ink, margin: 0, isTextBox: true });
      s.addText(steps[i][2], { x: 1.4, y: y + 0.36, w: 2.8, h: 0.5, fontFace: BODY, fontSize: 12.5,
        color: C.ink2, margin: 0, valign: "top", isTextBox: true });
    }
    shot(s, "01-home.jpg", 4.55, 1.55, 4.95);
    s.addText("7 output languages  ·  any input language  ·  key points & action items  ·  history",
      { x: 4.55, y: 4.3, w: 4.95, h: 0.3, fontFace: BODY, fontSize: 11, italic: true, color: C.accent,
        margin: 0, align: "center", isTextBox: true });
    footer(s, n);
    s.addNotes("The user experience is three steps: snap, understand, listen. The output includes a plain-language summary, key facts and action items with deadlines. Seven output languages are supported: English, Hindi, Spanish, French, German, Japanese and Arabic.");
  }

  // 4. Architecture ----------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Block diagram");
    s.addImage({ path: path.join(ROOT, "report", "block-diagram.png"), x: 1.3, y: 1.0, w: 7.4, h: 7.4 * 9 / 16 });
    footer(s, n);
    s.addNotes("Everything runs in the Mumbai region, asia-south1, except API Gateway, which is not offered there and runs in Tokyo. The frontend is a static website on Cloud Storage. The browser calls API Gateway, which invokes a single Cloud Run function. The function orchestrates Cloud Vision, Gemini on Vertex AI, Text-to-Speech, Cloud Storage and Firestore. Service accounts restrict permissions and Cloud Logging records every request.");
  }

  // 5. Workflow -----------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "How a request flows", "One photo, five Google Cloud services, about 11 seconds");
    const flow = [
      ["Cloud Storage", "Signed upload", "Browser uploads the photo directly to a private bucket", C.accent],
      ["Cloud Vision", "Text check", "Text detection rejects photos with no readable text", C.teal],
      ["Vertex AI", "Understand", "Gemini transcribes, explains and translates", C.teal],
      ["Text-to-Speech", "Speak", "Neural voice produces an MP3, saved to Cloud Storage", C.teal],
      ["Firestore", "Remember", "Result stored and shown in history", C.accent],
    ];
    for (let i = 0; i < 5; i++) {
      const x = 0.5 + i * 1.84;
      s.addShape("roundRect", { x, y: 1.75, w: 1.64, h: 2.5, rectRadius: 0.1, fill: { color: C.card }, line: { type: "none" } });
      s.addShape("ellipse", { x: x + 0.57, y: 1.95, w: 0.5, h: 0.5, fill: { color: flow[i][3] }, line: { type: "none" } });
      s.addText(String(i + 1), { x: x + 0.57, y: 1.95, w: 0.5, h: 0.5, fontFace: HEAD, fontSize: 16, bold: true,
        color: C.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
      s.addText(flow[i][0], { x: x + 0.1, y: 2.6, w: 1.44, h: 0.35, fontFace: HEAD, fontSize: 14, bold: true,
        color: C.ink, align: "center", margin: 0, isTextBox: true });
      s.addText(flow[i][1], { x: x + 0.1, y: 2.95, w: 1.44, h: 0.3, fontFace: BODY, fontSize: 11, bold: true,
        color: flow[i][3], align: "center", margin: 0, isTextBox: true });
      s.addText(flow[i][2], { x: x + 0.12, y: 3.3, w: 1.4, h: 0.85, fontFace: BODY, fontSize: 10.5,
        color: C.ink2, align: "center", valign: "top", margin: 0, isTextBox: true });
      if (i < 4) s.addShape("rightArrow", { x: x + 1.66, y: 2.9, w: 0.16, h: 0.22, fill: { color: "9CA3AF" }, line: { type: "none" } });
    }
    s.addText("API Gateway → Cloud Run function orchestrates every step  ·  least-privilege service accounts  ·  Cloud Logging",
      { x: 0.5, y: 4.5, w: 9, h: 0.35, fontFace: BODY, fontSize: 12, color: C.ink2, align: "center", margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Walk through a single request. The photo never passes through the API: it goes straight to Cloud Storage with a signed URL. Cloud Vision is a cheap gate, so a blank photo never reaches Gemini. Gemini does the heavy lifting in one multimodal call. Text-to-Speech speaks it, and Firestore stores the record.");
  }

  // 6. Cloud services grid --------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Cloud services used", "8 core Google Cloud services plus IAM and Cloud Logging, all serverless or fully managed");
    const svc = [
      [fa.FaDatabase, "Cloud Storage", "Photos & MP3 audio, private + encrypted"],
      [fa.FaBolt, "Cloud Run", "Python 3.12 function orchestrating the AI pipeline"],
      [fa.FaExchangeAlt, "API Gateway", "OpenAPI routes: /upload-url, /process, /history"],
      [fa.FaBrain, "Vertex AI", "Gemini 3.5 Flash-Lite reads, explains, translates"],
      [fa.FaEye, "Cloud Vision", "Text detection gate before Gemini runs"],
      [fa.FaVolumeUp, "Text-to-Speech", "Neural voices in 7 languages"],
      [fa.FaTable, "Firestore", "Serverless NoSQL history (free tier)"],
      [fa.FaGlobe, "Storage hosting", "HTTPS static website for the web app"],
      [fa.FaShieldAlt, "IAM", "Least-privilege service accounts"],
      [fa.FaChartLine, "Cloud Logging", "Logs & metrics for every request"],
    ];
    for (let i = 0; i < svc.length; i++) {
      const col = i % 5, row = Math.floor(i / 5);
      const x = 0.5 + col * 1.82, y = 1.55 + row * 1.8;
      s.addShape("roundRect", { x, y, w: 1.68, h: 1.62, rectRadius: 0.1,
        fill: { color: row === 1 && col >= 3 ? "F9FAFB" : C.card }, line: { type: "none" } });
      await iconCircle(s, svc[i][0], x + 0.56, y + 0.14, 0.56, i < 8 ? C.accentSoft : C.tealSoft, i < 8 ? C.accent : C.teal);
      s.addText(svc[i][1], { x: x + 0.06, y: y + 0.76, w: 1.56, h: 0.3, fontFace: HEAD, fontSize: 12.5, bold: true,
        color: C.ink, align: "center", margin: 0, isTextBox: true });
      s.addText(svc[i][2], { x: x + 0.1, y: y + 1.06, w: 1.48, h: 0.5, fontFace: BODY, fontSize: 9.5,
        color: C.ink2, align: "center", valign: "top", margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("The rubric asks for at least three cloud services; VaaniSetu uses eight core Google Cloud services plus IAM and Cloud Logging, and no Azure services. Every service is serverless or fully managed, so there is nothing to patch and no idle cost.");
  }

  // 7. Development technologies ----------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Development technologies");
    const left = [
      [fa.FaPython, "Python 3.12 + Google Cloud SDKs", "Cloud Run function calling Storage, Vision, Vertex AI (google-genai), Text-to-Speech and Firestore"],
      [fa.FaHtml5, "HTML5", "Semantic, accessible page structure with a skip link and ARIA roles"],
      [fa.FaCss3Alt, "CSS3", "Responsive grid, design tokens, animated pipeline tracker, reduced-motion support"],
      [fa.FaJs, "JavaScript (ES2020)", "Camera / drag-and-drop upload, Canvas resizing, Fetch API, audio playback"],
    ];
    const right = [
      [fa.FaTerminal, "gcloud CLI + Bash", "One repeatable script, run in Cloud Shell, provisions every resource"],
      [fa.FaGitAlt, "Git + GitHub", "Version control with small, atomic commits"],
      [fa.FaCode, "JSON", "API payloads, structured AI output and the OpenAPI spec"],
    ];
    const row = async (arr, x0, w) => {
      for (let i = 0; i < arr.length; i++) {
        const y = 1.2 + i * 0.95;
        await iconCircle(s, arr[i][0], x0, y, 0.6, C.accentSoft, C.accent);
        s.addText(arr[i][1], { x: x0 + 0.8, y, w, h: 0.3, fontFace: HEAD, fontSize: 15, bold: true, color: C.ink, margin: 0, isTextBox: true });
        s.addText(arr[i][2], { x: x0 + 0.8, y: y + 0.32, w, h: 0.5, fontFace: BODY, fontSize: 11.5, color: C.ink2, margin: 0, valign: "top", isTextBox: true });
      }
    };
    await row(left, 0.5, 3.6);
    s.addShape("roundRect", { x: 5.35, y: 1.1, w: 4.15, h: 3.1, rectRadius: 0.12, fill: { color: C.card }, line: { type: "none" } });
    await row(right, 5.6, 2.9);
    footer(s, n);
    s.addNotes("The backend is Python on a Cloud Run function using Google's client libraries, including google-genai for Gemini. The frontend is plain HTML, CSS and JavaScript with no framework, which keeps it fast. Deployment is automated with the gcloud CLI from Cloud Shell, and the code is on GitHub.");
  }

  // 8-9. Demo slides ----------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Demo: English notice → Hindi speech");
    shot(s, "02-result-hindi-notice.jpg", 0.5, 1.05, 6.3);
    const pts = ["Document type detected: exam notice", "Summary written in Hindi and spoken by a neural Text-to-Speech voice",
      "Key points and action items with deadlines", "All five pipeline stages complete", "Cloud Vision OCR confidence 98%"];
    s.addText(pts.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < pts.length - 1 } })),
      { x: 7.0, y: 1.1, w: 2.5, h: 3.2, fontFace: BODY, fontSize: 12.5, color: C.ink, paraSpaceAfter: 8, valign: "top", margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Live demo: choose the college notice sample, select Hindi and click 'Read it to me'. The tracker lights up Cloud Storage, Cloud Vision, Vertex AI, Text-to-Speech and Firestore, and the Hindi audio plays automatically.");
  }
  {
    const s = pres.addSlide(); n++;
    title(s, "Demo: Hindi bill → English, and history");
    shot(s, "03-result-english-bill.jpg", 0.5, 1.05, 4.4);
    shot(s, "05-history.jpg", 5.1, 1.05, 4.4);
    s.addText("A bill printed in Hindi is explained in English: amount due ₹2,170.50, due date 10 October 2026, late fee ₹50.",
      { x: 0.5, y: 3.5, w: 4.4, h: 0.8, fontFace: BODY, fontSize: 12, color: C.ink2, margin: 0, valign: "top", isTextBox: true });
    s.addText("Every result is saved in Firestore. Tapping a card replays the explanation and audio.",
      { x: 5.1, y: 3.5, w: 4.4, h: 0.8, fontFace: BODY, fontSize: 12, color: C.ink2, margin: 0, valign: "top", isTextBox: true });
    footer(s, n);
    s.addNotes("This shows cross-language understanding: the input is Hindi and the output is English. Cloud Vision reads Devanagari too, with 94% confidence on this bill, and Gemini explains it correctly, including reading the consumer number digit by digit.");
  }

  // 10. Google Cloud console evidence ----------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Deployed on Google Cloud (asia-south1)");
    const g = [["06-cloud-run-function.jpg", "Cloud Run function metrics"], ["07-api-gateway.jpg", "API Gateway: active"],
      ["08-cloud-storage-audio.jpg", "Cloud Storage: MP3 files"], ["09-firestore.jpg", "Firestore record"]];
    for (let i = 0; i < 4; i++) {
      const x = 0.5 + (i % 2) * 4.6, y = 1.05 + Math.floor(i / 2) * 2.1;
      shot(s, g[i][0], x, y, 3.3);
      s.addText(g[i][1], { x: x + 3.4, y: y + 0.6, w: 1.1, h: 0.6, fontFace: BODY, fontSize: 11, bold: true,
        color: C.ink, margin: 0, valign: "middle", isTextBox: true });
    }
    footer(s, n);
    s.addNotes("These are Google Cloud console screenshots of the real deployment: the Cloud Run function's request metrics, the active API Gateway, the MP3 files Text-to-Speech generated in Cloud Storage, and a stored record in Firestore.");
  }

  // 11. Performance numbers --------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Performance at a glance", "Measured per document during testing");
    const stats = [["~1.5 s", "Cloud Vision text check"], ["~3.5 s", "Gemini understanding"], ["~2 s", "Text-to-Speech"], ["~11 s", "Photo to speech, end to end"]];
    for (let i = 0; i < 4; i++) {
      const x = 0.5 + i * 2.3;
      s.addText(stats[i][0], { x, y: 1.7, w: 2.1, h: 0.9, fontFace: HEAD, fontSize: 44, bold: true,
        color: i === 3 ? C.accent : C.ink, margin: 0, isTextBox: true });
      s.addText(stats[i][1], { x, y: 2.6, w: 2.1, h: 0.5, fontFace: BODY, fontSize: 12.5, color: C.ink2, margin: 0, valign: "top", isTextBox: true });
    }
    const more = [["7", "output languages"], ["10", "Google Cloud services"], ["₹0", "cost while idle"]];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      s.addShape("roundRect", { x, y: 3.45, w: 2.85, h: 1.1, rectRadius: 0.1, fill: { color: i === 0 ? C.accentSoft : C.card }, line: { type: "none" } });
      s.addText(more[i][0], { x: x + 0.25, y: 3.55, w: 1.0, h: 0.9, fontFace: HEAD, fontSize: 34, bold: true, color: C.accent, valign: "middle", margin: 0, isTextBox: true });
      s.addText(more[i][1], { x: x + 1.25, y: 3.55, w: 1.5, h: 0.9, fontFace: BODY, fontSize: 14, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Timings come from the function's own measurements, which the app shows under each result. Switching from Gemini 3.8 Flash to 3.5 Flash-Lite with thinking off cut the AI step from about 16 seconds to about 3.5. Because everything is pay-per-use, the app costs nothing when nobody is using it.");
  }

  // 12. Security ----------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Security & cost by design");
    const items = [
      [fa.FaLock, "Private storage", "Public access prevention enforced, encrypted at rest, uploads deleted after 30 days"],
      [fa.FaKey, "Signed URLs", "Browser gets 5-minute upload and 1-hour download links, never Google credentials"],
      [fa.FaUserShield, "Least privilege", "Separate service accounts for function, gateway and builds, each with only the roles it needs"],
      [fa.FaTachometerAlt, "Spend guard", "At most 3 function instances; ₹400 budget alert at 50/90/100%"],
      [fa.FaFilter, "Cost gate", "Cloud Vision blocks non-document photos before any Gemini charge"],
      [fa.FaCloud, "Scales to zero", "No servers to patch; nothing runs and nothing bills while idle"],
    ];
    for (let i = 0; i < 6; i++) {
      const col = i % 2, r = Math.floor(i / 2);
      const x = 0.5 + col * 4.6, y = 1.2 + r * 1.25;
      await iconCircle(s, items[i][0], x, y, 0.62, col ? C.tealSoft : C.accentSoft, col ? C.teal : C.accent);
      s.addText(items[i][1], { x: x + 0.8, y, w: 3.6, h: 0.3, fontFace: HEAD, fontSize: 15, bold: true, color: C.ink, margin: 0, isTextBox: true });
      s.addText(items[i][2], { x: x + 0.8, y: y + 0.32, w: 3.6, h: 0.6, fontFace: BODY, fontSize: 11.5, color: C.ink2, valign: "top", margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Security was a design goal from the start. The browser never holds Google credentials; it only receives short-lived signed URLs. Each component has its own service account with only the roles it needs. The instance cap, the budget alert and the Vision gate protect the budget.");
  }

  // 13. Challenges ----------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Challenges solved");
    const rows = [
      ["The AWS account was suspended mid-project", "Rebuilt on Google Cloud with one re-runnable deploy script; AWS version kept in Git history"],
      ["Gemini 3.8 Flash took 16-24 s per document", "Benchmarked 6 models: 3.5 Flash-Lite with thinking off takes ~3.5 s and costs less"],
      ["API Gateway is not offered in Mumbai", "Gateway runs in Tokyo (asia-northeast1) and routes to the function in Mumbai"],
      ["Cloud Run has no private key to sign URLs", "The function signs Storage URLs via the IAM signBlob API with its own service account"],
    ];
    s.addText("Challenge", { x: 0.5, y: 1.1, w: 4.2, h: 0.35, fontFace: HEAD, fontSize: 14, bold: true, color: C.accent, margin: 0, isTextBox: true });
    s.addText("How it was solved", { x: 5.3, y: 1.1, w: 4.2, h: 0.35, fontFace: HEAD, fontSize: 14, bold: true, color: C.teal, margin: 0, isTextBox: true });
    for (let i = 0; i < rows.length; i++) {
      const y = 1.55 + i * 0.88;
      s.addShape("roundRect", { x: 0.5, y, w: 4.3, h: 0.75, rectRadius: 0.08, fill: { color: C.card }, line: { type: "none" } });
      s.addShape("roundRect", { x: 5.2, y, w: 4.3, h: 0.75, rectRadius: 0.08, fill: { color: C.tealSoft }, line: { type: "none" } });
      s.addShape("rightArrow", { x: 4.88, y: y + 0.26, w: 0.25, h: 0.24, fill: { color: "9CA3AF" }, line: { type: "none" } });
      s.addText(rows[i][0], { x: 0.65, y, w: 4.0, h: 0.75, fontFace: BODY, fontSize: 12, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
      s.addText(rows[i][1], { x: 5.35, y, w: 4.0, h: 0.75, fontFace: BODY, fontSize: 12, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Real-world constraints shaped the design. The AWS account was suspended, so the whole stack was rebuilt on Google Cloud service for service. Benchmarking six Gemini models found a version four times faster and cheaper. Signing URLs without a private key was solved with the IAM signBlob API.");
  }

  // 14. Conclusion ------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    s.background = { color: C.ink };
    s.addText("Conclusion & future scope", { x: 0.5, y: 0.4, w: 9, h: 0.6, fontFace: HEAD, fontSize: 30, bold: true, color: C.white, margin: 0, isTextBox: true });
    const concl = ["A working, deployed serverless app that turns any document photo into spoken guidance",
      "8 core Google Cloud services + IAM and Cloud Logging, integrated end to end",
      "Secure, cheap to run, and deployed with one script"];
    const fut = ["Multi-page PDFs with Pub/Sub and Workflows", "More Indian-language voices and a spoken Q&A mode",
      "Private per-user history with Firebase Authentication", "WhatsApp / IVR channel for feature phones"];
    s.addText("What was achieved", { x: 0.5, y: 1.3, w: 4.3, h: 0.35, fontFace: HEAD, fontSize: 16, bold: true, color: "F4A57C", margin: 0, isTextBox: true });
    s.addText(concl.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < concl.length - 1 } })),
      { x: 0.5, y: 1.75, w: 4.3, h: 2.6, fontFace: BODY, fontSize: 13.5, color: "E5E7EB", paraSpaceAfter: 10, valign: "top", margin: 0, isTextBox: true });
    s.addText("What comes next", { x: 5.3, y: 1.3, w: 4.2, h: 0.35, fontFace: HEAD, fontSize: 16, bold: true, color: "5EEAD4", margin: 0, isTextBox: true });
    s.addText(fut.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < fut.length - 1 } })),
      { x: 5.3, y: 1.75, w: 4.2, h: 2.6, fontFace: BODY, fontSize: 13.5, color: "E5E7EB", paraSpaceAfter: 10, valign: "top", margin: 0, isTextBox: true });
    s.addText("Live: storage.googleapis.com/vaanisetu-web-project-2acd026b-3237-497d-89d/index.html   ·   Code: github.com/17mohak/vaanisetu",
      { x: 0.5, y: 4.75, w: 9, h: 0.35, fontFace: BODY, fontSize: 12, color: "9CA3AF", margin: 0, isTextBox: true });
    s.addNotes("Summarise the achievement and the roadmap, then offer the live URL for anyone who wants to try it.");
  }

  // 15. Thank you -------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    s.background = { color: C.accent };
    s.addText("Thank you", { x: 0.5, y: 1.6, w: 9, h: 1.0, fontFace: HEAD, fontSize: 54, bold: true, color: C.white, align: "center", margin: 0, isTextBox: true });
    s.addText("Questions?  ·  प्रश्न?", { x: 0.5, y: 2.7, w: 9, h: 0.6, fontFace: BODY, fontSize: 22, color: "FDE7D9", align: "center", margin: 0, isTextBox: true });
    s.addNotes("Invite questions. Likely viva topics: why serverless, how signed URLs work, how service-account least privilege works, why Cloud Vision runs before Gemini, why API Gateway is in Tokyo, and what happens if Gemini returns malformed JSON.");
  }

  await pres.writeFile({ fileName: OUT });
  console.log("saved", OUT);
})();
