import os, json, smtplib, datetime, urllib.request, urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
RECIPIENT    = os.environ.get("RECIPIENT", GMAIL_USER)
NEWS_API_KEY = os.environ["NEWS_API_KEY"]
MAX_AGE_DAYS = 2
SEEN_FILE    = "seen_urls.json"

QUERIES = {
    "Brazil - Hotel Development": [
        "Brazil hotel hospitality Marriott Accor Hilton",
        "Brasil hotelaria investimento abertura",
    ],
    "Brazil - AV Display and IPTV": [
        "Brazil hotel IPTV display signage technology",
        "Brasil televisao comercial hotelaria",
    ],
    "LATAM South - Hotel Market": [
        "Colombia Peru Chile Panama hotel hospitality 2026",
        "Latin America hotel chain Marriott Wyndham IHG",
    ],
    "UAE - Hotel Development": [
        "Dubai UAE hotel opening hospitality 2026",
        "Abu Dhabi hotel Marriott Hilton Accor",
    ],
    "UAE - AV Display and IPTV": [
        "UAE Dubai hotel display signage AV technology",
        "UAE hotel IPTV in-room entertainment",
    ],
    "Saudi Arabia - Hotel Development": [
        "Saudi Arabia hotel Vision 2030 hospitality",
        "NEOM Red Sea resort hotel construction",
    ],
    "Saudi Arabia - AV and Display": [
        "Saudi Arabia hotel display AV technology signage",
        "KSA hotel IPTV commercial display",
    ],
    "Turkey - Hotel and AV": [
        "Turkey hotel hospitality Marriott Hilton 2026",
        "Turkey hotel display AV commercial technology",
    ],
    "Hotel Operators MEA Pipeline": [
        "Marriott Hilton Accor IHG Middle East Africa hotel",
        "GCC hotel chain expansion 2026",
    ],
    "Hotel Operators LATAM Pipeline": [
        "Marriott Hilton Accor IHG hotel South America",
        "Wyndham Radisson hotel Latin America opening",
    ],
    "Hospitality TV IPTV and Middleware": [
        "hospitality TV IPTV hotel in-room entertainment",
        "hotel television middleware Nonius Acentic SONIFI",
    ],
    "Commercial Display and Digital Signage": [
        "commercial display digital signage hotel lobby AV",
        "hotel display technology B2B system integrator",
    ],
    "Hotel Construction and Pipeline": [
        "hotel construction pipeline development 2026",
        "JLL hotel supply pipeline hospitality investment",
    ],
    "Competitive Intelligence": [
        "Samsung LYNK LG ProCentric hotel TV hospitality",
        "Philips hospitality TV commercial display hotel",
    ],
    "Industry Events and Reports": [
        "HITEC hospitality technology conference 2026",
        "hotel technology trend report AV display 2026",
    ],
}

POSITIVE_KEYWORDS = [
    "hotel", "hospitality", "resort", "hotelaria", "hoteleiro",
    "hospedagem", "hoteleria", "otel", "iptv", "in-room",
    "display", "signage", "audiovisual", "commercial tv",
    "marriott", "hilton", "accor", "wyndham", "ihg", "radisson",
    "hyatt", "novotel", "ibis", "sheraton", "intercontinental",
    "samsung lynk", "lg procentric", "philips hospitality",
    "nonius", "acentic", "sonifi", "enseo", "guestroom",
    "hotel technology", "hotel tv", "hotel construction",
    "hotel opening", "hotel pipeline", "hotel development",
    "digital signage", "commercial display", "hotel lobby",
    "hitec", "oracle hospitality",
]

NEGATIVE_KEYWORDS = [
    "world cup", "fifa", "nfl", "nba", "celebrity", "time 100",
    "concert", "music festival", "oscar", "grammy",
    "cryptocurrency", "bitcoin", "stock market",
    "crime", "murder", "accident", "weather forecast",
    "election", "senator", "congress",
]

def is_relevant(title, description):
    text = (title + " " + (description or "")).lower()
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        if not any(kw in text for kw in ["hotel", "hospitality", "resort", "hotelaria"]):
            return False
    return any(kw in text for kw in POSITIVE_KEYWORDS)

def load_seen_urls():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=14)
        return {url: ts for url, ts in data.items()
                if datetime.datetime.fromisoformat(ts) > cutoff}
    return {}

def save_seen_urls(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)

def newsapi_search(query, api_key, from_date):
    params = urllib.parse.urlencode({
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key,
    })
    url = "https://newsapi.org/v2/everything?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "TCLMonitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("articles", [])
    except Exception as e:
        print("  [WARN] NewsAPI error: " + str(e))
        return []

