Note
“””

import os, json, smtplib, datetime, time, random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException

# ─────────────────────────────────────────────────────────────

# CONFIG

# ─────────────────────────────────────────────────────────────

GMAIL_USER   = os.environ[“GMAIL_USER”]
GMAIL_PASS   = os.environ[“GMAIL_PASS”]
RECIPIENT    = os.environ.get(“RECIPIENT”, GMAIL_USER)
MAX_RESULTS  = 6
MAX_AGE_DAYS = 2
SEEN_FILE    = “seen_urls.json”
QUERY_DELAY  = 4   # seconds between queries (avoid rate limit)

# ─────────────────────────────────────────────────────────────

# RELEVANCE FILTER

# ─────────────────────────────────────────────────────────────

POSITIVE_KEYWORDS = [
“hotel”, “hospitality”, “resort”, “hotelaria”, “hoteleiro”,
“hospedagem”, “hotelería”, “otel”, “konaklama”, “فندق”, “فنادق”,
“iptv”, “in-room”, “inroom”, “set-top”, “stb”, “middleware”,
“display”, “signage”, “audiovisual”, “av system”, “commercial tv”,
“marriott”, “hilton”, “accor”, “wyndham”, “ihg”, “radisson”,
“hyatt”, “novotel”, “ibis”, “sheraton”, “intercontinental”,
“samsung lynk”, “lg procentric”, “philips hospitality”,
“nonius”, “acentic”, “sonifi”, “enseo”, “guestroom”, “guest room”,
“property management”, “pms”, “check-in”, “front desk”,
“hotel technology”, “hotel tv”, “hotel construction”, “hotel opening”,
“hotel pipeline”, “hotel development”, “hotel investment”,
“digital signage”, “commercial display”, “hotel lobby”,
“hitec”, “oracle hospitality”, “amadeus hospitality”,
]

NEGATIVE_KEYWORDS = [
“world cup”, “fifa”, “nfl”, “nba”, “mlb”, “celebrity”, “time 100”,
“concert”, “music festival”, “oscar”, “grammy”, “box office”,
“cryptocurrency”, “bitcoin”, “stock market”, “earnings report”,
“crime”, “murder”, “accident”, “weather forecast”, “hurricane”,
“election”, “senator”, “congress”, “parliament”,
“morgan wallen”, “taylor swift”, “college football”,
]

def is_relevant(article):
text = (article.get(“title”, “”) + “ “ + article.get(“body”, “”)).lower()
# Reject if strong negative signal without hospitality context
if any(neg in text for neg in NEGATIVE_KEYWORDS):
if not any(kw in text for kw in [“hotel”, “hospitality”, “resort”, “hotelaria”]):
return False
# Accept if any positive keyword present
return any(kw in text for kw in POSITIVE_KEYWORDS)

# ─────────────────────────────────────────────────────────────

# SEARCH QUERIES

# ─────────────────────────────────────────────────────────────

