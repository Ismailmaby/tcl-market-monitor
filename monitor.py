import os, json, smtplib, datetime, time, random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
RECIPIENT    = os.environ.get("RECIPIENT", GMAIL_USER)
MAX_RESULTS  = 6
MAX_AGE_DAYS = 2
SEEN_FILE    = "seen_urls.json"
QUERY_DELAY  = 4

POSITIVE_KEYWORDS = [
    "hotel", "hospitality", "resort", "hotelaria", "hoteleiro",
    "hospedagem", "hoteleria", "otel", "konaklama",
    "iptv", "in-room", "inroom", "set-top", "stb", "middleware",
    "display", "signage", "audiovisual", "av system", "commercial tv",
    "marriott", "hilton", "accor", "wyndham", "ihg", "radisson",
    "hyatt", "novotel", "ibis", "sheraton", "intercontinental",
    "samsung lynk", "lg procentric", "philips hospitality",
    "nonius", "acentic", "sonifi", "enseo", "guestroom", "guest room",
    "property management", "pms", "check-in", "front desk",
    "hotel technology", "hotel tv", "hotel construction", "hotel opening",
    "hotel pipeline", "hotel development", "hotel investment",
    "digital signage", "commercial display", "hotel lobby",
    "hitec", "oracle hospitality", "amadeus hospitality",
]

NEGATIVE_KEYWORDS = [
    "world cup", "fifa", "nfl", "nba", "mlb", "celebrity", "time 100",
    "concert", "music festival", "oscar", "grammy", "box office",
    "cryptocurrency", "bitcoin", "stock market",
    "crime", "murder", "accident", "weather forecast", "hurricane",
    "election", "senator", "congress", "parliament",
    "morgan wallen", "taylor swift", "college football",
]

QUERIES = {
    "Brazil - Hotel Development": [
        "Brazil hotel opening Marriott Hilton Accor 2026",
        "mercado hoteleiro Brasil investimento 2026",
        "Brasil hotelaria nova abertura rede hoteleira",
        "Brazil hospitality construction pipeline IHG Wyndham",
    ],
    "Brazil - AV Display and IPTV": [
        "Brazil hotel IPTV in-room entertainment system",
        "Brasil televisao comercial hotelaria display",
        "Brazil digital signage hotel AV technology",
        "Brasil middleware IPTV hotelaria Nonius",
    ],
    "LATAM South - Hotel Market": [
        "Colombia Peru Chile hotel opening Marriott Accor 2026",
        "Panama Argentina hospitality hotel investment",
        "hoteleria latinoamerica apertura rede hotelera 2026",
        "LATAM hotel chain IHG Wyndham Radisson expansion",
    ],
    "UAE - Hotel Development": [
        "Dubai hotel opening 2026 hospitality",
        "Abu Dhabi new hotel Marriott Hilton construction",
        "UAE hospitality investment hotel pipeline",
    ],
    "UAE - AV Display and IPTV": [
        "UAE hotel AV display technology system",
        "Dubai commercial display signage hospitality",
        "UAE hotel IPTV in-room entertainment",
    ],
    "Saudi Arabia - Hotel Development": [
        "Saudi Arabia hotel construction opening 2026",
        "Vision 2030 hospitality hotel Marriott Hilton",
        "NEOM Red Sea resort hotel development",
    ],
    "Saudi Arabia - AV and Display": [
        "Saudi Arabia hotel AV display technology 2026",
        "KSA hotel IPTV commercial display system",
        "Saudi hospitality technology integrator signage",
    ],
    "Turkey - Hotel and AV": [
        "Turkey hotel opening hospitality Marriott Hilton 2026",
        "Turkiye otel yatirim acilis 2026",
        "Turkey hotel AV display commercial technology",
    ],
    "Hotel Operators MEA Pipeline": [
        "Marriott Hilton Accor MEA new hotel 2026",
        "IHG Wyndham Radisson Middle East Africa hotel",
        "GCC hotel chain expansion new property 2026",
        "Arabian Travel Market hospitality announcement",
    ],
    "Hotel Operators LATAM Pipeline": [
        "Marriott Hilton Accor LATAM hotel new property 2026",
        "IHG Wyndham hotel South America expansion",
        "hotel chain Brazil Colombia Peru opening",
    ],
    "Hospitality TV IPTV and Middleware": [
        "hospitality TV IPTV hotel system 2026",
        "hotel in-room entertainment upgrade Android",
        "IPTV middleware hotel Nonius Acentic SONIFI Enseo",
        "hotel television CMS smart TV system integrator",
    ],
    "Commercial Display and Digital Signage": [
        "commercial display hotel lobby digital signage 2026",
        "hospitality AV display system integrator",
        "hotel commercial TV display B2B technology",
    ],
    "Hotel Construction and Investment Pipeline": [
        "hotel construction pipeline MEA report 2026",
        "hotel development LATAM investment pipeline",
        "new hotel supply Middle East Africa 2026",
        "JLL STR hotel pipeline hospitality supply",
    ],
    "Tenders RFP and Procurement": [
        "hotel AV technology tender RFP procurement",
        "hospitality TV display system tender 2026",
        "hotel technology procurement system integrator bid",
    ],
    "Competitive Intelligence": [
        "Samsung LYNK hotel TV hospitality 2026",
        "LG ProCentric hotel display system",
        "Philips hospitality TV commercial display",
        "hotel TV brand comparison system integrator",
    ],
    "Industry Events and Reports": [
        "HITEC hospitality technology conference 2026",
        "ISE AV exhibition commercial display 2026",
        "Arabian Travel Market hotel technology",
        "hotel technology trend report 2026",
    ],
}

def is_relevant(article):
    text = (article.get("title", "") + " " + article.get("body", "")).lower()
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

def fetch_news(queries, max_results, max_age_days, seen_urls):
    results = {}
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    new_seen = {}
    with DDGS() as ddgs:
        for section, query_list in queries.items():
            section_articles = []
            seen_this_section = set()
            for query in query_list:
                for attempt in range(3):
                    try:
                        time.sleep(QUERY_DELAY + random.uniform(0, 2))
                        articles = list(ddgs.news(query, max_results=max_results, timelimit="w"))
                        break
                    except RatelimitException:
                        wait = 15 + (attempt * 10)
                        print("  [RATELIMIT] waiting " + str(wait) + "s")
                        time.sleep(wait)
                        articles = []
                    except Exception as e:
                        print("  [WARN] " + str(e))
                        articles = []
                        break
                for a in articles:
                    url = a.get("url", "")
                    if not url or url in seen_urls or url in seen_this_section:
                        continue
                    if not is_relevant(a):
                        continue
                    seen_this_section.add(url)
                    pub_date_str = a.get("date", "")
                    try:
                        pub_date = datetime.datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                        if pub_date.replace(tzinfo=None) < cutoff:
                            continue
                    except Exception:
                        pass
                    section_articles.append({
                        "title":  a.get("title", "No title"),
                        "source": a.get("source", "Unknown"),
                        "date":   pub_date_str[:10] if pub_date_str else "N/A",
                        "url":    url,
                        "body":   a.get("body", ""),
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
                lines.append("Source: " + a["source"] + " | Date: " + a["date"] + " | " + a["url"] + "\n")
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
    results, new_seen = fetch_news(QUERIES, MAX_RESULTS, MAX_AGE_DAYS, seen_urls)
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
