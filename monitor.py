import os, json, smtplib, datetime, urllib.request, urllib.error
import asyncio, re, tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER    = os.environ["GMAIL_USER"]
GMAIL_PASS    = os.environ["GMAIL_PASS"]
RECIPIENT     = os.environ.get("RECIPIENT", GMAIL_USER)
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
API_BASE      = "https://lanyiapi.com"
MODEL         = "claude-sonnet-4-6"
VOICE         = "en-US-AndrewNeural"
GITHUB_USER   = "Ismailmaby"
REPO_NAME     = "tcl-market-monitor"
PAGES_BASE    = "https://" + GITHUB_USER + ".github.io/" + REPO_NAME

# ─────────────────────────────────────────
# CONTENT GENERATION
# ─────────────────────────────────────────

def get_intel_prompt():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return (
        "You are a market intelligence analyst for TCL hospitality TV, MEA and LATAM. Today: " + today + ".\n"
        "Generate a daily market intelligence briefing. Return ONLY raw JSON:\n"
        '{"sections":['
        '{"title":"MEA Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"LATAM Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Competitive Intelligence","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Hospitality Technology","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"BD Opportunities","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]}'
        "]}\n"
        "Topics: UAE/Saudi hotel market, Brazil LATAM hospitality, Samsung LYNK vs LG ProCentric, IPTV middleware, TCL BD actions. Keep each insight under 40 words."
    )

def get_broadcast_prompt(sections):
    date_str = datetime.datetime.utcnow().strftime("%B %d, %Y")
    content = ""
    for s in sections:
        content += "\n\n" + s.get("title", "") + ":\n"
        for item in s.get("items", []):
            content += "- " + item.get("headline", "") + ": " + item.get("insight", "") + " Action: " + item.get("action", "") + "\n"

    return (
        "You are a senior broadcast news writer for a business radio program, style of Bloomberg Radio and BBC World Service Business. "
        "Write a professional 10-minute radio broadcast script based on the market intelligence below. "
        "Target: 1400 to 1600 words total. "
        "Use [SECTION] on its own line to separate the 5 major segments.\n\n"
        "STRUCTURE:\n"
        "Opening (no [SECTION] before it): 50 words. Welcome listeners, state today's date (" + date_str + "), tease the top 3 stories.\n"
        "[SECTION]\n"
        "MEA Hotel Market (280 words): Lead with strongest story. Bring in market context, pipeline numbers, chain names, implications for hospitality TV suppliers in UAE and Saudi.\n"
        "[SECTION]\n"
        "LATAM Hotel Market (280 words): Brazil and South America hotel landscape. Specific city-level opportunities, brand expansions, risks.\n"
        "[SECTION]\n"
        "Competitive Intelligence (280 words): Deep dive on Samsung LYNK and LG ProCentric. Their specific weaknesses TCL can exploit. Concrete positioning language.\n"
        "[SECTION]\n"
        "Hospitality Technology (280 words): IPTV middleware landscape, Android TV adoption, in-room entertainment evolution, key vendor moves.\n"
        "[SECTION]\n"
        "BD Opportunities and Closing (280 words): Specific accounts and tenders to chase this week. Closing summary and one motivational line for the BD team.\n\n"
        "RULES:\n"
        "- Spoken English only. No bullet points, no headers, no asterisks.\n"
        "- Natural sentence rhythm. Mix short and long sentences.\n"
        "- Use broadcast transitions: Meanwhile... Turning now to... On the competitive front... Looking at technology... And finally...\n"
        "- Include specific company names, geographies, and numbers.\n"
        "- [SECTION] must appear on its own line, never inline.\n"
        "- Do NOT include any stage directions or sound cues in the text.\n\n"
        "MARKET INTELLIGENCE:\n" + content
    )

def call_api(prompt, max_tokens=1500):
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}]
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

def extract_text(raw):
    try:
        data = json.loads(raw)
        if "content" in data:
            text = ""
            for block in data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
            return text.strip()
    except Exception:
        pass
    return ""

# ─────────────────────────────────────────
# AUDIO GENERATION
# ─────────────────────────────────────────

async def _tts_segment(text, path):
    import edge_tts
    tts = edge_tts.Communicate(text, voice=VOICE, rate="+8%", pitch="-3Hz")
    await tts.save(path)

def tts(text, path):
    asyncio.run(_tts_segment(text, path))

