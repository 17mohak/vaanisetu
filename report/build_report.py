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
TITLE = ("VaaniSetu: An AI-Powered Multilingual Document Reader using Amazon Bedrock, "
         "Amazon Polly, Amazon Rekognition and AWS Lambda")
OLD_TITLE = "Employee Management System using AWS Elastic Beanstalk and AWS SQL Server"
FONT = "Times New Roman"
APP_URL = "https://main.dubqxztshiysh.amplifyapp.com"
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
        "Build a fully serverless web application on AWS that needs no servers to manage.",
        "Combine at least three cloud services: this project integrates **eight core AWS services** "
        "(S3, Lambda, API Gateway, Rekognition, Bedrock, Polly, DynamoDB, Amplify) plus IAM and "
        "CloudWatch.",
        "Use generative AI (Amazon Nova on Amazon Bedrock) to read and explain documents in seven "
        "languages, and neural text-to-speech (Amazon Polly) to speak the explanation.",
        "Keep the system secure (private storage, pre-signed URLs, least-privilege IAM) and "
        "cost-efficient (pay-per-use, no idle cost).",
    ])
    heading(doc, "1.2", "Key Features", level=2)
    bullets(doc, [
        "**Photo to speech in about 10 seconds**: upload or capture a document photo and hear it explained.",
        "**Seven output languages**: English, Hindi, Spanish, French, German, Japanese and Arabic, each "
        "with a natural Amazon Polly neural voice. The source document can be in any language "
        "(for example, a Hindi bill explained in English).",
        "**Structured understanding**: document type, title, plain-language summary, key points and "
        "action items with deadlines, plus the full transcribed text.",
        "**Smart gatekeeping**: Amazon Rekognition checks that the photo really contains text before "
        "the more expensive AI model is called.",
        "**History**: every processed document is stored in DynamoDB and can be replayed.",
        "**Accessible design**: large type, high contrast, keyboard navigation and a live progress "
        "tracker that shows each AWS service as it runs.",
    ])

    # 2 Block diagram -------------------------------------------------------
    page_break(doc)
    heading(doc, "2.", "Block Diagram")
    para(doc, "Figure 2.1 shows the architecture of VaaniSetu. All components run in the AWS "
              "Asia Pacific (Mumbai) region, ap-south-1.")
    figure(doc, ROOT / "report" / "block-diagram.png", "Figure 2.1: System block diagram of VaaniSetu on AWS")
    heading(doc, "2.1", "Workflow", level=2)
    numbered(doc, [
        "The user opens the web application, which is served over HTTPS by **AWS Amplify Hosting**.",
        "The browser resizes the photo and calls **POST /upload-url** on **Amazon API Gateway**. "
        "**AWS Lambda** returns a short-lived pre-signed URL.",
        "The browser uploads the photo **directly to a private Amazon S3 bucket** using that URL, so "
        "large files never pass through the API.",
        "The browser calls **POST /process**. Lambda asks **Amazon Rekognition** (DetectText) whether "
        "the image contains readable text. Photos without text are rejected at this point.",
        "Lambda sends the image to **Amazon Nova 2 Lite on Amazon Bedrock**, which transcribes the "
        "document and returns JSON: document type, title, a spoken summary in the chosen language, "
        "key points and action items.",
        "**Amazon Polly** converts the summary to speech with a neural voice. The MP3 file is saved to S3.",
        "The result is stored in **Amazon DynamoDB** and returned to the browser with pre-signed "
        "links to the image and audio, and the audio plays automatically.",
        "**AWS IAM** limits the Lambda function to exactly these actions, and **Amazon CloudWatch** "
        "records logs and metrics for every request.",
    ])

    # 3 Technologies --------------------------------------------------------
    page_break(doc)
    heading(doc, "3.", "Technologies Used")
    heading(doc, "3.1", "Development Technologies", level=2)
    table(doc, ["Technology", "Purpose in VaaniSetu"], [
        ["Python 3.12", "Backend business logic running on AWS Lambda (arm64 / Graviton)."],
        ["Boto3 (AWS SDK for Python)", "Calls S3, Rekognition, Bedrock (Converse API), Polly and DynamoDB from Lambda."],
        ["HTML5", "Page structure: upload area, language selector, results, history and "
                  "\"how it works\" sections, with semantic, accessible markup."],
        ["CSS3", "Styling: responsive grid layout, custom design tokens, animated pipeline "
                 "tracker and waveform, mobile layout and reduced-motion support."],
        ["JavaScript (ES2020)", "Dynamic features: drag-and-drop and camera upload, in-browser image "
                                "resizing (Canvas API), Fetch API calls, live pipeline status, audio "
                                "playback and history cards."],
        ["JSON", "Data format between browser, API and AI model, and for IAM policies."],
        ["AWS CLI and Bash", "Infrastructure provisioning and repeatable deployment (infra/deploy.sh)."],
        ["Git and GitHub", "Version control with small, atomic commits."],
    ], widths=[4.5, 10.5])

    heading(doc, "3.2", "Cloud Services (Deployment)", level=2)
    para(doc, "The following AWS services are used. All of them are serverless or fully managed, "
              "so the application has no servers to patch and costs nothing while idle.")
    table(doc, ["AWS Service", "Role in VaaniSetu", "Configuration"], [
        ["Amazon S3", "Stores uploaded document photos (uploads/) and generated speech (audio/).",
         "Private bucket, public access blocked, SSE-S3 encryption, CORS for browser upload, "
         "30-day lifecycle on uploads, pre-signed URLs."],
        ["AWS Lambda", "Serverless backend that runs the whole AI pipeline.",
         "vaanisetu-api, Python 3.12, arm64, 512 MB, 29 s timeout."],
        ["Amazon API Gateway", "Public REST entry point for the web app.",
         "HTTP API with routes POST /upload-url, POST /process, GET /history; CORS; throttling "
         "at 10 req/s (burst 20)."],
        ["Amazon Bedrock", "Generative AI that reads, understands, simplifies and translates the document.",
         "Model: Amazon Nova 2 Lite (multimodal) via the global cross-region inference profile, "
         "Converse API, temperature 0.2."],
        ["Amazon Rekognition", "Computer-vision gate: detects printed text before calling the AI model.",
         "DetectText API reading the image directly from S3; at least 2 text lines required."],
        ["Amazon Polly", "Neural text-to-speech for the explanation.",
         "Neural engine; voices Kajal (English-IN and Hindi), Lucia, Lea, Vicki, Kazuha and Hala; MP3 output."],
        ["Amazon DynamoDB", "Stores the history of processed documents.",
         "Table vaanisetu-documents, on-demand capacity, key pk + createdAt for newest-first queries."],
        ["AWS Amplify Hosting", "Hosts the static frontend over HTTPS with a global CDN.",
         "App vaanisetu, branch main, deployed from a zip by the deploy script."],
        ["AWS IAM", "Security: grants Lambda only the permissions it needs.",
         "Role vaanisetu-lambda-role with a least-privilege inline policy (see Section 4.4)."],
        ["Amazon CloudWatch", "Monitoring: Lambda logs, errors and duration metrics.",
         "Log group /aws/lambda/vaanisetu-api."],
    ], widths=[3.3, 5.6, 6.1], size=10)

    # 4 Code ----------------------------------------------------------------
    page_break(doc)
    heading(doc, "4.", "Code")
    para(doc, "The complete source code is in the project repository (" + REPO_URL + "). It is "
              "organised into backend/ (Lambda), frontend/ (web app), infra/ (deployment script, IAM "
              "policy, sample generator) and report/. The most important parts are shown below.")
    heading(doc, "4.1", "Lambda: request routing", level=2)
    code(doc, excerpt("backend/lambda_function.py", "def lambda_handler", "# ------"),
         "backend/lambda_function.py: lambda_handler")
    heading(doc, "4.2", "Lambda: AI pipeline (Rekognition → Bedrock → Polly → DynamoDB)", level=2)
    code(doc, excerpt("backend/lambda_function.py", "def process_document", "PROMPT = "),
         "backend/lambda_function.py: process_document")
    heading(doc, "4.3", "Lambda: Amazon Bedrock prompt and call", level=2)
    code(doc, excerpt("backend/lambda_function.py", "PROMPT = ", "# ------"),
         "backend/lambda_function.py: prompt and analyse_with_bedrock")
    heading(doc, "4.4", "IAM least-privilege policy", level=2)
    code(doc, (ROOT / "infra/lambda-policy.json").read_text(encoding="utf-8"), "infra/lambda-policy.json")
    heading(doc, "4.5", "Frontend: upload and processing", level=2)
    code(doc, excerpt("frontend/app.js", '$("go").addEventListener', "async function api"),
         "frontend/app.js: direct-to-S3 upload and pipeline call")
    page_break(doc)
    heading(doc, "4.6", "Deployment script (excerpt)", level=2)
    code(doc, excerpt("infra/deploy.sh", 'echo "== API Gateway', 'API_URL='),
         "infra/deploy.sh: creating the HTTP API and wiring it to Lambda")

    # 5 Screenshots ----------------------------------------------------------
    page_break(doc)
    heading(doc, "5.", "Screenshots")
    shots = [
        ("01-home.jpg", "Figure 5.1: VaaniSetu home page (hosted on AWS Amplify)"),
        ("02-result-hindi-notice.jpg", "Figure 5.2: English college notice explained and spoken in Hindi; "
                                        "the pipeline tracker shows every AWS service completed"),
        ("03-result-english-bill.jpg", "Figure 5.3: Hindi electricity bill explained in English, with key "
                                        "points, action items and per-service timings"),
        ("04-history.jpg", "Figure 5.4: History of processed documents loaded from Amazon DynamoDB"),
        ("05-lambda.jpg", "Figure 5.5: AWS Lambda function vaanisetu-api with its API Gateway trigger"),
        ("06-api-gateway.jpg", "Figure 5.6: Amazon API Gateway HTTP API routes"),
        ("07-s3-audio.jpg", "Figure 5.7: Amazon S3 bucket with MP3 files generated by Amazon Polly"),
        ("08-dynamodb.jpg", "Figure 5.8: Amazon DynamoDB table vaanisetu-documents with stored results"),
        ("09-amplify.jpg", "Figure 5.9: AWS Amplify Hosting app with the deployed main branch"),
        ("10-cloudwatch.jpg", "Figure 5.10: Amazon CloudWatch log group for the Lambda function"),
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
              "phone becomes a clear spoken explanation in the user's own language in about ten "
              "seconds. In testing, Amazon Rekognition took about 1 second, Amazon Bedrock (Nova 2 "
              "Lite) about 4 seconds and Amazon Polly about 1.5 to 2 seconds per document.")
    heading(doc, "6.1", "Outcomes", level=2)
    bullets(doc, [
        "A fully serverless application on AWS integrating eight core services plus IAM and CloudWatch.",
        "Documents in one language (for example Hindi) explained and spoken in another (for example English).",
        "Security by design: private S3 buckets, short-lived pre-signed URLs, encryption at rest and a "
        "least-privilege IAM role.",
        "Pay-per-use cost: there are no running servers, so the application costs nothing when idle.",
        "Infrastructure provisioned by a single repeatable script, with source code under version control.",
    ])
    heading(doc, "6.2", "Challenges and Learnings", level=2)
    bullets(doc, [
        "The AWS Free-plan account did not allow Amazon Textract, Translate or Comprehend. The design "
        "was changed to use a multimodal model on Amazon Bedrock, which reads, translates and "
        "summarises in a single call.",
        "Amazon CloudFront required account verification for new accounts, so the frontend was "
        "hosted on AWS Amplify Hosting, which also provides HTTPS and a CDN.",
        "Rekognition's text detection supports Latin script only. It is therefore used as a fast, low-cost "
        "\"is there text?\" gate, while Bedrock performs the multilingual reading.",
        "API Gateway limits requests to 29 seconds, so uploads go directly to S3 and the AI pipeline "
        "was designed to finish in about 10 seconds.",
    ])
    heading(doc, "6.3", "Future Scope", level=2)
    bullets(doc, [
        "Support multi-page PDFs using asynchronous processing with Amazon SQS or AWS Step Functions.",
        "Add more Indian languages as Amazon Polly voices become available, and a voice question-"
        "and-answer mode (\"When is my next dose?\").",
        "User accounts with Amazon Cognito so that each user's history is private.",
        "A WhatsApp or IVR channel so that users without smartphones can send a photo and receive a call back.",
    ])
    para(doc, "Live application: " + APP_URL, size=11, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=2)
    para(doc, "Source code: " + REPO_URL, size=11, align=WD_ALIGN_PARAGRAPH.LEFT)

    doc.save(output)
    print("saved", output)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