QUERIES = {
“🇧🇷 Brazil – Hotel Development”: [
“Brazil hotel opening Marriott Hilton Accor 2026”,
“mercado hoteleiro Brasil investimento 2026”,
“Brasil hotelaria nova abertura rede hoteleira”,
“Brazil hospitality construction pipeline IHG Wyndham”,
],
“🇧🇷 Brazil – AV, Display & IPTV”: [
“Brazil hotel IPTV in-room entertainment system”,
“Brasil televisão comercial hotelaria display”,
“Brazil digital signage hotel AV technology”,
“Brasil middleware IPTV hotelaria Nonius”,
],
“🇦🇷🇨🇴🇵🇪 LATAM South – Hotel Market”: [
“Colombia Peru Chile hotel opening Marriott Accor 2026”,
“Panama Argentina hospitality hotel investment”,
“hoteleria latinoamerica apertura rede hotelera 2026”,
“LATAM hotel chain IHG Wyndham Radisson expansion”,
],
“🇦🇪 UAE – Hotel Development”: [
“Dubai hotel opening 2026 hospitality”,
“Abu Dhabi new hotel Marriott Hilton construction”,
“UAE hospitality investment hotel pipeline”,
“فندق دبي افتتاح فنادق 2026”,
],
“🇦🇪 UAE – AV, Display & IPTV”: [
“UAE hotel AV display technology system”,
“Dubai commercial display signage hospitality”,
“UAE hotel IPTV in-room entertainment”,
“Dubai hotel TV technology integrator”,
],
“🇸🇦 Saudi Arabia – Hotel Development”: [
“Saudi Arabia hotel construction opening 2026”,
“Vision 2030 hospitality hotel Marriott Hilton”,
“NEOM Red Sea resort hotel development”,
“فنادق السعودية مشاريع رؤية 2030”,
],
“🇸🇦 Saudi Arabia – AV & Display”: [
“Saudi Arabia hotel AV display technology 2026”,
“KSA hotel IPTV commercial display system”,
“Saudi hospitality technology integrator signage”,
],
“🇹🇷 Turkey – Hotel & AV”: [
“Turkey hotel opening hospitality Marriott Hilton 2026”,
“Türkiye otel yatırım açılış 2026”,
“Turkey hotel AV display commercial technology”,
“Türkiye konaklama teknoloji dijital tabela”,
],
“🏨 Hotel Operators – MEA Pipeline”: [
“Marriott Hilton Accor MEA new hotel 2026”,
“IHG Wyndham Radisson Middle East Africa hotel”,
“GCC hotel chain expansion new property 2026”,
“Arabian Travel Market hospitality announcement”,
],
“🏨 Hotel Operators – LATAM Pipeline”: [
“Marriott Hilton Accor LATAM hotel new property 2026”,
“IHG Wyndham hotel South America expansion”,
“hotel chain Brazil Colombia Peru opening”,
“Latin America hospitality operator investment 2026”,
],
“📺 Hospitality TV, IPTV & Middleware”: [
“hospitality TV IPTV hotel system 2026”,
“hotel in-room entertainment upgrade Android”,
“IPTV middleware hotel Nonius Acentic SONIFI Enseo”,
“hotel television CMS smart TV system integrator”,
“hotel set-top box streaming in-room”,
],
“🖥️ Commercial Display & Digital Signage”: [
“commercial display hotel lobby digital signage 2026”,
“hospitality AV display system integrator”,
“hotel commercial TV display B2B technology”,
“digital signage hotel restaurant conference”,
],
“🏗️ Hotel Construction & Investment Pipeline”: [
“hotel construction pipeline MEA report 2026”,
“hotel development LATAM investment pipeline”,
“new hotel supply Middle East Africa 2026”,
“JLL STR hotel pipeline hospitality supply”,
“hotel real estate investment hospitality”,
],
“📋 Tenders, RFP & Procurement”: [
“hotel AV technology tender RFP procurement”,
“hospitality TV display system tender 2026”,
“hotel technology procurement system integrator bid”,
],
“🏆 Competitive Intelligence”: [
“Samsung LYNK hotel TV hospitality 2026”,
“LG ProCentric hotel display system”,
“Philips hospitality TV commercial display”,
“hotel TV brand comparison system integrator”,
“TCL commercial display hotel hospitality”,
],
“📰 Industry Events & Reports”: [
“HITEC hospitality technology conference 2026”,
“ISE AV exhibition commercial display 2026”,
“Arabian Travel Market hotel technology”,
“hotel technology trend report 2026”,
“hospitality industry report forecast 2026”,
],
}

# ─────────────────────────────────────────────────────────────

# DEDUPLICATION

# ─────────────────────────────────────────────────────────────

def load_seen_urls():
if os.path.exists(SEEN_FILE):
with open(SEEN_FILE, “r”) as f:
data = json.load(f)
cutoff = datetime.datetime.now() - datetime.timedelta(days=14)
return {
url: ts for url, ts in data.items()
if datetime.datetime.fromisoformat(ts) > cutoff
}
return {}

def save_seen_urls(seen):
with open(SEEN_FILE, “w”) as f:
json.dump(seen, f, indent=2)

# ─────────────────────────────────────────────────────────────

# FETCH NEWS

# ─────────────────────────────────────────────────────────────

def fetch_news(queries, max_results, max_age_days, seen_urls):
results = {}
cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
new_seen = {}

