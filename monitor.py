import os, json, smtplib, datetime, urllib.request, urllib.error, sys
import asyncio, re, tempfile, xml.etree.ElementTree as ET
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
VOICE_CN      = "zh-CN-YunxiNeural"
GITHUB_USER   = "Ismailmaby"
REPO_NAME     = "tcl-market-monitor"
PAGES_BASE    = "https://" + GITHUB_USER + ".github.io/" + REPO_NAME

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

RSS_SOURCES = [
    ("HospitalityNet",       "https://www.hospitalitynet.org/rss/news.xml"),
    ("Hotel Management",     "https://www.hotelmanagement.net/rss.xml"),
    ("Skift",                "https://skift.com/feed/"),
    ("Digital Signage Today","https://www.digitalsignagetoday.com/rss/"),
    ("Hosteltur LATAM",      "https://www.hosteltur.com/feed"),
    ("eTurboNews",           "https://www.eturbonews.com/feed/"),
    ("Business Traveller",   "https://www.businesstraveller.com/feed/"),
]

HOSPITALITY_KEYWORDS = [
    "hotel", "hospitality", "resort", "motel", "inn", "hotelaria",
    "hotelero", "hoteleria", "hospedagem", "otel",
    "iptv", "in-room", "display", "signage", "audiovisual",
    "marriott", "hilton", "accor", "wyndham", "ihg", "radisson",
    "hyatt", "novotel", "ibis", "sheraton", "intercontinental",
    "samsung lynk", "lg procentric", "philips hospitality",
    "nonius", "acentic", "sonifi", "enseo",
    "hotel technology", "hotel tv", "hotel construction",
    "hotel opening", "hotel pipeline", "hotel development",
    "digital signage", "commercial display", "guestroom",
    "middle east", "saudi", "dubai", "uae", "gulf",
    "brazil", "brasil", "latin america", "latam", "colombia",
]