def make_chime():
    from pydub.generators import Sine
    from pydub import AudioSegment
    bell_a = Sine(880).to_audio_segment(duration=700).fade_in(10).fade_out(600).apply_gain(-12)
    bell_b = Sine(1320).to_audio_segment(duration=500).fade_in(10).fade_out(450).apply_gain(-16)
    bell_c = Sine(660).to_audio_segment(duration=800).fade_in(10).fade_out(700).apply_gain(-18)
    chime = bell_a.overlay(bell_b, position=50).overlay(bell_c, position=100)
    silence = AudioSegment.silent(duration=600)
    return silence + chime + silence

def make_ambient(duration_ms):
    from pydub.generators import Sine
    a2 = Sine(110).to_audio_segment(duration=duration_ms).apply_gain(-42)
    e3 = Sine(165).to_audio_segment(duration=duration_ms).apply_gain(-44)
    a3 = Sine(220).to_audio_segment(duration=duration_ms).apply_gain(-46)
    e4 = Sine(330).to_audio_segment(duration=duration_ms).apply_gain(-48)
    return a2.overlay(e3).overlay(a3).overlay(e4)

def make_intro_music(duration_ms=6000):
    from pydub.generators import Sine
    from pydub import AudioSegment
    notes = [(220, 0), (277, 300), (330, 600), (440, 900), (554, 1200), (660, 1500)]
    intro = AudioSegment.silent(duration=duration_ms)
    for freq, pos in notes:
        note = Sine(freq).to_audio_segment(duration=800).fade_in(80).fade_out(400).apply_gain(-14)
        intro = intro.overlay(note, position=pos)
    return intro.fade_in(200).fade_out(1000)

def make_outro_music(duration_ms=4000):
    from pydub.generators import Sine
    from pydub import AudioSegment
    notes = [(660, 0), (554, 300), (440, 600), (330, 900), (220, 1200)]
    outro = AudioSegment.silent(duration=duration_ms)
    for freq, pos in notes:
        note = Sine(freq).to_audio_segment(duration=800).fade_in(50).fade_out(600).apply_gain(-14)
        outro = outro.overlay(note, position=pos)
    return outro.fade_in(500).fade_out(1500)

def generate_full_audio(broadcast_script, output_path):
    from pydub import AudioSegment

    print("  Splitting script by [SECTION]...")
    parts = [p.strip() for p in re.split(r'\[SECTION\]', broadcast_script) if p.strip()]
    print("  Parts: " + str(len(parts)))

    tmpdir = tempfile.mkdtemp()

    # Generate TTS for each part
    voice_segments = []
    for i, part in enumerate(parts):
        part_path = os.path.join(tmpdir, "part_" + str(i) + ".mp3")
        print("  TTS part " + str(i+1) + "/" + str(len(parts)) + " (" + str(len(part)) + " chars)...")
        try:
            tts(part, part_path)
            seg = AudioSegment.from_mp3(part_path)
            voice_segments.append(seg)
        except Exception as e:
            print("  TTS error part " + str(i) + ": " + str(e)[:60])
            voice_segments.append(AudioSegment.silent(duration=500))

    # Build chime and assemble voice track
    chime = make_chime()
    voice_track = AudioSegment.empty()
    for i, seg in enumerate(voice_segments):
        if i == 0:
            voice_track += seg
        else:
            voice_track += chime + seg

    total_ms = len(voice_track)
    print("  Voice track: " + str(round(total_ms/60000, 1)) + " min")

    # Create intro/outro music
    intro = make_intro_music(6000)
    outro = make_outro_music(4000)

    # Create ambient background for full duration
    full_ms = len(intro) + total_ms + len(outro)
    ambient = make_ambient(full_ms)

    # Assemble full track: intro + voice + outro
    voice_with_bookends = intro + voice_track + outro

    # Mix ambient under everything at low volume
    final = ambient.overlay(voice_with_bookends)
    final = final.normalize()

    # Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.export(output_path, format="mp3", bitrate="96k")
    size = os.path.getsize(output_path)
    print("  Final audio: " + str(round(total_ms/60000, 1)) + " min, " + str(round(size/1024/1024, 1)) + " MB")
    return size

# ─────────────────────────────────────────
# RSS FEED
# ─────────────────────────────────────────