```
with DDGS() as ddgs:
    for section, query_list in queries.items():
        section_articles = []
        seen_this_section = set()

        for query in query_list:
            # Rate limit protection: delay + retry
            for attempt in range(3):
                try:
                    time.sleep(QUERY_DELAY + random.uniform(0, 2))
                    articles = list(ddgs.news(query, max_results=max_results, timelimit="w"))
                    break
                except RatelimitException:
                    wait = 15 + (attempt * 10)
                    print(f"  [RATELIMIT] '{query[:40]}' — waiting {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                    articles = []
                except Exception as e:
                    print(f"  [WARN] '{query[:40]}': {e}")
                    articles = []
                    break

            for a in articles:
                url = a.get("url", "")
                if not url or url in seen_urls or url in seen_this_section:
                    continue
                if not is_relevant(a):
                    continue
                seen_this_section.add(url)

                # Date filter
                pub_date_str = a.get("date", "")
                try:
                    pub_date = datetime.datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                    if pub_date.replace(tzinfo=None) < cutoff:
                        continue
                except Exception:
                    pass  # include if date unparseable

                section_articles.append({
                    "title":  a.get("title", "No title"),
                    "source": a.get("source", "Unknown"),
                    "date":   pub_date_str[:10] if pub_date_str else "N/A",
                    "url":    url,
                    "body":   a.get("body", ""),
                })
                new_seen[url] = datetime.datetime.now().isoformat()

        results[section] = section_articles
        print(f"   {section}: {len(section_articles)} articles")

return results, new_seen
```

# ─────────────────────────────────────────────────────────────

# BUILD MARKDOWN (for NotebookLM)

# ─────────────────────────────────────────────────────────────

def build_markdown(results, run_date):
total = sum(len(v) for v in results.values())
active = [s for s, v in results.items() if v]

```
lines = [
    "# TCL Hospitality Market Intelligence — Daily Briefing",
    f"**Date:** {run_date}",
    f"**Total new articles:** {total}",
    "**Markets:** UAE · Saudi Arabia · Turkey · Brazil · Colombia · Peru · Panama · Chile",
    "**Scope:** Hotel development pipeline · AV/Display technology · IPTV & middleware · Competitive intelligence",
    f"**Active sections today:** {len(active)} of {len(results)}",
    "", "---", "",
]

for section, articles in results.items():
    lines.append(f"## {section}")
    if not articles:
        lines.append("*No new articles in this category today.*\n")
    else:
        for a in articles:
            lines.append(f"### {a['title']}")
            lines.append(f"**Source:** {a['source']} | **Date:** {a['date']} | [Read full article]({a['url']})\n")
            if a["body"]:
                lines.append(f"{a['body'][:600]}\n")
    lines.append("")

lines += [
    "---",
    f"*TCL Global Engineering Business Center · Hospitality TV & Commercial Display*",
    f"*Generated: {run_date}*",
]
return "\n".join(lines)
```

# ─────────────────────────────────────────────────────────────

# BUILD HTML EMAIL

# ─────────────────────────────────────────────────────────────

def build_html_email(results, run_date):
total = sum(len(v) for v in results.values())
active = sum(1 for v in results.values() if v)

```
html = f"""<!DOCTYPE html>
```

<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:20px;background:#eef1f5;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:720px;margin:auto;">

  <!-- HEADER -->

  <div style="background:#0d1b2a;padding:28px 32px;border-radius:10px 10px 0 0;">
    <h1 style="color:#fff;margin:0 0 4px;font-size:20px;font-weight:700;letter-spacing:-0.3px;">
      📡 TCL Market Intelligence
    </h1>
    <p style="color:#7eb8f7;margin:0;font-size:13px;">
      Hospitality TV & Commercial Display · Daily Briefing
    </p>
    <div style="margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;">
      <span style="background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;">📅 {run_date[:10]}</span>
      <span style="background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;">📰 {total} new articles</span>
      <span style="background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;">📂 {active} active sections</span>
      <span style="background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;">🌍 MEA + LATAM</span>
    </div>
  </div>

  <!-- BODY -->

  <div style="background:#fff;padding:8px 32px 32px;border:1px solid #dde;border-top:none;border-radius:0 0 10px 10px;">"""

```
for section, articles in results.items():
    html += f"""
