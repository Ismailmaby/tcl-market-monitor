import os, json, smtplib, datetime, urllib.request, urllib.error, re, xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER       = os.environ["GMAIL_USER"]
GMAIL_PASS       = os.environ["GMAIL_PASS"]
RECIPIENT        = os.environ.get("RECIPIENT", GMAIL_USER)
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
ELEVENLABS_KEY   = os.environ["ELEVENLABS_API_KEY"]
API_BASE         = "https://lanyiapi.com"
MODEL            = "claude-sonnet-4-6"
VOICE_ID         = "TxGEqnHWrfWFTfGW9XjX"
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
    lines = [
        "Good morning. TCL Market Intelligence for " + date_str + ". "
        "Here are your top hospitality TV opportunities across MEA and LATAM.",
    ]
    for s in sections:
        lines.append(s.get("title", "") + ".")
        for item in s.get("items", [])[:2]:
            headline = item.get("headline", "")
            insight  = item.get("insight", "")
            lines.append(headline + ". " + insight)
    lines.append("Stay sharp. Good selling.")
    script = " ".join(l for l in lines if l.strip())
    if len(script) > 1400:
        script = script[:1397] + "..."
    return script

def generate_audio(script, api_key, output_path):
    payload = json.dumps({
        "text": script,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}
    }).encode()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/text-to-speech/" + VOICE_ID,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_data)
            print("  Audio generated: " + str(len(audio_data)) + " bytes")
            return len(audio_data)
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        print("  ElevenLabs error: " + str(e.code) + " - " + err)
        return 0
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
        audio_size = generate_audio(script, ELEVENLABS_KEY, audio_path)
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