def update_rss_feed(run_date, audio_filename, audio_size, episode_title, duration_min):
    feed_path = "docs/feed.xml"
    pub_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    audio_url = PAGES_BASE + "/audio/" + audio_filename
    guid = audio_url

    items_xml = ""
    if os.path.exists(feed_path):
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(feed_path)
            root = tree.getroot()
            channel = root.find("channel")
            existing = channel.findall("item") if channel is not None else []
            for item in existing[:20]:
                items_xml += ET.tostring(item, encoding="unicode")
        except Exception:
            pass

    duration_str = str(int(duration_min)) + ":00"
    new_item = (
        "<item>"
        "<title>" + episode_title + "</title>"
        "<description>TCL daily market intelligence for MEA and LATAM hospitality TV sales. 10-minute broadcast briefing.</description>"
        "<enclosure url=\"" + audio_url + "\" length=\"" + str(audio_size) + "\" type=\"audio/mpeg\"/>"
        "<pubDate>" + pub_date + "</pubDate>"
        "<guid>" + guid + "</guid>"
        "<itunes:duration>" + duration_str + "</itunes:duration>"
        "<itunes:explicit>false</itunes:explicit>"
        "</item>"
    )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" '
        'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">'
        "<channel>"
        "<title>TCL Market Intelligence</title>"
        "<link>" + PAGES_BASE + "</link>"
        "<description>Daily hospitality TV and commercial display market intelligence. MEA and LATAM BD briefing.</description>"
        "<language>en-us</language>"
        "<itunes:author>TCL Global Engineering Business Center</itunes:author>"
        "<itunes:category text=\"Business\"/>"
        "<itunes:explicit>false</itunes:explicit>"
        + new_item + items_xml +
        "</channel></rss>"
    )

    os.makedirs("docs", exist_ok=True)
    with open(feed_path, "w", encoding="utf-8") as f:
        f.write(rss)
    print("  RSS updated: " + feed_path)

# ─────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────

def build_html_email(sections, run_date, has_audio):
    total = sum(len(s.get("items", [])) for s in sections)
    audio_note = ""
    if has_audio:
        audio_note = (
            "<div style='margin:16px 0 0;padding:12px 16px;background:rgba(126,184,247,0.15);border-radius:8px;'>"
            "<p style='color:#7eb8f7;margin:0;font-size:13px;'>🎙️ 10-min audio briefing available - subscribe via Podcast app</p>"
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
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>5 sections</span>"
        "</div>" + audio_note + "</div>"
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
    att.add_header("Content-Disposition", "attachment", filename="tcl_intel_" + run_date[:10] + ".md")
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

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    run_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print("TCL Market Monitor - " + run_date)

    # Step 1: Generate intel JSON
    print("\n[1/4] Generating market intelligence...")
    try:
        raw = call_api(get_intel_prompt(), max_tokens=1500)
        sections = extract_sections(raw)
        print("  Sections: " + str(len(sections)) + " | Insights: " + str(sum(len(s.get("items",[])) for s in sections)))
    except Exception as e:
        print("  ERROR: " + str(e))
        sections = []

    # Step 2: Generate broadcast script
    print("\n[2/4] Writing broadcast script...")
    broadcast_script = ""
    has_audio = False
    audio_size = 0

    if sections:
        try:
            raw_script = call_api(get_broadcast_prompt(sections), max_tokens=2000)
            broadcast_script = extract_text(raw_script)
            print("  Script: " + str(len(broadcast_script)) + " chars, ~" + str(round(len(broadcast_script.split())/150, 1)) + " min")
        except Exception as e:
            print("  Script error: " + str(e))

    # Step 3: Generate audio
    if broadcast_script:
        print("\n[3/4] Generating broadcast audio...")
        audio_filename = "tcl_intel_" + run_date[:10] + ".mp3"
        audio_path = "docs/audio/" + audio_filename
        try:
            audio_size = generate_full_audio(broadcast_script, audio_path)
            has_audio = audio_size > 0
            if has_audio:
                duration_min = round(os.path.getsize(audio_path) / (96000/8) / 60, 1)
                episode_title = "TCL Market Intel - " + run_date[:10]
                update_rss_feed(run_date, audio_filename, audio_size, episode_title, duration_min)
        except Exception as e:
            print("  Audio error: " + str(e))

    # Step 4: Email
    print("\n[4/4] Sending email...")
    md   = build_markdown(sections, run_date)
    html = build_html_email(sections, run_date, has_audio)
    save_markdown(md, run_date)
    send_email(html, md, run_date)
    print("\nDone.")

if __name__ == "__main__":
    main()
