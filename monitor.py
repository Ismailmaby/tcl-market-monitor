import os
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

QUERIES = {
    "🇧🇷 Brazil – Hotel & Hospitality": [
        "Brazil hotel technology IPTV 2025",
        "Brazil hospitality TV display investment 2025",
        "Brazil hotel opening construction pipeline 2025",
    ],
    "🇦🇷🇨🇴🇵🇪 LATAM South – Hotel Market": [
        "Argentina Colombia Peru hotel technology 2025",
        "LATAM hospitality market growth 2025",
        "Panama Chile hotel investment 2025",
    ],
    "🇦🇪 UAE – Hotel & Display": [
        "UAE hotel technology smart TV 2025",
        "Dubai Abu Dhabi hotel opening 2025",
        "UAE hospitality IPTV commercial display 2025",
    ],
    "🇸🇦 Saudi Arabia – Hospitality": [
        "Saudi Arabia hotel construction Vision 2030 2025",
        "NEOM Red Sea hotel technology 2025",
        "Saudi hospitality TV display 2025",
    ],
    "🇹🇷 Turkey – Hotel Market": [
        "Turkey hotel technology 2025",
        "Turkey hospitality display IPTV 2025",
        "Türkiye otel teknoloji 2025",
    ],
    "🏨 Competitive Intelligence": [
        "Samsung LYNK hospitality hotel TV 2025",
        "LG ProCentric hotel smart TV 2025",
        "hospitality TV Android CMS hotel 2025",
    ],
}

def fetch_news(queries, max_results, max_age_days):
    results = {}
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    with DDGS() as ddgs:
        for section, query_list in queries.items():
            section_articles = []
            seen_urls = set()
            for query in query_list:
                try:
                    articles = list(ddgs.news(query, max_results=max_results, timelimit="w"))
                    for a in articles:
                        url = a.get("url", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
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
                except Exception as e:
                    print(f"  [WARN] Query failed '{query}': {e}")
            results[section] = section_articles
    return results

def build_markdown(results, run_date):
    lines = [
        f"# TCL Hospitality Market Intelligence",
        f"**Date:** {run_date}",
        f"**Markets:** Brazil, Argentina, Colombia, Peru, Panama, Chile | UAE, Saudi Arabia, Turkey",
        "",
        "---",
        "",
    ]
    for section, articles in results.items():
        lines.append(f"## {section}")
        if not articles:
            lines.append("_No new articles found._")
        else:
            for a in articles:
                lines.append(f"### {a['title']}")
                lines.append(f"- **Source:** {a['source']}  |  **Date:** {a['date']}")
                lines.append(f"- **URL:** {a['url']}")
                if a["body"]:
                    lines.append(f"\n{a['body'][:400]}")
        lines.append("")
    return "\n".join(lines)

def build_html_email(results, run_date):
    total = sum(len(v) for v in results.values())
    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:720px;margin:auto;color:#222;">
    <div style="background:#1a1a2e;padding:24px 32px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">📡 TCL Market Intelligence</h1>
        <p style="color:#aaa;margin:6px 0 0;">{run_date} · {total} articles</p>
    </div>
    <div style="padding:24px 32px;background:#f9f9f9;border:1px solid #e0e0e0;">"""
    for section, articles in results.items():
        html += f'<h2 style="color:#1a1a2e;border-bottom:2px solid #e63946;padding-bottom:6px;">{section}</h2>'
        if not articles:
            html += '<p style="color:#999;font-style:italic;">No new articles found.</p>'
        else:
            for a in articles:
                html += f"""<div style="margin-bottom:16px;padding:14px;background:#fff;border-radius:6px;border-left:4px solid #e63946;">
                    <a href="{a['url']}" style="font-size:15px;font-weight:bold;color:#1a1a2e;text-decoration:none;">{a['title']}</a>
                    <p style="font-size:12px;color:#888;margin:4px 0;">{a['source']} · {a['date']}</p>
                    {'<p style="font-size:13px;color:#444;margin:6px 0 0;">' + a["body"][:280] + '</p>' if a["body"] else ''}
                </div>"""
    html += "</div></body></html>"
    return html

def send_email(html_body, markdown_content, run_date):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"📡 TCL Market Intel · {run_date}"
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
    results = fetch_news(QUERIES, MAX_RESULTS, MAX_AGE_DAYS)
    for section, articles in results.items():
        print(f"   {section}: {len(articles)} articles")
    md_content   = build_markdown(results, run_date)
    html_content = build_html_email(results, run_date)
    save_markdown(md_content, run_date)
    send_email(html_content, md_content, run_date)
    print("\n✅ Done.")

if __name__ == "__main__":
    main()