def fetch_rss(name, url, max_age_days=7):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=max_age_days)
    articles = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in items:
            title = (item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            desc  = (item.findtext("description") or item.findtext("{http://www.w3.org/2005/Atom}summary") or "").strip()
            link  = (item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or "").strip()
            pub   = (item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}published") or "").strip()

            # Relevance filter
            text = (title + " " + desc).lower()
            if not any(kw in text for kw in HOSPITALITY_KEYWORDS):
                continue

            # Date filter
            try:
                import email.utils
                pub_dt = email.utils.parsedate_to_datetime(pub).replace(tzinfo=None)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

            # Clean description
            clean_desc = re.sub(r'<[^>]+>', '', desc)[:300]
            articles.append({
                "source": name,
                "title": title,
                "description": clean_desc,
                "link": link,
                "pub": pub[:10] if pub else "",
            })
        print("  " + name + ": " + str(len(articles)) + " relevant articles")
    except Exception as e:
        print("  " + name + " SKIP: " + str(e)[:50])
    return articles

def fetch_all_news():
    all_articles = []
    seen = set()
    for name, url in RSS_SOURCES:
        arts = fetch_rss(name, url)
        for a in arts:
            if a["title"] not in seen:
                seen.add(a["title"])
                all_articles.append(a)
    print("  Total unique articles: " + str(len(all_articles)))
    return all_articles

def build_news_context(articles):
    lines = []
    for a in articles[:40]:
        lines.append("[" + a["source"] + " | " + a["pub"] + "] " + a["title"])
        if a["description"]:
            lines.append("  " + a["description"])
    return "\n".join(lines)

def get_analysis_prompt(news_context, session):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if session == "morning":
        focus = "Strategic market overview: hotel pipeline, competitive landscape, technology trends. What should a BD manager know before making calls today?"
    else:
        focus = "Tactical BD actions: specific accounts to follow up, tenders in pipeline, pricing intelligence, channel moves. What concrete actions before end of day?"

    return (
        "You are a market intelligence analyst for TCL hospitality TV, MEA (UAE, Saudi Arabia, Turkey) and LATAM (Brazil, Colombia, Peru, Chile). "
        "Today: " + today + ". Session: " + ("Morning" if session=="morning" else "Evening") + ".\n"
        "Focus: " + focus + "\n\n"
        "Based ONLY on the real news articles below, generate a market intelligence briefing. "
        "If an article is not directly relevant to hospitality TV or hotel markets, ignore it. "
        "Return ONLY raw JSON:\n"
        '{"sections":['
        '{"title":"MEA Hotel Market","items":[{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"LATAM Hotel Market","items":[{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Competitive Intelligence","items":[{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"Hospitality Technology","items":[{"headline":"...","insight":"...","action":"..."}]},'
        '{"title":"BD Opportunities","items":[{"headline":"...","insight":"...","action":"..."}]}'
        "]}\n"
        "Each section: 2-3 items based on real articles. Each insight max 50 words. "
        "If no real news covers a section, note it briefly.\n\n"
        "REAL NEWS ARTICLES:\n" + news_context
    )

def get_broadcast_prompt(sections, articles, session):
    date_str = datetime.datetime.utcnow().strftime("%B %d, %Y")
    time_label = "Morning Briefing" if session == "morning" else "Evening Update"

    # Top headlines for broadcast
    headlines = "\n".join(["- " + a["title"] + " (" + a["source"] + ")" for a in articles[:15]])

    intel = ""
    for s in sections:
        intel += "\n" + s.get("title","") + ":\n"
        for item in s.get("items",[]):
            intel += "  " + item.get("headline","") + ": " + item.get("insight","") + "\n"

    return (
        "You are a senior broadcast news writer. Style: Bloomberg Radio meets BBC World Service Business. "
        "Write a professional 10-minute radio " + time_label + " script for " + date_str + ". "
        "Target: 3000 words total (~15 minutes of spoken audio). Use [SECTION] on its own line between the 6 segments.\n\n"
        "CRITICAL PRIVACY RULE: This is a PUBLIC broadcast. "
        "Do NOT mention any specific client company names, prospect names, or internal sales targets. "
        "Focus ONLY on: industry trends, market dynamics, hotel chain brand names (Marriott/Hilton/Accor etc as public companies), "
        "competitor products (Samsung LYNK, LG ProCentric), and technology trends. "
        "BD opportunities should be framed as market opportunities, not specific client mentions.\n\n"
        "STRUCTURE:\n"
        "OPENING (120 words): Strong hook, date, tease top 3 stories.\n"
        "[SECTION]\n"
        "MEA HOTEL MARKET (560 words): Market trends, pipeline numbers, major hotel brand expansions in UAE and Saudi. "
        "Focus on publicly known developments.\n"
        "[SECTION]\n"
        "LATAM HOTEL MARKET (560 words): Brazil and South America hotel landscape, brand expansions, market opportunities.\n"
        "[SECTION]\n"
        "COMPETITIVE INTELLIGENCE (560 words): Samsung LYNK and LG ProCentric public product moves and market positioning weaknesses.\n"
        "[SECTION]\n"
        "HOSPITALITY TECHNOLOGY (560 words): IPTV middleware trends, Android TV adoption, in-room entertainment evolution.\n"
        "[SECTION]\n"
        "MARKET OUTLOOK AND CLOSE (560 words): Key market opportunities in MEA and LATAM for hospitality TV suppliers. "
        "Forward-looking industry analysis. Sharp motivational close.\n\n"
        "RULES:\n"
        "- Spoken English only. No bullets. No headers. No asterisks.\n"
        "- Vary sentence length. Natural broadcast rhythm.\n"
        "- Transitions: Meanwhile... Turning now to... On the competitive front... And finally...\n"
        "- Reference real news sources and headlines where relevant.\n"
        "- NO specific client or prospect company names in the script.\n"
        "- [SECTION] on its own line only.\n\n"
        "TOP NEWS HEADLINES TODAY:\n" + headlines + "\n\n"
        "INTELLIGENCE ANALYSIS:\n" + intel
    )
def get_chinese_broadcast_prompt(english_script, session):
    time_label = "早间播报" if session == "morning" else "晚间播报"
    return (
        "你是一名专业的中文广播新闻播音员，风格参考中央人民广播电台和中国国际广播电台。"
        "请将以下英文酒店行业市场情报播报稿翻译并改写为标准中文广播稿。\n\n"
        "要求：\n"
        "- 目标时长：15分钟朗读内容（约2500-3000中文字）\n"
        "- 语言：标准普通话，播音腔，正式庄重\n"
        "- 句式：多用短句，适合朗读，节奏流畅\n"
        "- 过渡语：使用'与此同时'、'转眼来看'、'在竞争格局方面'、'最后'等\n"
        "- 保留[SECTION]标记在对应位置（单独一行）\n"
        "- 隐私规则：不提及任何具体客户或潜在客户名称\n"
        "- 可提及公开的酒店品牌（万豪、希尔顿、雅高等）和竞品（三星LYNK、LG ProCentric）\n"
        "- 开头说：'现在是TCL市场情报" + time_label + "，以下是今日要点。'\n"
        "- 结尾说：'以上是今日TCL市场情报播报，感谢收听，祝您工作顺利。'\n\n"
        "原文英文播报稿：\n" + english_script
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

async def _tts_segment_cn(text, path):
    import edge_tts
    tts = edge_tts.Communicate(text, voice=VOICE_CN, rate="+5%", pitch="-2Hz")
    await tts.save(path)

def tts_cn(text, path):
    asyncio.run(_tts_segment_cn(text, path))


def make_news_intro(duration_ms=7000):
    from pydub.generators import Sine
    from pydub import AudioSegment
    base = AudioSegment.silent(duration=duration_ms)
    drone = Sine(82).to_audio_segment(duration=duration_ms).apply_gain(-18)
    base = base.overlay(drone)
    melody = [(880,0,400),(1108,350,400),(1320,700,400),(1760,1050,600),
              (1320,1800,300),(1108,2100,300),(880,2400,800),
              (1760,3500,500),(1320,4000,500),(1108,4500,500),(880,5000,1500)]
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
    return AudioSegment.silent(duration=400) + base + AudioSegment.silent(duration=400)

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
    noise = WhiteNoise().to_audio_segment(duration=duration_ms).apply_gain(-38)
    hum = Sine(60).to_audio_segment(duration=duration_ms).apply_gain(-30)
    return noise.overlay(hum)

def generate_voice_track(script, voice_func, tmpdir, prefix):
    from pydub import AudioSegment
    parts = [p.strip() for p in re.split(r'\[SECTION\]', script) if p.strip()]
    print("  " + prefix + " segments: " + str(len(parts)))
    chime = make_transition_chime()
    track = AudioSegment.empty()
    for i, part in enumerate(parts):
        part_path = os.path.join(tmpdir, prefix + "_" + str(i) + ".mp3")
        print("  TTS " + prefix + " " + str(i+1) + "/" + str(len(parts)) + " (" + str(len(part)) + " chars)...")
        try:
            voice_func(part, part_path)
            seg = AudioSegment.from_mp3(part_path)
            track += seg if i == 0 else chime + seg
        except Exception as e:
            print("  TTS error: " + str(e)[:60])
            track += AudioSegment.silent(duration=1000)
    return track

def make_language_bridge():
    from pydub.generators import Sine
    from pydub import AudioSegment
    silence = AudioSegment.silent(duration=1000)
    notes = [(660,0,600),(880,400,500),(1108,800,400),(1320,1200,800)]
    bridge = AudioSegment.silent(duration=3000)
    for freq, pos, dur in notes:
        note = Sine(freq).to_audio_segment(duration=dur).fade_in(50).fade_out(400).apply_gain(-10)
        bridge = bridge.overlay(note, position=pos)
    return silence + bridge + silence

def generate_full_audio(broadcast_script, chinese_script, output_path):
    from pydub import AudioSegment
    tmpdir = tempfile.mkdtemp()

    # English track
    print("  [EN] Generating English voice track...")
    en_track = generate_voice_track(broadcast_script, tts, tmpdir, "en")
    en_min = round(len(en_track)/60000, 1)
    print("  [EN] Duration: " + str(en_min) + " min")

    # Chinese track
    print("  [CN] Generating Chinese voice track...")
    cn_track = generate_voice_track(chinese_script, tts_cn, tmpdir, "cn")
    cn_min = round(len(cn_track)/60000, 1)
    print("  [CN] Duration: " + str(cn_min) + " min")

    # Bridge between languages
    bridge = make_language_bridge()

    # Full voice content
    voice_content = en_track + bridge + cn_track
    total_ms = len(voice_content)

    # Music bookends
    intro = make_news_intro(7000)
    outro = make_outro(5000)
    full_ms = len(intro) + total_ms + len(outro)

    # Background ambient
    background = make_news_background(full_ms)
    foreground = intro + voice_content + outro
    final = foreground.overlay(background)

    peak = final.max_dBFS
    if peak < -3:
        final = final.apply_gain(-3 - peak)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final.export(output_path, format="mp3", bitrate="128k")
    size = os.path.getsize(output_path)
    total_min = round(total_ms/60000, 1)
    print("  Final: EN " + str(en_min) + "min + CN " + str(cn_min) + "min = " + str(total_min) + "min total, " + str(round(size/1024/1024, 1)) + " MB")
    return size

def update_rss_feed(run_date, session, audio_filename, audio_size, episode_title):
    feed_path = "docs/feed.xml"
    pub_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    audio_url = PAGES_BASE + "/audio/" + audio_filename
    items_xml = ""
    if os.path.exists(feed_path):
        try:
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
        "<description>TCL Market Intelligence " + ("Morning Briefing" if session=="morning" else "Evening Update") + " - Real news from HospitalityNet, Hotel Management, Skift and more.</description>"
        "<enclosure url=\"" + audio_url + "\" length=\"" + str(audio_size) + "\" type=\"audio/mpeg\"/>"
        "<pubDate>" + pub_date + "</pubDate>"
        "<guid>" + audio_url + "?v=" + run_date[:10].replace("-","") + "</guid>"
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
        "<description>Daily hospitality TV and commercial display market intelligence. Real news from industry sources. MEA and LATAM BD briefing.</description>"
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

def build_html_email(sections, articles, run_date, session, has_audio, pipeline_html=""):
    total = sum(len(s.get("items",[])) for s in sections)
    label = "Morning Briefing" if session == "morning" else "Evening Update"
    source_list = list(set(a["source"] for a in articles))
    sources_str = ", ".join(source_list[:5])
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='margin:0;padding:20px;background:#eef1f5;font-family:Arial,sans-serif;'>"
        "<div style='max-width:760px;margin:auto;'>"
        "<div style='background:#0d1b2a;padding:28px 32px;border-radius:10px 10px 0 0;'>"
        "<h1 style='color:#fff;margin:0 0 4px;font-size:20px;'>TCL Market Intelligence</h1>"
        "<p style='color:#7eb8f7;margin:0;font-size:13px;'>" + label + " - Real news from " + sources_str + "</p>"
        "<div style='margin-top:16px;'>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + run_date[:10] + "</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + str(len(articles)) + " real articles</span>"
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;margin-right:8px;'>" + str(total) + " insights</span>"
        + ("<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>🎙️ Audio ready</span>" if has_audio else "") +
        "</div></div>"
        "<div style='background:#fff;padding:8px 32px 32px;border:1px solid #dde;border-top:none;border-radius:0 0 10px 10px;'>"
    )
    # Real articles section
    html += (
        "<div style='padding-top:24px;'>"
        "<h2 style='font-size:13px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px;'>Real News Sources Today</h2>"
    )
    for a in articles[:8]:
        html += (
            "<div style='margin-bottom:8px;padding:10px 14px;background:#f8f9fa;border-radius:6px;border-left:3px solid #7eb8f7;'>"
            "<a href='" + a.get("link","#") + "' style='font-size:13px;font-weight:600;color:#0d1b2a;text-decoration:none;'>" + a["title"] + "</a>"
            "<span style='font-size:11px;color:#999;margin-left:8px;'>" + a["source"] + " · " + a["pub"] + "</span>"
            "</div>"
        )
    html += "</div>"
    # Analysis sections
    for s in sections:
        html += (
            "<div style='padding-top:24px;'>"
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
    # Inject pipeline report (AM only)
    if pipeline_html:
        html += pipeline_html

    html += (
        "<div style='margin-top:36px;padding-top:20px;border-top:1px solid #eee;text-align:center;'>"
        "<p style='font-size:11px;color:#aaa;line-height:1.8;margin:0;'>"
        "TCL Global Engineering Business Center<br>"
        "MEA: UAE, Saudi Arabia, Turkey | LATAM: Brazil, Colombia, Peru, Panama, Chile"
        "</p></div></div></body></html>"
    )
    return html

def build_markdown(sections, articles, run_date, session):
    label = "Morning Briefing" if session == "morning" else "Evening Update"
    lines = ["# TCL Market Intelligence - " + label + " " + run_date[:10], ""]
    lines.append("## Real News Sources")
    for a in articles[:10]:
        lines.append("- [" + a["title"] + "](" + a.get("link","") + ") — " + a["source"] + " " + a["pub"])
    lines.append("")
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

    print("\n[1/5] Fetching real news from industry RSS sources...")
    articles = fetch_all_news()

    # Load pipeline report (AM only)
    pipeline_html = ""
    pipeline_md = ""
    if SESSION == "morning":
        try:
            import importlib.util, os as _os
            spec = importlib.util.spec_from_file_location(
                "pipeline_report",
                _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "pipeline_report.py")
            )
            pr = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pr)
            pipeline_html, pipeline_md = pr.get_pipeline_report()
        except Exception as e:
            print("  Pipeline skipped: " + str(e)[:80])

    print("\n[2/5] Analyzing with Claude...")
    sections = []
    if articles:
        try:
            news_context = build_news_context(articles)
            raw = call_api(get_analysis_prompt(news_context, SESSION), max_tokens=1500)
            sections = extract_sections(raw)
            print("  Sections: " + str(len(sections)) + " | Insights: " + str(sum(len(s.get("items",[])) for s in sections)))
        except Exception as e:
            print("  ERROR: " + str(e))

    print("\n[3/5] Writing broadcast script...")
    broadcast_script = ""
    if sections:
        try:
            raw_script = call_api(get_broadcast_prompt(sections, articles, SESSION), max_tokens=1800)
            broadcast_script = extract_text(raw_script)
            print("  Script: " + str(len(broadcast_script)) + " chars")
        except Exception as e:
            print("  Script error: " + str(e))

    print("\n[4/5] Generating broadcast audio...")
    has_audio = False
    audio_size = 0
    ts = datetime.datetime.utcnow().strftime("%H%M")
    audio_filename = "tcl_" + ("am" if SESSION=="morning" else "pm") + "_" + run_date[:10].replace("-","") + "_" + ts + ".mp3"
    audio_path = "docs/audio/" + audio_filename

    # Generate Chinese broadcast script
    chinese_script = ""
    if broadcast_script:
        print("\n[3.5/5] Translating to Chinese broadcast script...")
        try:
            raw_cn = call_api(get_chinese_broadcast_prompt(broadcast_script, SESSION), max_tokens=1800)
            chinese_script = extract_text(raw_cn)
            print("  Chinese script: " + str(len(chinese_script)) + " chars")
        except Exception as e:
            print("  Chinese script error: " + str(e))

    if broadcast_script:
        try:
            audio_size = generate_full_audio(broadcast_script, chinese_script, audio_path)
            has_audio = audio_size > 0
            if has_audio:
                episode_title = "TCL Market Intel [" + ("AM" if SESSION=="morning" else "PM") + "] - " + run_date[:10]
                update_rss_feed(run_date, SESSION, audio_filename, audio_size, episode_title)
        except Exception as e:
            print("  Audio error: " + str(e))

    print("\n[5/5] Sending email...")
    md   = build_markdown(sections, articles, run_date, SESSION)
    html = build_html_email(sections, articles, run_date, SESSION, has_audio, pipeline_html)
    if pipeline_md:
        md = md + chr(10) + chr(10) + pipeline_md
    save_markdown(md, run_date, SESSION)
    send_email(html, md, run_date, SESSION)

    # Sync to Notion
    print("\n[5.5/5] Syncing to Notion...")
    try:
        import importlib.util as _ilu, os as _os
        _spec = _ilu.spec_from_file_location(
            "notion_sync",
            _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "notion_sync.py")
        )
        _ns = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_ns)
        _ns.run(sections, articles, SESSION, run_date)
    except Exception as e:
        print("  Notion sync skipped: " + str(e)[:80])

    print("\nDone.")

if __name__ == "__main__":
    main()