<div style="padding-top:28px;">
  <h2 style="font-size:15px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;
             padding-bottom:8px;margin:0 0 16px;">{section}</h2>"""

    if not articles:
        html += '<p style="color:#ccc;font-style:italic;font-size:13px;margin:0;">No new articles today.</p>'
    else:
        for a in articles:
            body = (a["body"][:280] + "…") if len(a["body"]) > 280 else a["body"]
            html += f"""
  <div style="margin-bottom:12px;padding:16px;background:#f8f9fa;border-radius:8px;
              border-left:4px solid #e63946;">
    <a href="{a['url']}" style="font-size:14px;font-weight:600;color:#0d1b2a;
              text-decoration:none;line-height:1.4;display:block;">{a['title']}</a>
    <div style="margin-top:6px;">
      <span style="font-size:11px;color:#e63946;font-weight:700;text-transform:uppercase;
                   letter-spacing:0.5px;">{a['source']}</span>
      <span style="font-size:11px;color:#999;margin-left:8px;">{a['date']}</span>
    </div>
    {'<p style="font-size:13px;color:#555;margin:8px 0 0;line-height:1.55;">' + body + '</p>' if body else ''}
  </div>"""

    html += "\n    </div>"

html += f"""
<!-- FOOTER -->
<div style="margin-top:36px;padding-top:20px;border-top:1px solid #eee;text-align:center;">
  <p style="font-size:11px;color:#aaa;line-height:1.8;margin:0;">
    <strong style="color:#0d1b2a;">TCL Global Engineering Business Center</strong><br>
    Hospitality TV & Commercial Display · Key Account BD<br>
    MEA: UAE · Saudi Arabia · Turkey &nbsp;|&nbsp; LATAM: Brazil · Colombia · Peru · Panama · Chile<br><br>
    <span style="color:#7eb8f7;">📎 Attach the .md file to NotebookLM for your daily audio briefing</span>
  </p>
</div>
```

  </div>

</div>
</body></html>"""
    return html

# ─────────────────────────────────────────────────────────────

# SEND EMAIL

# ─────────────────────────────────────────────────────────────

def send_email(html_body, markdown_content, run_date):
msg = MIMEMultipart(“mixed”)
msg[“Subject”] = f”📡 TCL Market Intel · {run_date[:10]} · {sum(1 for l in html_body.split() if ‘articles’ in l)} digest”
msg[“From”]    = GMAIL_USER
msg[“To”]      = RECIPIENT
msg.attach(MIMEText(html_body, “html”))
attachment = MIMEText(markdown_content, “plain”, “utf-8”)
attachment.add_header(“Content-Disposition”, “attachment”,
filename=f”tcl_intel_{run_date[:10]}.md”)
msg.attach(attachment)
with smtplib.SMTP_SSL(“smtp.gmail.com”, 465) as server:
server.login(GMAIL_USER, GMAIL_PASS)
server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
print(f”  ✅ Email sent → {RECIPIENT}”)

def save_markdown(content, run_date):
os.makedirs(“output”, exist_ok=True)
path = f”output/tcl_intel_{run_date[:10]}.md”
with open(path, “w”, encoding=“utf-8”) as f:
f.write(content)
print(f”  ✅ Markdown saved → {path}”)

# ─────────────────────────────────────────────────────────────

# MAIN

# ─────────────────────────────────────────────────────────────

def main():
run_date = datetime.datetime.utcnow().strftime(”%Y-%m-%d %H:%M UTC”)
print(f”\n{’=’*55}”)
print(f”  TCL Market Monitor · {run_date}”)
print(f”{’=’*55}\n”)

```
seen_urls = load_seen_urls()
print(f"  Dedup cache: {len(seen_urls)} known URLs (14-day window)\n")

print("  Fetching news...\n")
results, new_seen = fetch_news(QUERIES, MAX_RESULTS, MAX_AGE_DAYS, seen_urls)

total = sum(len(v) for v in results.values())
print(f"\n  Total new articles: {total}")

seen_urls.update(new_seen)
save_seen_urls(seen_urls)

md      = build_markdown(results, run_date)
html    = build_html_email(results, run_date)
save_markdown(md, run_date)

print("\n  Sending email...")
send_email(html, md, run_date)

print(f"\n{'='*55}")
print(f"  ✅ Done · {len(new_seen)} new URLs cached")
print(f"{'='*55}\n")
```

if **name** == “**main**”:
main()
