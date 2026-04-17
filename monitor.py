import os
import json
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from duckduckgo_search import DDGS

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
RECIPIENT    = os.environ.get("RECIPIENT", GMAIL_USER)
MAX_RESULTS  = 5
MAX_AGE_DAYS = 2
SEEN_FILE    = "seen_urls.json"

QUERIES = {
    "🇧🇷 Brazil – Hotel Development": [
        "Brazil hotel opening 2026",
        "mercado hoteleiro Brasil 2026",
        "Brazil hotel construction pipeline",
        "Accor Marriott Hilton IHG Brasil",
        "Brazil resort development investment",
    ],
    "🇧🇷 Brazil – AV & Display": [
        "Brazil AV display commercial signage 2026",
        "Brasil televisão comercial display hotel",
        "Brazil digital signage hospitality",
        "Brasil integrador audiovisual hotelaria",
        "Brazil hotel in-room technology",
    ],
    "🇧🇷 Brazil – IPTV & Middleware": [
        "Brazil IPTV hotel middleware 2026",
        "Brasil sistema IPTV hotelaria",
        "Nonius Acentic SONIFI Brazil hotel",
        "Brasil plataforma streaming hotel",
    ],
    "🇦🇷🇨🇴🇵🇪 LATAM South – Hotel": [
        "Colombia Peru Chile hotel 2026",
        "Panama Argentina hospitality investment",
        "hoteleria latinoamerica tecnologia 2026",
        "LATAM hotel chain expansion",
        "Wyndham IHG Radisson LATAM",
    ],
    "🇦🇪 UAE – Hotel Development": [
        "UAE hotel opening Dubai 2026",
        "Abu Dhabi hotel construction 2026",
        "Dubai hospitality investment operator",
        "UAE hotel pipeline development",
        "فندق دبي افتتاح 2026",
    ],
    "🇦🇪 UAE – AV & Display": [
        "UAE AV display commercial signage",
        "Dubai hospitality technology AV",
        "UAE IPTV smart TV hotel system",
        "Dubai digital signage hotel lobby",
        "UAE commercial display tender",
    ],
    "🇸🇦 Saudi Arabia – Hotel Development": [
        "Saudi Arabia hotel construction 2026",
        "Vision 2030 hospitality giga projects",
        "NEOM Red Sea hotel opening",
        "Saudi hotel operator investment",
        "فندق السعودية مشاريع 2026",
    ],
    "🇸🇦 Saudi Arabia – AV & Display": [
        "Saudi Arabia AV display hospitality",
        "Saudi hotel technology system integrator",
        "KSA commercial display signage 2026",
        "Saudi IPTV hotel entertainment",
    ],
    "🇹🇷 Turkey – Hotel & AV": [
        "Turkey hotel investment 2026",
        "Türkiye otel teknoloji 2026",
        "Turkey AV display commercial signage",
        "Türkiye konaklama sektörü yatırım",
        "Turkey hospitality operator expansion",
    ],
    "🏨 Global Hotel Operators – MEA": [
        "Marriott Hilton Accor MEA expansion 2026",
        "IHG Wyndham hotel Middle East Africa",
        "hotel chain new property GCC 2026",
        "Arabian Travel Market hotel 2026",
    ],
    "🏨 Global Hotel Operators – LATAM": [
        "Marriott Hilton Accor LATAM 2026",
        "IHG Wyndham hotel South America",
        "hotel chain expansion Brazil Colombia",
        "LATAM hospitality operator news",
    ],
    "📺 Hospitality TV & IPTV": [
        "hospitality TV IPTV hotel system 2026",
        "hotel in-room entertainment upgrade",
        "IPTV middleware hotel Nonius Acentic",
        "hotel TV Android CMS system",
        "SONIFI Enseo hotel entertainment",
    ],
    "🖥️ Commercial Display & Signage": [
        "commercial display hotel lobby 2026",
        "digital signage hospitality AV",
        "hotel digital display system integrator",
        "commercial TV display B2B 2026",
        "hotel lobby signage technology",
    ],
    "🏗️ Hotel Construction & Pipeline": [
        "hotel construction pipeline MEA 2026",
        "hotel development report LATAM 2026",
        "new hotel opening Middle East",
        "hospitality real estate investment 2026",
        "JLL hotel pipeline report",
    ],
    "📋 Tenders & Procurement": [
        "hotel AV tender procurement 2026",
        "hospitality TV RFP system integrator",
        "hotel technology procurement Middle East",
        "hotel display tender Brazil",
    ],
    "🏆 Competitive Intelligence": [
        "Samsung LYNK hotel TV 2026",
        "LG ProCentric hospitality display",
        "Philips hospitality TV hotel",
        "TCL hotel TV commercial display",
        "hotel TV brand comparison 2026",
    ],
    "📰 Industry Events & Trends": [
        "HITEC hospitality technology 2026",
        "ISE AV display exhibition 2026",
        "Arabian Travel Market 2026",
        "hotel technology trend 2026",
        "Skift hospitality insight 2026",
    ],
}

