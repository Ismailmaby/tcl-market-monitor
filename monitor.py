import os, json, smtplib, datetime, urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER    = os.environ["GMAIL_USER"]
GMAIL_PASS    = os.environ["GMAIL_PASS"]
RECIPIENT     = os.environ.get("RECIPIENT", GMAIL_USER)
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
API_BASE      = "https://lanyiapi.com"
MODEL         = "claude-sonnet-4-6"

def get_prompt():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return (
        "You are a market intelligence analyst for TCL hospitality TV and commercial display, "
        "covering MEA (UAE, Saudi Arabia, Turkey) and LATAM (Brazil, Colombia, Peru, Panama, Chile). "
        "Today is " + today + ". "
        "Use web search to find real news from the past 48 hours. "
        "Search for: hotel openings MEA LATAM, Samsung LYNK LG ProCentric hospitality TV news, "
        "IPTV middleware hotel technology, Marriott Hilton Accor IHG expansion, "
        "hotel construction pipeline UAE Saudi Brazil. "
        "Return ONLY valid JSON, no other text:\n"
        '{"sections":['
        '{"title":"MEA Hotel Market","items":[{"headline":"...","insight":"...","source":"...","action":"..."}]},'
        '{"title":"LATAM Hotel Market","items":[{"headline":"...","insight":"...","source":"...","action":"..."}]},'
        '{"title":"Competitive Intelligence","items":[{"headline":"...","insight":"...","source":"...","action":"..."}]},'
        '{"title":"Hospitality Technology","items":[{"headline":"...","insight":"...","source":"...","action":"..."}]},'
        '{"title":"BD Opportunities","items":[{"headline":"...","insight":"...","source":"...","action":"..."}]}'
        "]}\n"
        "Each section needs 3 items based on REAL news found via web search. "
        "Include source name for each item. Only real verified information."
    )

def call_api(prompt, api_key):
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        API_BASE + "/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
            "content-type": "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

def extract_sections(response):
    text = ""
    for block in response.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        print("  [WARN] No JSON: " + text[:300])
        return []
    try:
        data = json.loads(text[start:end])
        return data.get("sections", [])
    except Exception as e:
        print("  [WARN] Parse error: " + str(e)[:60])
        return []

def build_html_email(sections, run_date):
    total = sum(len(s.get("items", [])) for s in sections)
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
        "<span style='background:rgba(255,255,255,0.1);color:#cde;padding:5px 12px;border-radius:20px;font-size:12px;'>Real news via web search</span>"
        "</div></div>"
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
                + ("<p style='font-size:11px;color:#999;margin:4px 0;'>Source: " + item["source"] + "</p>" if item.get("source") else "")
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
            if item.get("source"):
                lines.append("Source: " + item["source"])
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

def main():
    run_date = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print("TCL Market Monitor - " + run_date)
    print("API: " + API_BASE + " | Model: " + MODEL + " | Web search: ON")
    try:
        response = call_api(get_prompt(), ANTHROPIC_KEY)
        sections = extract_sections(response)
        total = sum(len(s.get("items", [])) for s in sections)
        print("Sections: " + str(len(sections)) + " | Insights: " + str(total))
    except Exception as e:
        print("ERROR: " + str(e))
        sections = []
    html = build_html_email(sections, run_date)
    md   = build_markdown(sections, run_date)
    save_markdown(md, run_date)
    send_email(html, md, run_date)
    print("Done.")

if __name__ == "__main__":
    main()
