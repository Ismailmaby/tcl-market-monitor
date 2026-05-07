import os, json, smtplib, datetime, urllib.request, urllib.error
import asyncio, re, tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER    = os.environ["GMAIL_USER"]
GMAIL_PASS    = os.environ["GMAIL_PASS"]
RECIPIENT     = os.environ.get("RECIPIENT", GMAIL_USER)
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
SESSION       = os.environ.get("SESSION", "morning")
API_BASE      = "https://lanyiapi.com"
MODEL         = "claude-sonnet-4-6"
VOICE         = "en-US-AndrewNeural"
GITHUB_USER   = "Ismailmaby"
REPO_NAME     = "tcl-market-monitor"
PAGES_BASE    = "https://" + GITHUB_USER + ".github.io/" + REPO_NAME

def get_intel_prompt(session):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")

    if session == "morning":
        focus = (
            "Focus on strategic market overview: hotel pipeline developments, "
            "new property openings, major chain expansions, competitive landscape shifts. "
            "Angle: what should a BD manager know before making calls today?"
        )
    else:
        focus = (
            "Focus on tactical BD actions: specific tenders and RFPs in pipeline, "
            "key accounts to follow up, pricing intelligence, channel partner moves. "
            "Angle: what concrete actions should a BD manager take before end of day?"
        )

    return (
        "You are a market intelligence analyst for TCL hospitality TV, MEA and LATAM. "
        "Today: " + today + ". Cover news and events from " + week_ago + " to " + today + ".\n"
        + focus + "\n"
        "Return ONLY raw JSON:\n"
        '{"sections":['
        '{"title":"MEA Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"LATAM Hotel Market","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Competitive Intelligence","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Hospitality Technology","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"BD Opportunities","items":[{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."},{"headline":"...","insight":"...","action":"..."}]}'
        "]}\n"
        "Each insight max 40 words. Base on real industry knowledge from the past week."
    )

def get_broadcast_prompt(sections, session):
    date_str = datetime.datetime.utcnow().strftime("%B %d, %Y")
    time_label = "Morning Briefing" if session == "morning" else "Evening Update"

    content = ""
    for s in sections:
        content += "\n\n" + s.get("title", "") + ":\n"
        for item in s.get("items", []):
            content += "- " + item.get("headline","") + ": " + item.get("insight","") + " Action: " + item.get("action","") + "\n"

    return (
        "You are a senior broadcast news writer. Style: Bloomberg Radio meets BBC World Service Business. "
        "Write a professional 10-minute radio " + time_label + " script for " + date_str + ". "
        "Target: 1500 words. "
        "Use [SECTION] on its own line between the 6 segments.\n\n"
        "STRUCTURE:\n"
        "OPENING (60 words): Welcome, state date and session (" + time_label + "), tease top 3 stories.\n"
        "[SECTION]\n"
        "MEA HOTEL MARKET (270 words): Lead story first. Market context, numbers, chain names, implications for hospitality TV in UAE and Saudi.\n"
        "[SECTION]\n"
        "LATAM HOTEL MARKET (270 words): Brazil focus, then Colombia Peru Chile. City-level specifics, brand moves, risks and opportunities.\n"
        "[SECTION]\n"
        "COMPETITIVE INTELLIGENCE (270 words): Samsung LYNK and LG ProCentric weaknesses. Specific talking points TCL sales reps can use today.\n"
        "[SECTION]\n"
        "HOSPITALITY TECHNOLOGY (270 words): IPTV middleware, Android TV, in-room entertainment trends. Vendor landscape in MEA and LATAM.\n"
        "[SECTION]\n"
        "BD OPPORTUNITIES AND CLOSE (270 words): Specific accounts, tenders, follow-ups for this week. Sharp closing line.\n\n"
        "RULES:\n"
        "- Natural spoken English only. No bullet points. No headers. No asterisks.\n"
        "- Vary sentence length. Mix short punchy lines with longer analytical ones.\n"
        "- Transitions: Meanwhile... Turning now to... On the competitive front... Looking at technology... And finally...\n"
        "- Include company names, cities, and numbers.\n"
        "- [SECTION] must be on its own line only.\n\n"
        "INTELLIGENCE DATA:\n" + content
    )

def call_api(prompt, max_tokens=2000):
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

async def _tts_segment(text, path):
    import edge_tts
    tts = edge_tts.Communicate(text, voice=VOICE, rate="+8%", pitch="-3Hz")
    await tts.save(path)

def tts(text, path):
    asyncio.run(_tts_segment(text, path))

def make_news_intro(duration_ms=7000):
    from pydub.generators import Sine
    from pydub import AudioSegment
    # News broadcast style: ascending tones
    base = AudioSegment.silent(duration=duration_ms)
    # Low drone
    drone = Sine(82).to_audio_segment(duration=duration_ms).apply_gain(-18)
    base = base.overlay(drone)
    # Melody notes - news style
    melody = [(880,0,400), (1108,350,400), (1320,700,400), (1760,1050,600),
              (1320,1800,300), (1108,2100,300), (880,2400,800),
              (1760,3500,500), (1320,4000,500), (1108,4500,500), (880,5000,1500)]
    for freq, pos, dur in melody:
        note = Sine(freq).to_audio_segment(duration=dur).fade_in(30).fade_out(int(dur*0.6)).apply_gain(-8)
        base = base.overlay(note, position=pos)
    return base.fade_in(100).fade_out(800)

