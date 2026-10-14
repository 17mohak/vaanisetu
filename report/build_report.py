"""Builds the mini-project report on top of the college front-page template.

Usage: python report/build_report.py <front-pages.docx> <output.docx>
The template's cover, certificate and contents pages are kept as they are; only
the project title and the contents list are updated, and the report body is appended.
"""
import copy
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "report" / "screenshots"
TITLE = ("VaaniSetu: An AI-Powered Multilingual Document Reader using Vertex AI Gemini, "
         "Cloud Vision, Cloud Text-to-Speech and Cloud Run")
OLD_TITLE = "Employee Management System using AWS Elastic Beanstalk and AWS SQL Server"
FONT = "Times New Roman"
APP_URL = "https://storage.googleapis.com/vaanisetu-web-project-2acd026b-3237-497d-89d/index.html"
REPO_URL = "https://github.com/17mohak/vaanisetu"
STUDENTS = [("Mohak Mandwani", "2406506")]


# ------------------------------------------------------------------ helpers
def set_run_text(paragraph, text):
    """Replace a paragraph's text but keep the formatting of its first run."""
    runs = paragraph.runs
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def replace_title(doc):
    for p in doc.paragraphs:
        full = p.text
        if OLD_TITLE not in full:
            continue
        if full.strip().startswith("“") and full.strip().endswith("”"):   # cover page line
            set_run_text(p, f"“{TITLE}”")
            continue
        # certificate sentence: title sits in its own bold run(s)
        for r in p.runs:
            if OLD_TITLE in r.text:
                r.text = r.text.replace(OLD_TITLE, TITLE)
        joined = "".join(r.text for r in p.runs)
        if OLD_TITLE in joined:  # title split across runs
            start = joined.index(OLD_TITLE)
            pos = 0
            for r in p.runs:
                end = pos + len(r.text)
                if end > start and pos < start + len(OLD_TITLE):
                    keep_before = r.text[: max(0, start - pos)]
                    keep_after = r.text[max(0, start + len(OLD_TITLE) - pos):]
                    r.text = keep_before + (TITLE if pos <= start < end else "") + keep_after
                pos = end


def set_students(doc):
    """Fill the 'Student NameN / App ID' lines (cover and certificate) and drop unused ones."""
    for p in list(doc.paragraphs):
        m = re.match(r"Student Name(\d)", p.text.strip())
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if idx < len(STUDENTS):
            runs = p.runs
            runs[0].text = STUDENTS[idx][0]
            runs[-1].text = STUDENTS[idx][1]
        else:
            p._p.getparent().remove(p._p)


def tighten_cover(doc):
    """The new title wraps to three lines; drop one of the two blank lines above
    the academic-year line so the cover still fits on one page."""
    paras = doc.paragraphs
    ay = next(i for i, p in enumerate(paras) if p.text.strip().startswith("AY:"))
    if not paras[ay - 1].text.strip() and not paras[ay - 2].text.strip():
        paras[ay - 1]._p.getparent().remove(paras[ay - 1]._p)


def update_contents(doc):
    """Template list: Introduction / Technologies used / Development... / Deployment... / Code /
    Screenshots / Conclusion. Insert 'Block Diagram' and rename the sub-items."""
    items = {p.text.strip(): p for p in doc.paragraphs}
    intro = items["Introduction"]
    block = copy.deepcopy(intro._p)
    intro._p.addnext(block)
    for t in block.iter(qn("w:t")):
        t.text = ""
    block.findall(".//" + qn("w:t"))[0].text = "Block Diagram"
    set_run_text(items["Development Technology used"], "Development Technologies")
    set_run_text(items["Deployment Technology used"], "Cloud Services (Deployment)")


def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def para(doc, text="", size=12, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         space_after=6, line=1.15, color=None):
    p = doc.add_paragraph()
    p.alignment = align
    fmt = p.paragraph_format
    fmt.space_after = Pt(space_after)
    fmt.space_before = Pt(0)
    fmt.line_spacing = line
    if text:
        add_rich(p, text, size=size, bold=bold, italic=italic, color=color)
    return p


def add_rich(p, text, size=12, bold=False, italic=False, color=None):
    """Supports **bold** spans inside text."""
    for i, chunk in enumerate(re.split(r"\*\*", text)):
        if not chunk:
            continue
        r = p.add_run(chunk)
        r.font.name = FONT
        r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
        r.font.size = Pt(size)
        r.bold = bold or (i % 2 == 1)
        r.italic = italic
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
    return p