def fetch_news(queries, api_key, max_age_days, seen_urls):
    results = {}
    new_seen = {}
    from_date = (datetime.datetime.utcnow() - datetime.timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    for section, query_list in queries.items():
        section_articles = []
        seen_this_section = set()

        for query in query_list:
            articles = newsapi_search(query, api_key, from_date)
            for a in articles:
                url = a.get("url", "")
                if not url or url in seen_urls or url in seen_this_section:
                    continue
                title = a.get("title") or ""
                description = a.get("description") or ""
                if not is_relevant(title, description):
                    continue
                seen_this_section.add(url)
                pub = a.get("publishedAt", "")[:10]
                source = (a.get("source") or {}).get("name", "Unknown")
                section_articles.append({
                    "title":  title,
                    "source": source,
                    "date":   pub,
                    "url":    url,
                    "body":   description,
                })
                new_seen[url] = datetime.datetime.now().isoformat()

        results[section] = section_articles
        print("   " + section + ": " + str(len(section_articles)) + " articles")

    return results, new_seen

def build_markdown(results, run_date):
    total = sum(len(v) for v in results.values())
    lines = [
        "# TCL Hospitality Market Intelligence - Daily Briefing",
        "Date: " + run_date,
        "Total new articles: " + str(total),
        "Markets: UAE, Saudi Arabia, Turkey, Brazil, Colombia, Peru, Panama, Chile",
        "",
        "---",
        "",
    ]
    for section, articles in results.items():
        lines.append("## " + section)
        if not articles:
            lines.append("No new articles today.\n")
        else:
            for a in articles:
                lines.append("### " + a["title"])
                lines.append("Source: " + a["source"] + " | Date: " + a["date"])
                lines.append(a["url"] + "\n")
                if a["body"]:
                    lines.append(a["body"][:600] + "\n")
        lines.append("")
    lines.append("---")
    lines.append("Generated by TCL Market Monitor - " + run_date)
    return "\n".join(lines)

def build_html_email(results, run_date):
    total = sum(len(v) for v in results.values())
    active = sum(1 for v in results.values() if v)
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;padding:20px;background:#eef1f5;font-family:Arial,sans-serif;'>"
        "<div style='max-width:720px;margin:auto;'>"
        "<div style='background:#0d1b2a;padding:28px 32px;border-radius:10px 10px 0 0;'>"
        "<h1 style='color:#fff;margin:0 0 4px;font-size:20px;'>TCL Market Intelligence</h1>"
        "<p style='color:#7eb8f7;margin:0;font-size:13px;'>Hospitality TV and Commercial Display - Daily Briefing</p>"
        "<div style='margin-top:16px;'>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>Date: " + run_date[:10] + "</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + str(total) + " new articles</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>" + str(active) + " active sections</span>"
        "</div></div>"
        "<div style='background:#fff;padding:8px 32px 32px;border:1px solid #dde;border-top:none;border-radius:0 0 10px 10px;'>"
    )
    for section, articles in results.items():
        html += (
            "<div style='padding-top:28px;'>"
            "<h2 style='font-size:15px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;padding-bottom:8px;margin:0 0 16px;'>" + section + "</h2>"
        )
        if not articles:
            html += "<p style='color:#ccc;font-style:italic;font-size:13px;margin:0;'>No new articles today.</p>"
        else:
            for a in articles:
                body = (a["body"][:280] + "...") if len(a["body"]) > 280 else a["body"]
                html += (
                    "<div style='margin-bottom:12px;padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #e63946;'>"
                    "<a href='" + a["url"] + "' style='font-size:14px;font-weight:600;color:#0d1b2a;text-decoration:none;display:block;'>" + a["title"] + "</a>"
                    "<div style='margin-top:6px;'>"
                    "<span style='font-size:11px;color:#e63946;font-weight:700;text-transform:uppercase;'>" + a["source"] + "</span>"
                    "<span style='font-size:11px;color:#999;margin-left:8px;'>" + a["date"] + "</span>"
                    "</div>"
                    + ("<p style='font-size:13px;color:#555;margin:8px 0 0;line-height:1.55;'>" + body + "</p>" if body else "") +
                    "</div>"
                )
        html += "</div>"
    html += (
        "<div style='margin-top:36px;padding-top:20px;border-top:1px solid #eee;text-align:center;'>"
        "<p style='font-size:11px;color:#aaa;line-height:1.8;margin:0;'>"
        "TCL Global Engineering Business Center<br>"
        "Hospitality TV and Commercial Display - Key Account BD<br>"
        "MEA: UAE, Saudi Arabia, Turkey | LATAM: Brazil, Colombia, Peru, Panama, Chile<br><br>"
        "Attach the .md file to NotebookLM for your daily audio briefing"
        "</p></div></div></body></html>"
    )
    return html

def send_email(html_body, markdown_content, run_date):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "TCL Market Intel - " + run_date[:10]
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    attachment = MIMEText(markdown_content, "plain", "utf-8")
    attachment.add_header("Content-Disposition", "attachment",
                          filename="tcl_intel_" + run_date[:10] + ".md")
    msg.attach(attachment)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    print("  Email sent to " + RECIPIENT)

def save_markdown(content, run_date):
    os.makedirs("output", exist_ok=True)
    path = "output/tcl_intel_" + run_date[:10] + ".md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("  Markdown saved: " + path)

def main():
    run_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print("TCL Market Monitor - " + run_date)
    seen_urls = load_seen_urls()
    print("Dedup cache: " + str(len(seen_urls)) + " URLs")
    results, new_seen = fetch_news(QUERIES, NEWS_API_KEY, MAX_AGE_DAYS, seen_urls)
    total = sum(len(v) for v in results.values())
    print("Total new articles: " + str(total))
    seen_urls.update(new_seen)
    save_seen_urls(seen_urls)
    md   = build_markdown(results, run_date)
    html = build_html_email(results, run_date)
    save_markdown(md, run_date)
    send_email(html, md, run_date)
    print("Done. " + str(len(new_seen)) + " new URLs cached.")

if __name__ == "__main__":
    main()