def make_transition_chime():
    from pydub.generators import Sine
    from pydub import AudioSegment
    notes = [(880,0,500),(1108,200,400),(1320,400,600)]
    base = AudioSegment.silent(duration=1400)
    for freq, pos, dur in notes:
        note = Sine(freq).to_audio_segment(duration=dur).fade_in(20).fade_out(300).apply_gain(-10)
        base = base.overlay(note, position=pos)
    silence = AudioSegment.silent(duration=400)
    return silence + base + silence

def make_outro(duration_ms=5000):
    from pydub.generators import Sine
    from pydub import AudioSegment
    base = AudioSegment.silent(duration=duration_ms)
    drone = Sine(82).to_audio_segment(duration=duration_ms).apply_gain(-20)
    base = base.overlay(drone)
    notes = [(880,0,600),(1108,400,500),(1320,800,400),(1108,1300,500),(880,1800,1500)]
    for freq, pos, dur in notes:
        note = Sine(freq).to_audio_segment(duration=dur).fade_in(50).fade_out(int(dur*0.7)).apply_gain(-10)
        base = base.overlay(note, position=pos)
    return base.fade_in(300).fade_out(2000)

def make_news_background(duration_ms):
    from pydub.generators import Sine, WhiteNoise
    from pydub import AudioSegment
    # Subtle newsroom ambient: very low white noise + bass hum
    noise = WhiteNoise().to_audio_segment(duration=duration_ms).apply_gain(-38)
    hum = Sine(60).to_audio_segment(duration=duration_ms).apply_gain(-30)
    return noise.overlay(hum)

def generate_full_audio(broadcast_script, output_path):
    from pydub import AudioSegment

    print("  Splitting script into segments...")
    parts = [p.strip() for p in re.split(r'\[SECTION\]', broadcast_script) if p.strip()]
    print("  Segments: " + str(len(parts)))

    tmpdir = tempfile.mkdtemp()

    # TTS each segment
    voice_segments = []
    for i, part in enumerate(parts):
        part_path = os.path.join(tmpdir, "seg_" + str(i) + ".mp3")
        print("  TTS " + str(i+1) + "/" + str(len(parts)) + " (" + str(len(part)) + " chars)...")
        try:
            tts(part, part_path)
            seg = AudioSegment.from_mp3(part_path)
            voice_segments.append(seg)
        except Exception as e:
            print("  TTS error: " + str(e)[:60])
            voice_segments.append(AudioSegment.silent(duration=1000))

    # Build transition chime
    chime = make_transition_chime()

    # Assemble voice track with chimes between segments
    voice_track = AudioSegment.empty()
    for i, seg in enumerate(voice_segments):
        if i == 0:
            voice_track += seg
        else:
            voice_track += chime + seg

    total_ms = len(voice_track)
    print("  Voice track: " + str(round(total_ms/60000, 1)) + " min")

    # Build music elements
    intro = make_news_intro(7000)
    pause_after_intro = AudioSegment.silent(duration=800)
    outro = make_outro(5000)
    full_ms = len(intro) + len(pause_after_intro) + total_ms + len(outro)

    # Build background ambient for full duration (quiet newsroom)
    background = make_news_background(full_ms)

    # Assemble: intro music + pause + voice + outro music
    foreground = intro + pause_after_intro + voice_track + outro

    # Mix: background at low volume under foreground
    # Use overlay with foreground on top (louder)
    final = foreground.overlay(background)

    # Gentle normalize - don't over-compress
    peak = final.max_dBFS
    if peak < -3:
        final = final.apply_gain(-3 - peak)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.export(output_path, format="mp3", bitrate="128k")
    size = os.path.getsize(output_path)
    print("  Final: " + str(round(total_ms/60000, 1)) + " min, " + str(round(size/1024/1024, 1)) + " MB")
    return size

def update_rss_feed(run_date, session, audio_filename, audio_size, episode_title):
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
            for item in existing[:28]:
                items_xml += ET.tostring(item, encoding="unicode")
        except Exception:
            pass

    new_item = (
        "<item>"
        "<title>" + episode_title + "</title>"
        "<description>TCL Market Intelligence " + ("Morning Briefing" if session=="morning" else "Evening Update") + " - MEA and LATAM hospitality TV BD briefing.</description>"
        "<enclosure url=\"" + audio_url + "\" length=\"" + str(audio_size) + "\" type=\"audio/mpeg\"/>"
        "<pubDate>" + pub_date + "</pubDate>"
        "<guid>" + guid + "</guid>"
        "<itunes:duration>10:00</itunes:duration>"
        "<itunes:explicit>false</itunes:explicit>"
        "</item>"
    )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">'
        "<channel>"
        "<title>TCL Market Intelligence</title>"
        "<link>" + PAGES_BASE + "</link>"
        "<description>Daily hospitality TV and commercial display market intelligence. MEA and LATAM BD briefing. Morning and Evening editions.</description>"
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
    print("  RSS updated")

