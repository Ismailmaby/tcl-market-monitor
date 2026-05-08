import urllib.request, urllib.error, datetime, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_PASS"]
RECIPIENT  = os.environ.get("RECIPIENT", GMAIL_USER)

URLS = {
    "HospitalityNet":        "https://www.hospitalitynet.org/rss/news.xml",
    "Hotel Management":      "https://www.hotelmanagement.net/rss.xml",
    "HotelNewsNow":          "https://www.hotelnewsnow.com/rss",
    "Skift Hotels":          "https://skift.com/feed/",
    "Arabian Business":      "https://www.arabianbusiness.com/rss",
    "Hotelier MEA":          "https://www.hotelier-mea.com/feed/",
    "Breaking Travel News":  "https://www.breakingtravelnews.com/feed/",
    "Travel Daily News":     "https://www.traveldailynews.com/feed/",
    "Hospitality Tech":      "https://hospitalitytech.com/rss.xml",
    "AVNetwork":             "https://www.avnetwork.com/rss/all",
    "Digital Signage Today": "https://www.digitalsignagetoday.com/rss/",
    "Hotel News Resource":   "https://www.hotelnewsresource.com/rss.xml",
    "Hosteltur LATAM":       "https://www.hosteltur.com/feed",
    "Panrotas Brazil":       "https://www.panrotas.com.br/rss/",
    "PhocusWire":            "https://www.phocuswire.com/rss",
    "Hotel Tech Report":     "https://www.hoteltechreport.com/feed",
    "Travel Weekly":         "https://www.travelweekly.com/rss",
    "Zawya Hospitality":     "https://www.zawya.com/rss/hospitality.xml",
    "eTurboNews":            "https://www.eturbonews.com/feed/",
    "Business Traveller":    "https://www.businesstraveller.com/feed/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

results = {"ok": [], "fail": []}

print("Testing " + str(len(URLS)) + " URLs...\n")

for name, url in URLS.items():
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            size = len(content)
            # Count items
            item_count = content.decode("utf-8", errors="ignore").count("<item>") + content.decode("utf-8", errors="ignore").count("<entry>")
            status = "OK - " + str(size) + " bytes, " + str(item_count) + " items"
            results["ok"].append((name, url, item_count))
            print("OK   " + name + ": " + str(item_count) + " items")
    except urllib.error.HTTPError as e:
        status = "HTTP " + str(e.code)
        results["fail"].append((name, url, status))
        print("FAIL " + name + ": HTTP " + str(e.code))
    except Exception as e:
        status = str(e)[:50]
        results["fail"].append((name, url, status))
        print("FAIL " + name + ": " + str(e)[:50])

print("\n=== SUMMARY ===")
print("OK:   " + str(len(results["ok"])))
print("FAIL: " + str(len(results["fail"])))

# Send email with results
html = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
    "<body style='font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:20px;'>"
    "<h2 style='color:#0d1b2a;'>RSS Feed Accessibility Test Results</h2>"
    "<p>Tested from GitHub Actions server. " + str(len(results["ok"])) + " accessible, " + str(len(results["fail"])) + " blocked.</p>"
    "<h3 style='color:#27ae60;'>Accessible (" + str(len(results["ok"])) + ")</h3>"
)

for name, url, count in results["ok"]:
    html += (
        "<div style='padding:10px;background:#f0fff4;border-left:4px solid #27ae60;margin-bottom:8px;'>"
        "<strong>" + name + "</strong> — " + str(count) + " articles<br>"
        "<small style='color:#666;'>" + url + "</small>"
        "</div>"
    )

html += "<h3 style='color:#e63946;'>Blocked (" + str(len(results["fail"])) + ")</h3>"
for name, url, status in results["fail"]:
    html += (
        "<div style='padding:10px;background:#fff5f5;border-left:4px solid #e63946;margin-bottom:8px;'>"
        "<strong>" + name + "</strong> — " + status + "<br>"
        "<small style='color:#666;'>" + url + "</small>"
        "</div>"
    )

html += "</body></html>"

msg = MIMEMultipart("mixed")
msg["Subject"] = "RSS Test Results - " + str(len(results["ok"])) + " accessible"
msg["From"] = GMAIL_USER
msg["To"] = RECIPIENT
msg.attach(MIMEText(html, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
    s.login(GMAIL_USER, GMAIL_PASS)
    s.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

print("\nResults emailed to " + RECIPIENT)
