"""Generates fictional sample document photos used for demos."""
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

F = "C:/Windows/Fonts/"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "samples"
OUT.mkdir(parents=True, exist_ok=True)


def font(name, size, index=0):
    return ImageFont.truetype(F + name, size, index=index)


def photo(page, name, angle):
    """Place the page on a desk-coloured background, rotate slightly and add blur like a phone photo."""
    random.seed(name)
    w, h = page.size
    bg = Image.new("RGB", (w + 160, h + 160), (92, 74, 58))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 110))
    bg.paste(shadow, (92, 96), shadow)
    bg.paste(page, (80, 80))
    bg = bg.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(92, 74, 58))
    bg = bg.filter(ImageFilter.GaussianBlur(0.6))
    bg.convert("RGB").save(OUT / name, quality=88)


def paper(w, h, tint=(252, 250, 244)):
    return Image.new("RGB", (w, h), tint)


# ---------------------------------------------------------- prescription
p = paper(1100, 1450)
d = ImageDraw.Draw(p)
d.rectangle([0, 0, 1100, 170], fill=(18, 94, 110))
d.text((50, 35), "Sanjeevani Family Clinic", font=font("georgiab.ttf", 50), fill="white")
d.text((52, 105), "Dr. Anjali Deshpande, MBBS, MD (General Medicine)  |  Reg. No. MMC-2011-48213", font=font("arial.ttf", 24), fill=(215, 240, 243))
d.text((50, 200), "14, Lakeview Road, Kothrud, Pune 411038   Ph: 020-2546 7788", font=font("arial.ttf", 24), fill=(60, 60, 60))
d.line([50, 250, 1050, 250], fill=(18, 94, 110), width=3)
y = 280
for label, val in [("Patient:", "Mr. Ramesh Patil"), ("Age / Sex:", "62 yrs / M"), ("Date:", "22 Sep 2026")]:
    d.text((50, y), label, font=font("arialbd.ttf", 28), fill=(40, 40, 40))
    d.text((230, y), val, font=font("Inkfree.ttf", 36), fill=(20, 40, 120))
    y += 55
d.text((50, y + 20), "Diagnosis:", font=font("arialbd.ttf", 28), fill=(40, 40, 40))
d.text((230, y + 14), "Type 2 Diabetes, mild hypertension", font=font("Inkfree.ttf", 36), fill=(20, 40, 120))
d.text((50, y + 100), "Rx", font=font("georgiab.ttf", 64), fill=(18, 94, 110))
meds = [
    "1. Tab. Metformin 500 mg", "      1 tablet twice daily after breakfast & dinner  x 30 days",
    "2. Tab. Amlodipine 5 mg", "      1 tablet every morning  x 30 days",
    "3. Tab. Vitamin D3 60000 IU", "      1 tablet once a week (Sunday)  x 8 weeks",
]
y += 190
for m in meds:
    d.text((70, y), m, font=font("Inkfree.ttf", 34), fill=(20, 40, 120))
    y += 52 if m.startswith(" ") is False else 62
d.text((50, y + 30), "Advice:", font=font("arialbd.ttf", 28), fill=(40, 40, 40))
for i, a in enumerate(["Avoid sugar and fried food. Walk 30 minutes daily.",
                       "Check fasting blood sugar before next visit.",
                       "Follow-up after 4 weeks: 20 Oct 2026"]):
    d.text((70, y + 80 + i * 55), "- " + a, font=font("Inkfree.ttf", 32), fill=(20, 40, 120))
d.text((720, 1330), "Dr. A. Deshpande", font=font("segoesc.ttf", 34), fill=(20, 40, 120))
d.line([700, 1320, 1040, 1320], fill=(80, 80, 80), width=2)
photo(p, "prescription.jpg", -2.2)