def heading(doc, number, text, level=1):
    size = 16 if level == 1 else 13
    p = para(doc, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=8 if level == 1 else 4)
    p.paragraph_format.space_before = Pt(6 if level == 1 else 10)
    p.paragraph_format.keep_with_next = True
    add_rich(p, f"{number}  {text}", size=size, bold=True, color="1F3864")
    if level == 1:  # rule under chapter headings
        p_pr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "8"), ("w:space", "4"), ("w:color", "1F3864")):
            bottom.set(qn(k), v)
        bdr.append(bottom)
        p_pr.append(bdr)
    return p


def bullets(doc, items, size=12):
    for it in items:
        p = para(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        add_rich(p, "•  " + it, size=size)


def numbered(doc, items, size=12):
    for n, it in enumerate(items, 1):
        p = para(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=3)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        add_rich(p, f"{n}.  " + it, size=size)


def table(doc, header, rows, widths, size=10.5):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        add_rich(c.paragraphs[0], h, size=size, bold=True, color="FFFFFF")
        shade(c, "1F3864")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            add_rich(cells[i].paragraphs[0], val, size=size)
            if ri % 2:
                shade(cells[i], "EEF2F8")
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    # repeat header row on page breaks
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    tr_pr.append(th)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(doc, path, caption, width_cm=15.0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    cap = para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)
    add_rich(cap, caption, size=10.5, italic=True)


def code(doc, source, title):
    cap = para(doc, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=2)
    cap.paragraph_format.keep_with_next = True
    add_rich(cap, title, size=11, bold=True)
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    cell = t.rows[0].cells[0]
    shade(cell, "F4F4F4")
    cell.width = Cm(15)
    first = True
    for line in source.rstrip("\n").split("\n"):
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(line.replace("\t", "    ") or " ")
        r.font.name = "Consolas"
        r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), "Consolas")
        r.font.size = Pt(8.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def excerpt(path, start_marker, end_marker=None, max_lines=None):
    lines = (ROOT / path).read_text(encoding="utf-8").split("\n")
    s = next(i for i, l in enumerate(lines) if start_marker in l)
    e = len(lines)
    if end_marker:
        e = next(i for i, l in enumerate(lines[s + 1:], s + 1) if end_marker in l)
    chunk = lines[s:e]
    if max_lines:
        chunk = chunk[:max_lines]
    while chunk and not chunk[-1].strip():
        chunk.pop()
    return "\n".join(chunk)


def add_page_number_footer(section):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        r.font.name = FONT
        r.font.size = Pt(10)
        if kind:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), kind)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = text
            r._r.append(it)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), "1")
    section._sectPr.append(pg)
    section.header.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_rich(hp, "VaaniSetu · Cloud Application Development (CAP 303)", size=9, italic=True, color="666666")


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------------ report body
def build(template, output):
    doc = Document(template)
    replace_title(doc)
    set_students(doc)
    tighten_cover(doc)
    update_contents(doc)

    body = doc.add_section(WD_SECTION.NEW_PAGE)
    body.top_margin = Cm(2.2)
    body.bottom_margin = Cm(2.0)
    add_page_number_footer(body)

    # 1 Introduction ------------------------------------------------------
    heading(doc, "1.", "Introduction")
    para(doc, "Everyday life in India runs on paper: doctors' prescriptions, electricity bills, "
              "college notices, bank letters and government forms. Many people cannot read these "
              "documents comfortably: people with low vision, elderly citizens, people with limited "
              "literacy, and migrants who read a different language from the one the document is "
              "printed in. Missing a due date on a bill or misreading a dosage on a prescription has "
              "real consequences.")
    para(doc, "**VaaniSetu** (Hindi for \"bridge of voice\") is a serverless cloud application that "
              "solves this problem. The user simply photographs a document with a phone or uploads an "
              "image. The application reads the document, understands what it means, explains it in "
              "simple words in the language the user chooses, and **speaks the explanation aloud**. It "
              "also lists the key facts and the actions the reader must take, such as paying a bill "
              "before a deadline.")
    heading(doc, "1.1", "Objectives", level=2)
    bullets(doc, [
        "Build a fully serverless web application on Google Cloud Platform (GCP) that needs no "
        "servers to manage.",
        "Combine at least three cloud services: this project integrates **eight core Google Cloud "
        "services** (Cloud Storage, Cloud Run functions, API Gateway, Cloud Vision, Vertex AI, "
        "Cloud Text-to-Speech, Firestore and Cloud Storage website hosting) plus IAM and Cloud Logging.",
        "Use generative AI (Gemini on Vertex AI) to read and explain documents in seven languages, "
        "and neural text-to-speech (Cloud Text-to-Speech) to speak the explanation.",
        "Keep the system secure (private storage, signed URLs, least-privilege service accounts) and "
        "cost-efficient (pay-per-use, scale to zero, no idle cost).",
    ])
    heading(doc, "1.2", "Key Features", level=2)
    bullets(doc, [
        "**Photo to speech in about 11 seconds**: upload or capture a document photo and hear it explained.",
        "**Seven output languages**: English, Hindi, Spanish, French, German, Japanese and Arabic, each "
        "with a natural neural voice. The source document can be in any language "
        "(for example, a Hindi bill explained in English).",
        "**Structured understanding**: document type, title, plain-language summary, key points and "
        "action items with deadlines, plus the full transcribed text.",
        "**Smart gatekeeping**: Cloud Vision checks that the photo really contains text before "
        "the Gemini model is called.",
        "**History**: every processed document is stored in Firestore and can be replayed.",
        "**Accessible design**: large type, high contrast, keyboard navigation and a live progress "
        "tracker that shows each Google Cloud service as it runs.",
    ])

    # 2 Block diagram -------------------------------------------------------
    page_break(doc)
    heading(doc, "2.", "Block Diagram")
    para(doc, "Figure 2.1 shows the architecture of VaaniSetu. All components run in the Google Cloud "
              "Mumbai region (asia-south1), except API Gateway, which is not offered in Mumbai and "
              "runs in the nearest supported region, Tokyo (asia-northeast1).")
    figure(doc, ROOT / "report" / "block-diagram.png",
           "Figure 2.1: System block diagram of VaaniSetu on Google Cloud")
    heading(doc, "2.1", "Workflow", level=2)
    numbered(doc, [
        "The user opens the web application, a static website served over HTTPS from **Cloud Storage**.",
        "The browser resizes the photo and calls **POST /upload-url** on **Google Cloud API Gateway**. "
        "The **Cloud Run function** returns a short-lived V4 signed URL.",
        "The browser uploads the photo **directly to a private Cloud Storage bucket** using that URL, "
        "so large files never pass through the API.",
        "The browser calls **POST /process**. The function asks **Cloud Vision** (text detection) whether "
        "the image contains readable text. Photos without text are rejected at this point.",
        "The function sends the image to **Gemini 3.5 Flash-Lite on Vertex AI**, which transcribes the "
        "document and returns JSON: document type, title, a spoken summary in the chosen language, "
        "key points and action items.",
        "**Cloud Text-to-Speech** converts the summary to speech with a neural voice. The MP3 file is "
        "saved to Cloud Storage.",
        "The result is stored in **Firestore** and returned to the browser with signed links to the "
        "image and audio, and the audio plays automatically.",
        "**IAM service accounts** limit each component to exactly the roles it needs, and **Cloud "
        "Logging** records every request.",
    ])

    # 3 Technologies --------------------------------------------------------
    page_break(doc)
    heading(doc, "3.", "Technologies Used")
    heading(doc, "3.1", "Development Technologies", level=2)
    table(doc, ["Technology", "Purpose in VaaniSetu"], [
        ["Python 3.12", "Backend business logic running as a Cloud Run function (gen2)."],
        ["Google Cloud client libraries", "google-cloud-storage, -vision, -texttospeech and -firestore, "
                                          "plus google-genai for Gemini on Vertex AI."],
        ["Functions Framework", "Exposes the Python handler as an HTTP endpoint on Cloud Run."],
        ["HTML5", "Page structure: upload area, language selector, results, history and "
                  "\"how it works\" sections, with semantic, accessible markup."],
        ["CSS3", "Styling: responsive grid layout, custom design tokens, animated pipeline "
                 "tracker and waveform, mobile layout and reduced-motion support."],
        ["JavaScript (ES2020)", "Dynamic features: drag-and-drop and camera upload, in-browser image "
                                "resizing (Canvas API), Fetch API calls, live pipeline status, audio "
                                "playback and history cards."],
        ["JSON and OpenAPI 2.0", "Data format between browser, API and AI model; API Gateway configuration."],
        ["gcloud CLI and Bash", "Repeatable provisioning and deployment from Cloud Shell (infra/deploy.sh)."],
        ["Git and GitHub", "Version control with small, atomic commits."],
    ], widths=[4.5, 10.5])

    heading(doc, "3.2", "Cloud Services (Deployment)", level=2)
    para(doc, "The following Google Cloud services are used. All of them are serverless or fully "
              "managed, so the application has no servers to patch and costs nothing while idle.")
    table(doc, ["Google Cloud Service", "Role in VaaniSetu", "Configuration"], [
        ["Cloud Storage", "Stores uploaded document photos (uploads/) and generated speech (audio/).",
         "Private bucket in asia-south1, public access prevention enforced, uniform access, CORS for "
         "browser upload, uploads deleted after 30 days, V4 signed URLs."],
        ["Cloud Run functions", "Serverless backend that runs the whole AI pipeline.",
         "vaanisetu-api (gen2), Python 3.12, 512 MB, 60 s timeout, 0 to 3 instances."],
        ["API Gateway", "Public HTTPS entry point for the web app.",
         "OpenAPI config with POST /upload-url, POST /process, GET /history and CORS; gateway in "
         "asia-northeast1; calls the private function with its own service account."],
        ["Vertex AI (Gemini)", "Generative AI that reads, understands, simplifies and translates the document.",
         "Gemini 3.5 Flash-Lite (multimodal), global endpoint, JSON output, temperature 0.2, thinking off."],
        ["Cloud Vision API", "Computer-vision gate: detects printed text before calling Gemini.",
         "Document text detection reading the image directly from Cloud Storage; at least 2 lines required."],
        ["Cloud Text-to-Speech", "Neural text-to-speech for the explanation.",
         "Neural2 / WaveNet voices for en-IN, hi-IN, es-ES, fr-FR, de-DE, ja-JP and ar-XA; MP3 output."],
        ["Firestore", "Stores the history of processed documents.",
         "Native mode, asia-south1, free tier; collection documents ordered by createdAt."],
        ["Cloud Storage website", "Hosts the static frontend over HTTPS.",
         "Separate public-read bucket vaanisetu-web-<project> with index.html as main page."],
        ["IAM", "Security: grants each component only the permissions it needs.",
         "Service accounts vaanisetu-fn, vaanisetu-gateway and vaanisetu-build with least-privilege roles."],
        ["Cloud Logging", "Monitoring: request logs, errors and latency.",
         "Function logs and metrics; budget alert of 400 INR at 50%, 90% and 100%."],
    ], widths=[3.3, 5.6, 6.1], size=10)
    # drop the spacer after this full-page table so it cannot spill onto a blank page
    spacer = doc.paragraphs[-1]._p
    spacer.getparent().remove(spacer)

    # 4 Code ----------------------------------------------------------------
    heading(doc, "4.", "Code").paragraph_format.page_break_before = True
    para(doc, "The complete source code is in the project repository (" + REPO_URL + "). It is "
              "organised into backend/ (Cloud Run function), frontend/ (web app), infra/ (deployment "
              "script, API Gateway config, sample generator) and report/. The most important parts are "
              "shown below.")
    heading(doc, "4.1", "Cloud Run function: request routing", level=2)
    code(doc, excerpt("backend/main.py", "@functions_framework.http", "# ------"),
         "backend/main.py: api")
    heading(doc, "4.2", "AI pipeline (Vision → Gemini → Text-to-Speech → Firestore)", level=2)
    code(doc, excerpt("backend/main.py", "def process_document", "PROMPT = "),
         "backend/main.py: process_document")
    heading(doc, "4.3", "Gemini prompt and Vertex AI call", level=2)
    code(doc, excerpt("backend/main.py", "PROMPT = ", "def synthesize"),
         "backend/main.py: prompt and analyse_with_gemini")
    heading(doc, "4.4", "Signed Cloud Storage URLs", level=2)
    code(doc, excerpt("backend/main.py", "def signed_url", "def create_upload_url"),
         "backend/main.py: signed_url")
    page_break(doc)
    heading(doc, "4.5", "Least-privilege service accounts", level=2)
    code(doc, excerpt("infra/deploy.sh", 'echo "== Service accounts and roles"',
                      "# ------------------------------------------------------------------ Gemini model"),
         "infra/deploy.sh: service accounts and roles")
    heading(doc, "4.6", "API Gateway configuration (OpenAPI)", level=2)
    code(doc, excerpt("infra/openapi.template.yaml", "swagger:", "  /process:"),
         "infra/openapi.template.yaml (excerpt)")
    page_break(doc)
    heading(doc, "4.7", "Frontend: upload and processing", level=2)
    code(doc, excerpt("frontend/app.js", '$("go").addEventListener', "async function api"),
         "frontend/app.js: direct-to-Cloud-Storage upload and pipeline call")

    # 5 Screenshots ----------------------------------------------------------
    page_break(doc)
    heading(doc, "5.", "Screenshots")
    shots = [
        ("01-home.jpg", "Figure 5.1: VaaniSetu home page (hosted on Cloud Storage)"),
        ("02-result-hindi-notice.jpg", "Figure 5.2: English college notice explained and spoken in Hindi; "
                                        "the pipeline tracker shows every Google Cloud service completed"),
        ("03-result-english-bill.jpg", "Figure 5.3: Hindi electricity bill explained in English, with key "
                                        "points, action items and per-service timings"),
        ("04-result-spanish-prescription.jpg", "Figure 5.4: Prescription explained in Spanish with the "
                                                "audio playing"),
        ("05-history.jpg", "Figure 5.5: History of processed documents loaded from Firestore"),
        ("06-cloud-run-function.jpg", "Figure 5.6: Cloud Run function vaanisetu-api with request metrics"),
        ("07-api-gateway.jpg", "Figure 5.7: API Gateway vaanisetu-gateway (active, asia-northeast1)"),
        ("08-cloud-storage-audio.jpg", "Figure 5.8: Cloud Storage bucket with MP3 files generated by "
                                        "Cloud Text-to-Speech"),
        ("09-firestore.jpg", "Figure 5.9: Firestore document with the stored result"),
        ("10-iam-service-accounts.jpg", "Figure 5.10: Least-privilege IAM service accounts"),
        ("11-cloud-logging.jpg", "Figure 5.11: Cloud Logging showing every API request with latency"),
        ("12-budget-alert.jpg", "Figure 5.12: Budget alert of 400 INR (no credits used)"),
    ]
    for i, (f, cap) in enumerate(shots):
        figure(doc, SHOTS / f, cap, width_cm=15.0)
        if i % 2 == 1 and i != len(shots) - 1:
            page_break(doc)

    # 6 Conclusion -----------------------------------------------------------
    page_break(doc)
    heading(doc, "6.", "Conclusion")
    para(doc, "VaaniSetu shows how managed cloud services can be combined into a useful, "
              "socially relevant product with very little infrastructure code. A photo taken on a "
              "phone becomes a clear spoken explanation in the user's own language in about eleven "
              "seconds. In testing, Cloud Vision took about 1.5 seconds, Gemini 3.5 Flash-Lite about "
              "3.5 seconds and Cloud Text-to-Speech about 2 seconds per document.")
    heading(doc, "6.1", "Outcomes", level=2)
    bullets(doc, [
        "A fully serverless application on Google Cloud integrating eight core services plus IAM and "
        "Cloud Logging.",
        "Documents in one language (for example Hindi) explained and spoken in another (for example English).",
        "Security by design: private buckets, short-lived signed URLs, encryption at rest and "
        "least-privilege service accounts.",
        "Zero idle cost: the function scales to zero and there are no servers, so the application "
        "costs nothing when nobody is using it. A budget alert guards against surprises.",
        "Infrastructure provisioned by a single repeatable script, with source code under version control.",
    ])
    heading(doc, "6.2", "Challenges and Learnings", level=2)
    bullets(doc, [
        "The project was first built on AWS, but the AWS account was suspended. Because the "
        "infrastructure was scripted, the whole system was rebuilt on Google Cloud service for "
        "service; the AWS version remains in the Git history.",
        "Gemini 3.8 Flash took 16 to 24 seconds per document. Benchmarking six Gemini models on the "
        "real prompt showed that Gemini 3.5 Flash-Lite with thinking turned off answers in about "
        "3.5 seconds with correct output, and it is also the cheapest.",
        "API Gateway is not offered in Mumbai, so the gateway runs in Tokyo and routes to the "
        "function in Mumbai.",
        "Cloud Run functions have no private key for signing URLs, so the function signs Cloud "
        "Storage URLs through the IAM signBlob API using its own service account.",
    ])
    heading(doc, "6.3", "Future Scope", level=2)
    bullets(doc, [
        "Support multi-page PDFs using asynchronous processing with Pub/Sub and Workflows.",
        "Add more Indian languages (Marathi, Tamil, Bengali and others, which Cloud Text-to-Speech "
        "already supports) and a voice question-and-answer mode (\"When is my next dose?\").",
        "User accounts with Firebase Authentication so that each user's history is private.",
        "A WhatsApp or IVR channel so that users without smartphones can send a photo and receive a call back.",
    ])
    para(doc, "Live application: " + APP_URL, size=11, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=2)
    para(doc, "Source code: " + REPO_URL, size=11, align=WD_ALIGN_PARAGRAPH.LEFT)

    doc.save(output)
    print("saved", output)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
