import os, json, smtplib, datetime, urllib.request, urllib.error, re, xml.etree.ElementTree as ET, asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER       = os.environ["GMAIL_USER"]
GMAIL_PASS       = os.environ["GMAIL_PASS"]
RECIPIENT        = os.environ.get("RECIPIENT", GMAIL_USER)
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]

API_BASE         = "https://lanyiapi.com"
MODEL            = "claude-sonnet-4-6"
VOICE            = "en-US-AndrewNeural"
GITHUB_USER      = "Ismailmaby"
REPO_NAME        = "tcl-market-monitor"
PAGES_BASE       = "https://" + GITHUB_USER + ".github.io/" + REPO_NAME

def get_prompt():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return (
        "You are a market intelligence analyst for TCL hospitality TV, MEA and LATAM. Today: " + today + ".\n"
        "Generate a daily market intelligence briefing. Return ONLY raw JSON, no markdown:\n"
        '{"sections":['
        '{"title":"MEA Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"LATAM Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Competitive Intelligence","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Hospitality Technology","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"BD Opportunities","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]}'
        "]}\n"
        "Fill with insights about UAE/Saudi hotel market, Brazil LATAM hospitality, "
        "Samsung LYNK vs LG ProCentric weaknesses, IPTV middleware trends, TCL BD opportunities. "
        "Keep each insight under 40 words."
    )

def call_api(prompt, api_key):
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 1500,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        API_BASE + "/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode()

def extract_sections(raw):
    try:
        data = json.loads(raw)
        if "content" in data:
            text = ""
            for block in data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end]).get("sections", [])
    except Exception as e:
        print("  Parse error: " + str(e)[:60])
    return []

def sections_to_podcast_script(sections, run_date):
    date_str = datetime.datetime.utcnow().strftime("%B %d, %Y")

    # Build raw brief from sections
    brief_lines = []
    for s in sections:
        brief_lines.append("Section: " + s.get("title", ""))
        for item in s.get("items", [])[:2]:
            brief_lines.append("- " + item.get("headline", "") + ": " + item.get("insight", ""))
            if item.get("action"):
                brief_lines.append("  Action: " + item.get("action", ""))

    raw_brief = "\n".join(brief_lines)

    # Use LanyiAPI to rewrite as broadcast script
    broadcast_prompt = (
        "You are a professional broadcast news writer. "
        "Rewrite the following market intelligence brief as a 60-second spoken radio segment "
        "in the style of Bloomberg Radio or NPR Business. "
        "Use natural spoken English with varied sentence rhythm. "
        "No bullet points, no headers, no lists. "
        "Start with a strong opening hook. "
        "Include natural transitions like: Meanwhile... In Latin America... On the competitive front... "
        "End with one sharp closing line. "
        "Keep it under 900 characters total. "
        "Date: " + date_str + ".\n\n"
        "BRIEF:\n" + raw_brief + "\n\n"
        "OUTPUT (spoken script only, no stage directions):"
    )

    try:
        payload = json.dumps({
            "model": MODEL,
            "max_tokens": 400,
            "stream": False,
            "messages": [{"role": "user", "content": broadcast_prompt}]
        }).encode()
        req = urllib.request.Request(
            API_BASE + "/v1/messages",
            data=payload,
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
        data = json.loads(raw)
        script = ""
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                script += block.get("text", "")
        script = script.strip()
        if len(script) > 900:
            script = script[:897] + "..."
        print("  Broadcast script: " + str(len(script)) + " chars")
        return script
    except Exception as e:
        print("  Script rewrite failed: " + str(e)[:60] + " - using fallback")
        # Fallback: simple concat
        lines = ["Good morning. TCL Market Intelligence for " + date_str + "."]
        for s in sections:
            for item in s.get("items", [])[:1]:
                lines.append(item.get("headline", "") + ". " + item.get("insight", ""))
        lines.append("Stay sharp.")
        return " ".join(lines)[:900]

async def _generate_audio_async(script, output_path):
    import edge_tts
    tts = edge_tts.Communicate(script, voice=VOICE, rate="+8%", pitch="-4Hz")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    await tts.save(output_path)

def generate_audio(script, output_path):
    try:
        asyncio.run(_generate_audio_async(script, output_path))
        size = os.path.getsize(output_path)
        print("  Audio generated: " + str(size) + " bytes")
        return size
    except Exception as e:
        print("  Audio error: " + str(e)[:100])
        return 0

def update_rss_feed(run_date, audio_filename, audio_size, episode_title):
    feed_path = "docs/feed.xml"
    pub_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    audio_url = PAGES_BASE + "/audio/" + audio_filename
    guid = PAGES_BASE + "/audio/" + audio_filename

    # Load existing feed or create new
    items_xml = ""
    if os.path.exists(feed_path):
        try:
            tree = ET.parse(feed_path)
            root = tree.getroot()
            channel = root.find("channel")
            existing_items = channel.findall("item") if channel is not None else []
            # Keep last 20 episodes
            for item in existing_items[:20]:
                items_xml += ET.tostring(item, encoding="unicode")
        except Exception:
            items_xml = ""

    new_item = (
        "<item>"
        "<title>" + episode_title + "</title>"
        "<description>TCL daily market intelligence for MEA and LATAM hospitality TV sales.</description>"
        "<enclosure url=\"" + audio_url + "\" length=\"" + str(audio_size) + "\" type=\"audio/mpeg\"/>"
        "<pubDate>" + pub_date + "</pubDate>"
        "<guid>" + guid + "</guid>"
        "<itunes:duration>5:00</itunes:duration>"
        "</item>"
    )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" '
        'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        "<channel>"
        "<title>TCL Market Intelligence</title>"
        "<link>" + PAGES_BASE + "</link>"
        "<description>Daily hospitality TV and commercial display market intelligence for MEA and LATAM BD teams.</description>"
        "<language>en-us</language>"
        "<itunes:author>TCL Global Engineering Business Center</itunes:author>"
        "<itunes:category text=\"Business\"/>"
        "<itunes:explicit>false</itunes:explicit>"
        "<itunes:image href=\"" + PAGES_BASE + "/cover.jpg\"/>"
        + new_item + items_xml +
        "</channel>"
        "</rss>"
    )

    os.makedirs("docs", exist_ok=True)
    with open(feed_path, "w", encoding="utf-8") as f:
        f.write(rss)
    print("  RSS feed updated: " + feed_path)