# ---------------------------------------------------------- electricity bill (Hindi + English)
b = paper(1100, 1400, (255, 255, 255))
d = ImageDraw.Draw(b)
dev = lambda s: font("Nirmala.ttc", s)
d.rectangle([0, 0, 1100, 150], fill=(234, 88, 12))
d.text((40, 22), "उज्ज्वल विद्युत वितरण निगम", font=dev(48), fill="white")
d.text((42, 95), "Ujjwal Vidyut Vitaran Nigam Ltd.  (Fictional utility - sample bill)", font=font("arial.ttf", 24), fill=(255, 237, 213))
d.text((40, 180), "बिजली बिल / Electricity Bill", font=dev(40), fill=(30, 30, 30))
rows = [
    ("उपभोक्ता का नाम", "सुनीता शर्मा"),
    ("उपभोक्ता क्रमांक", "170024589631"),
    ("बिल माह", "सितंबर 2026"),
    ("पिछली रीडिंग", "4,812 यूनिट"),
    ("वर्तमान रीडिंग", "5,046 यूनिट"),
    ("खपत", "234 यूनिट"),
    ("ऊर्जा शुल्क", "₹ 1,638.00"),
    ("स्थिर शुल्क", "₹ 120.00"),
    ("बकाया राशि", "₹ 412.50"),
]
y = 260
for k, v in rows:
    d.rectangle([40, y, 1060, y + 64], outline=(225, 225, 225))
    d.text((60, y + 10), k, font=dev(32), fill=(70, 70, 70))
    d.text((600, y + 10), v, font=dev(32), fill=(20, 20, 20))
    y += 64
d.rectangle([40, y + 20, 1060, y + 130], fill=(255, 237, 213))
d.text((60, y + 38), "कुल देय राशि:  ₹ 2,170.50", font=dev(44), fill=(154, 52, 18))
y += 170
d.text((40, y), "अंतिम तिथि: 10 अक्टूबर 2026", font=dev(36), fill=(185, 28, 28))
d.text((40, y + 60), "अंतिम तिथि के बाद भुगतान पर ₹ 50 विलंब शुल्क लगेगा।", font=dev(30), fill=(40, 40, 40))
d.text((40, y + 110), "बकाया राशि 15 दिनों में जमा न करने पर बिजली कनेक्शन काटा जा सकता है।", font=dev(30), fill=(40, 40, 40))
d.text((40, y + 180), "ऑनलाइन भुगतान: UPI / नेट बैंकिंग  |  हेल्पलाइन: 1912", font=dev(28), fill=(90, 90, 90))
photo(b, "electricity-bill.jpg", 1.6)

# ---------------------------------------------------------- college notice
n = paper(1100, 1380, (250, 249, 245))
d = ImageDraw.Draw(n)
d.text((550, 60), "NORTHFIELD INSTITUTE OF TECHNOLOGY", font=font("georgiab.ttf", 42), fill=(25, 25, 60), anchor="mm")
d.text((550, 115), "Office of the Controller of Examinations", font=font("georgiai.ttf", 28), fill=(60, 60, 60), anchor="mm")
d.line([60, 160, 1040, 160], fill=(25, 25, 60), width=3)
d.text((60, 190), "Ref: NIT/COE/2026/417", font=font("arial.ttf", 24), fill=(50, 50, 50))
d.text((1040, 190), "Date: 25 September 2026", font=font("arial.ttf", 24), fill=(50, 50, 50), anchor="ra")
d.text((550, 270), "NOTICE", font=font("arialbd.ttf", 40), fill=(25, 25, 60), anchor="mm")
d.text((550, 320), "End-Semester Examination - Semester V (TY B.Tech)", font=font("arialbd.ttf", 28), fill=(25, 25, 60), anchor="mm")
body = [
    "All TY B.Tech students are hereby informed that the End-Semester",
    "Examinations for Semester V will commence from 3 November 2026.",
    "",
    "1. Examination forms must be submitted on the student portal on or",
    "    before 8 October 2026. A late fee of Rs. 500 applies till 12 Oct.",
    "2. Students with attendance below 75% will not be issued hall tickets.",
    "3. Hall tickets can be downloaded from 27 October 2026.",
    "4. Mini-project reports and presentations must be submitted to the",
    "    respective supervisors by 31 October 2026.",
    "5. Carry your college ID card and hall ticket to every examination.",
    "    Mobile phones and smart watches are strictly prohibited.",
]
y = 390
for line in body:
    d.text((70, y), line, font=font("times.ttf" if Path(F + "times.ttf").exists() else "georgia.ttf", 32), fill=(30, 30, 30))
    y += 52
d.text((1040, 1180), "Controller of Examinations", font=font("arialbd.ttf", 26), fill=(30, 30, 30), anchor="ra")
d.text((1040, 1120), "S. K. Kulkarni", font=font("segoesc.ttf", 32), fill=(20, 40, 120), anchor="ra")
d.ellipse([90, 1090, 250, 1250], outline=(60, 80, 160), width=4)
d.text((170, 1170), "NIT\nCOE", font=font("arialbd.ttf", 30), fill=(60, 80, 160), anchor="mm", align="center")
photo(n, "exam-notice.jpg", -1.2)
print("samples written to", OUT)