def load_seen_urls():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
        return {
            url: ts for url, ts in data.items()
            if datetime.datetime.fromisoformat(ts) > cutoff
        }
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
                try:
                    articles = list(ddgs.news(query, max_results=max_results, timelimit="w"))
                    for a in articles:
                        url = a.get("url", "")
                        if not url or url in seen_urls or url in seen_this_section:
                            continue
                        seen_this_section.add(url)
                        pub_date_str = a.get("date", "")
                        try:
                            pub_date = datetime.datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                            pub_date = pub_date.replace(tzinfo=None)
                            if pub_date < cutoff:
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
                except Exception as e:
                    print(f"  [WARN] Query failed '{query}': {e}")

            results[section] = section_articles

    return results, new_seen

def build_markdown(results, run_date):
    total = sum(len(v) for v in results.values())
    lines = [
        "# TCL Hospitality Market Intelligence",
        f"**Date:** {run_date}",
        f"**Total articles:** {total}",
        "**Markets:** Brazil, Argentina, Colombia, Peru, Panama, Chile | UAE, Saudi Arabia, Turkey",
        "",
        "---",
        "",
    ]
    for section, articles in results.items():
        lines.append(f"## {section}")
        if not articles:
            lines.append("_No new articles today._")
        else:
            for a in articles:
                lines.append(f"### {a['title']}")
                lines.append(f"- **Source:** {a['source']}  |  **Date:** {a['date']}")
                lines.append(f"- **URL:** {a['url']}")
                if a["body"]:
                    lines.append(f"\n{a['body'][:500]}")
        lines.append("")
    return "\n".join(lines)

def build_html_email(results, run_date):
    total = sum(len(v) for v in results.values())
    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#222;">
    <div style="background:#1a1a2e;padding:24px 32px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">📡 TCL Market Intelligence</h1>
        <p style="color:#aaa;margin:6px 0 0;">{run_date} · {total} new articles today</p>
    </div>
    <div style="padding:24px 32px;background:#f9f9f9;border:1px solid #e0e0e0;">"""
    for section, articles in results.items():
        html += f'<h2 style="color:#1a1a2e;border-bottom:2px solid #e63946;padding-bottom:6px;">{section}</h2>'
        if not articles:
            html += '<p style="color:#bbb;font-style:italic;font-size:13px;">No new articles today.</p>'
        else:
            for a in articles:
                html += f"""<div style="margin-bottom:14px;padding:14px;background:#fff;border-radius:6px;border-left:4px solid #e63946;">
                    <a href="{a['url']}" style="font-size:15px;font-weight:bold;color:#1a1a2e;text-decoration:none;">{a['title']}</a>
                    <p style="font-size:12px;color:#888;margin:4px 0;">{a['source']} · {a['date']}</p>
                    {'<p style="font-size:13px;color:#444;margin:6px 0 0;">' + a["body"][:300] + ('...' if len(a["body"]) > 300 else '') + '</p>' if a["body"] else ''}
                </div>"""
    html += """<hr style="border:none;border-top:1px solid #ddd;margin:24px 0;">
    <p style="font-size:11px;color:#aaa;text-align:center;">
        TCL Hospitality Market Monitor · Daily Digest<br>
        Attach the .md file to NotebookLM for audio briefing
    </p></div></body></html>"""
    return html

def send_email(html_body, markdown_content, run_date):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"📡 TCL Market Intel · {run_date[:10]}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    attachment = MIMEText(markdown_content, "plain", "utf-8")
    attachment.add_header("Content-Disposition", "attachment",
                          filename=f"tcl_intel_{run_date[:10]}.md")
    msg.attach(attachment)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    print(f"  ✅ Email sent to {RECIPIENT}")

def save_markdown(content, run_date):
    os.makedirs("output", exist_ok=True)
    filename = f"output/tcl_intel_{run_date[:10]}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ Markdown saved: {filename}")

def main():
    run_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n🚀 TCL Market Monitor — {run_date}\n")

    seen_urls = load_seen_urls()
    print(f"   Known URLs (dedup): {len(seen_urls)}\n")

    results, new_seen = fetch_news(QUERIES, MAX_RESULTS, MAX_AGE_DAYS, seen_urls)

    for section, articles in results.items():
        print(f"   {section}: {len(articles)} articles")

    seen_urls.update(new_seen)
    save_seen_urls(seen_urls)

    md_content   = build_markdown(results, run_date)
    html_content = build_html_email(results, run_date)
    save_markdown(md_content, run_date)
    send_email(html_content, md_content, run_date)
    print(f"\n✅ Done. {len(new_seen)} new URLs saved to dedup list.")

if __name__ == "__main__":
    main()