def build_html_email(sections, run_date, has_audio, audio_url=""):
    total = sum(len(s.get("items", [])) for s in sections)
    audio_banner = ""
    if has_audio:
        audio_banner = (
            "<div style='margin:16px 0 0;padding:12px 16px;background:rgba(255,255,255,0.1);border-radius:8px;'>"
            "<p style='color:#7eb8f7;margin:0;font-size:13px;'>🎧 Audio version available - subscribe to TCL Market Intel podcast in your Podcast app</p>"
            "</div>"
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;padding:20px;background:#eef1f5;font-family:Arial,sans-serif;'>"
        "<div style='max-width:760px;margin:auto;'>"
        "<div style='background:#0d1b2a;padding:28px 32px;border-radius:10px 10px 0 0;'>"
        "<h1 style='color:#fff;margin:0 0 4px;font-size:20px;'>TCL Market Intelligence</h1>"
        "<p style='color:#7eb8f7;margin:0;font-size:13px;'>Hospitality TV and Commercial Display - Daily Briefing</p>"
        "<div style='margin-top:16px;'>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>Date: " + run_date[:10] + "</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + str(total) + " insights</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>" + str(len(sections)) + " sections</span>"
        "</div>"
        + audio_banner +
        "</div>"
        "<div style='background:#fff;padding:8px 32px 32px;border:1px solid #dde;border-top:none;border-radius:0 0 10px 10px;'>"
    )
    for s in sections:
        html += (
            "<div style='padding-top:28px;'>"
            "<h2 style='font-size:15px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;padding-bottom:8px;margin:0 0 16px;'>" + s.get("title", "") + "</h2>"
        )
        for item in s.get("items", []):
            html += (
                "<div style='margin-bottom:14px;padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #e63946;'>"
                "<p style='font-size:14px;font-weight:700;color:#0d1b2a;margin:0 0 8px;'>" + item.get("headline", "") + "</p>"
                "<p style='font-size:13px;color:#444;margin:0 0 8px;line-height:1.6;'>" + item.get("insight", "") + "</p>"
                + ("<p style='font-size:12px;color:#e63946;margin:4px 0 0;'><strong>Action:</strong> " + item["action"] + "</p>" if item.get("action") else "") +
                "</div>"
            )
        html += "</div>"
    html += (
        "<div style='margin-top:36px;padding-top:20px;border-top:1px solid #eee;text-align:center;'>"
        "<p style='font-size:11px;color:#aaa;line-height:1.8;margin:0;'>"
        "TCL Global Engineering Business Center<br>"
        "MEA: UAE, Saudi Arabia, Turkey | LATAM: Brazil, Colombia, Peru, Panama, Chile"
        "</p></div></div></body></html>"
    )
    return html

def build_markdown(sections, run_date):
    lines = ["# TCL Market Intelligence - " + run_date[:10], ""]
    for s in sections:
        lines.append("## " + s.get("title", ""))
        for item in s.get("items", []):
            lines.append("### " + item.get("headline", ""))
            lines.append(item.get("insight", ""))
            if item.get("action"):
                lines.append("Action: " + item["action"])
            lines.append("")
        lines.append("")
    return "\n".join(lines)

def send_email(html_body, md_content, run_date):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "TCL Market Intel - " + run_date[:10]
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    att = MIMEText(md_content, "plain", "utf-8")
    att.add_header("Content-Disposition", "attachment",
                   filename="tcl_intel_" + run_date[:10] + ".md")
    msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    print("  Email sent")

def save_markdown(content, run_date):
    os.makedirs("output", exist_ok=True)
    with open("output/tcl_intel_" + run_date[:10] + ".md", "w", encoding="utf-8") as f:
        f.write(content)
    print("  Markdown saved")

def main():
    run_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print("TCL Market Monitor - " + run_date)

    # Step 1: Generate content
    print("Generating content...")
    try:
        raw = call_api(get_prompt(), ANTHROPIC_KEY)
        sections = extract_sections(raw)
    except Exception as e:
        print("Content error: " + str(e))
        sections = []
    total = sum(len(s.get("items", [])) for s in sections)
    print("Sections: " + str(len(sections)) + " | Insights: " + str(total))

    # Step 2: Generate audio
    audio_filename = "tcl_intel_" + run_date[:10] + ".mp3"
    audio_path = "docs/audio/" + audio_filename
    episode_title = "TCL Market Intel - " + run_date[:10]
    has_audio = False
    audio_size = 0

    if sections:
        print("Generating podcast audio...")
        script = sections_to_podcast_script(sections, run_date)
        print("  Script length: " + str(len(script)) + " chars")
        audio_size = generate_audio(script, audio_path)
        has_audio = audio_size > 0

    # Step 3: Update RSS feed
    if has_audio:
        print("Updating RSS feed...")
        update_rss_feed(run_date, audio_filename, audio_size, episode_title)

    # Step 4: Send email
    md   = build_markdown(sections, run_date)
    html = build_html_email(sections, run_date, has_audio)
    save_markdown(md, run_date)
    send_email(html, md, run_date)
    print("Done.")

if __name__ == "__main__":
    main()