def build_html_email(sections, run_date, session, has_audio):
    total = sum(len(s.get("items",[])) for s in sections)
    session_label = "Morning Briefing" if session == "morning" else "Evening Update"
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;padding:20px;background:#eef1f5;font-family:Arial,sans-serif;'>"
        "<div style='max-width:760px;margin:auto;'>"
        "<div style='background:#0d1b2a;padding:28px 32px;border-radius:10px 10px 0 0;'>"
        "<h1 style='color:#fff;margin:0 0 4px;font-size:20px;'>TCL Market Intelligence</h1>"
        "<p style='color:#7eb8f7;margin:0;font-size:13px;'>" + session_label + " - Hospitality TV and Commercial Display</p>"
        "<div style='margin-top:16px;'>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + run_date[:10] + "</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + str(total) + " insights</span>"
        + ("<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>🎙️ Audio ready</span>" if has_audio else "") +
        "</div></div>"
        "<div style='background:#fff;padding:8px 32px 32px;border:1px solid #dde;border-top:none;border-radius:0 0 10px 10px;'>"
    )
    for s in sections:
        html += (
            "<div style='padding-top:28px;'>"
            "<h2 style='font-size:15px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;padding-bottom:8px;margin:0 0 16px;'>" + s.get("title","") + "</h2>"
        )
        for item in s.get("items",[]):
            html += (
                "<div style='margin-bottom:14px;padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #e63946;'>"
                "<p style='font-size:14px;font-weight:700;color:#0d1b2a;margin:0 0 8px;'>" + item.get("headline","") + "</p>"
                "<p style='font-size:13px;color:#444;margin:0 0 8px;line-height:1.6;'>" + item.get("insight","") + "</p>"
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

def build_markdown(sections, run_date, session):
    label = "Morning Briefing" if session == "morning" else "Evening Update"
    lines = ["# TCL Market Intelligence - " + label + " " + run_date[:10], ""]
    for s in sections:
        lines.append("## " + s.get("title",""))
        for item in s.get("items",[]):
            lines.append("### " + item.get("headline",""))
            lines.append(item.get("insight",""))
            if item.get("action"):
                lines.append("Action: " + item["action"])
            lines.append("")
        lines.append("")
    return "\n".join(lines)

def send_email(html_body, md_content, run_date, session):
    label = "AM" if session == "morning" else "PM"
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "TCL Market Intel [" + label + "] - " + run_date[:10]
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    att = MIMEText(md_content, "plain", "utf-8")
    att.add_header("Content-Disposition", "attachment",
                   filename="tcl_intel_" + label.lower() + "_" + run_date[:10] + ".md")
    msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    print("  Email sent")

def save_markdown(content, run_date, session):
    label = "am" if session == "morning" else "pm"
    os.makedirs("output", exist_ok=True)
    with open("output/tcl_intel_" + label + "_" + run_date[:10] + ".md", "w", encoding="utf-8") as f:
        f.write(content)
    print("  Markdown saved")

def main():
    run_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    label = "Morning Briefing" if SESSION == "morning" else "Evening Update"
    print("TCL Market Monitor [" + label + "] - " + run_date)

    print("\n[1/4] Generating market intelligence...")
    try:
        raw = call_api(get_intel_prompt(SESSION), max_tokens=1500)
        sections = extract_sections(raw)
        print("  Sections: " + str(len(sections)) + " | Insights: " + str(sum(len(s.get("items",[])) for s in sections)))
    except Exception as e:
        print("  ERROR: " + str(e))
        sections = []

    print("\n[2/4] Writing broadcast script...")
    broadcast_script = ""
    if sections:
        try:
            raw_script = call_api(get_broadcast_prompt(sections, SESSION), max_tokens=2500)
            broadcast_script = extract_text(raw_script)
            print("  Script: " + str(len(broadcast_script)) + " chars")
        except Exception as e:
            print("  Script error: " + str(e))

    print("\n[3/4] Generating broadcast audio...")
    has_audio = False
    audio_size = 0
    ts = datetime.datetime.utcnow().strftime("%H%M")
    audio_filename = "tcl_" + ("am" if SESSION=="morning" else "pm") + "_" + run_date[:10].replace("-","") + "_" + ts + ".mp3"
    audio_path = "docs/audio/" + audio_filename

    if broadcast_script:
        try:
            audio_size = generate_full_audio(broadcast_script, audio_path)
            has_audio = audio_size > 0
            if has_audio:
                episode_title = "TCL Market Intel [" + ("AM" if SESSION=="morning" else "PM") + "] - " + run_date[:10]
                update_rss_feed(run_date, SESSION, audio_filename, audio_size, episode_title)
        except Exception as e:
            print("  Audio error: " + str(e))

    print("\n[4/4] Sending email...")
    md   = build_markdown(sections, run_date, SESSION)
    html = build_html_email(sections, run_date, SESSION, has_audio)
    save_markdown(md, run_date, SESSION)
    send_email(html, md, run_date, SESSION)
    print("\nDone.")

if __name__ == "__main__":
    main()
