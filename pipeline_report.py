import os, json, datetime, urllib.request

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NOTION_KEY    = os.environ.get("NOTION_API_KEY", "")
DB_ID         = "2b575a08-7008-80ec-b85e-000b8464936d"

# LTC漏斗阶段定义
FUNNEL_STAGES = {
    "未接触":  {"stage": "L",   "label": "线索",     "emoji": "⚪", "order": 1},
    "已建联":  {"stage": "L→T", "label": "线索→机会", "emoji": "🔵", "order": 2},
    "跟进中":  {"stage": "T",   "label": "机会",     "emoji": "🟡", "order": 3},
    "有意向":  {"stage": "T→C", "label": "机会→合同", "emoji": "🟠", "order": 4},
    "暂无需求":{"stage": "暂停", "label": "暂停",     "emoji": "⚫", "order": 5},
    "已失败":  {"stage": "丢单", "label": "丢单",     "emoji": "🔴", "order": 6},
}

def fetch_notion_customers():
    url = "https://api.notion.com/v1/databases/" + DB_ID + "/query"
    payload = json.dumps({
        "filter": {
            "property": "行业分类",
            "select": {"equals": "酒店"}
        },
        "sorts": [
            {"property": "客户级别", "direction": "ascending"},
            {"property": "下次跟进日期", "direction": "ascending"}
        ],
        "page_size": 100
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": "Bearer " + NOTION_KEY,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def parse_customers(data):
    customers = []
    today = datetime.date.today()
    for page in data.get("results", []):
        props = page.get("properties", {})

        def get_select(key):
            s = props.get(key, {}).get("select")
            return s["name"] if s else ""

        def get_text(key):
            t = props.get(key, {}).get("rich_text", [])
            return t[0]["plain_text"] if t else ""

        def get_title(key):
            t = props.get(key, {}).get("title", [])
            return t[0]["plain_text"] if t else ""

        def get_date(key):
            d = props.get(key, {}).get("date")
            return d["start"] if d else ""

        name     = get_title("客户名称")
        status   = get_select("沟通状态")
        level    = get_select("客户级别")
        region   = get_select("区域")
        city     = get_text("城市")
        contact  = get_text("联系人")
        notes    = get_text("备注")
        followup = get_date("下次跟进日期")
        ctype    = get_select("客户类型")

        # Days until follow-up
        days_until = None
        overdue = False
        if followup:
            try:
                fu_date = datetime.date.fromisoformat(followup)
                days_until = (fu_date - today).days
                overdue = days_until < 0
            except Exception:
                pass

        funnel = FUNNEL_STAGES.get(status, {"stage": "?", "label": status, "emoji": "⚪", "order": 9})

        customers.append({
            "name": name,
            "status": status,
            "level": level,
            "region": region,
            "city": city,
            "contact": contact,
            "notes": notes,
            "followup": followup,
            "days_until": days_until,
            "overdue": overdue,
            "type": ctype,
            "funnel_stage": funnel["stage"],
            "funnel_label": funnel["label"],
            "funnel_emoji": funnel["emoji"],
            "funnel_order": funnel["order"],
        })

    return sorted(customers, key=lambda x: (x["funnel_order"], x["level"] or ""))

def build_pipeline_html(customers):
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Pipeline stats
    active = [c for c in customers if c["status"] not in ["暂无需求", "已失败"]]
    by_stage = {}
    for c in active:
        stage = c["funnel_label"]
        by_stage.setdefault(stage, []).append(c)

    # Urgent: overdue or due within 3 days
    urgent = [c for c in active if c["days_until"] is not None and c["days_until"] <= 3]
    urgent.sort(key=lambda x: x["days_until"] if x["days_until"] is not None else 99)

    # By region
    mea    = [c for c in active if c["region"] in ["阿联酋","沙特阿拉伯","土耳其","埃及","卡塔尔","科威特"]]
    latam  = [c for c in active if c["region"] in ["巴西","哥伦比亚","秘鲁","智利","阿根廷","巴拿马"]]

    html = """
<div style='background:#fff;border:1px solid #dde;border-radius:10px;margin-top:24px;overflow:hidden;'>

  <!-- Pipeline Header -->
  <div style='background:#0d1b2a;padding:20px 28px;'>
    <h2 style='color:#fff;margin:0 0 4px;font-size:16px;font-weight:700;'>📊 Sales Pipeline — LTC Funnel</h2>
    <p style='color:#7eb8f7;margin:0;font-size:12px;'>""" + today_str + """ · """ + str(len(active)) + """ active accounts · Notion sync</p>
  </div>

  <div style='padding:20px 28px;'>

    <!-- Funnel Summary -->
    <div style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;'>"""

    funnel_order = ["线索", "线索→机会", "机会", "机会→合同"]
    funnel_colors = {"线索":"#95a5a6","线索→机会":"#3498db","机会":"#f39c12","机会→合同":"#e67e22"}
    for stage_label in funnel_order:
        count = len(by_stage.get(stage_label, []))
        color = funnel_colors.get(stage_label, "#999")
        html += f"""
      <div style='flex:1;min-width:80px;padding:12px;background:#f8f9fa;border-radius:8px;border-top:3px solid {color};text-align:center;'>
        <div style='font-size:22px;font-weight:700;color:{color};'>{count}</div>
        <div style='font-size:11px;color:#666;margin-top:2px;'>{stage_label}</div>
      </div>"""

    html += "\n    </div>"

    # Urgent actions
    if urgent:
        html += """
    <div style='background:#fff8f0;border:1px solid #f39c12;border-radius:8px;padding:14px;margin-bottom:20px;'>
      <p style='font-size:13px;font-weight:700;color:#e67e22;margin:0 0 10px;'>⚡ Urgent Follow-ups</p>"""
        for c in urgent:
            if c["overdue"]:
                tag = f"<span style='color:#e74c3c;font-weight:700;'>OVERDUE {abs(c['days_until'])}d</span>"
            elif c["days_until"] == 0:
                tag = "<span style='color:#e67e22;font-weight:700;'>TODAY</span>"
            else:
                tag = f"<span style='color:#f39c12;font-weight:700;'>in {c['days_until']}d</span>"

            html += f"""
      <div style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #fde;'>
        <span style='font-size:13px;font-weight:600;color:#0d1b2a;'>{c['funnel_emoji']} {c['name']}</span>
        <span style='font-size:12px;color:#666;'>{c['region']} · {c['type']} · {tag}</span>
      </div>"""
        html += "\n    </div>"

    # MEA Pipeline
    if mea:
        html += """
    <div style='margin-bottom:16px;'>
      <h3 style='font-size:13px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;padding-bottom:6px;margin:0 0 10px;'>🌍 MEA Pipeline</h3>"""
        for c in mea:
            notes_short = c["notes"][:80] + "..." if len(c["notes"]) > 80 else c["notes"]
            fu_str = f"Follow-up: {c['followup']}" if c["followup"] else ""
            html += f"""
      <div style='padding:10px 12px;background:#f8f9fa;border-radius:6px;border-left:3px solid #e63946;margin-bottom:8px;'>
        <div style='display:flex;justify-content:space-between;align-items:center;'>
          <span style='font-size:13px;font-weight:600;color:#0d1b2a;'>{c['funnel_emoji']} {c['name']}</span>
          <span style='font-size:11px;color:#888;'>{c['level']} · {c['type']}</span>
        </div>
        <div style='font-size:12px;color:#666;margin-top:4px;'>{c['funnel_label']} · {c['city']} · {fu_str}</div>
        {'<div style="font-size:12px;color:#555;margin-top:4px;">' + notes_short + '</div>' if notes_short else ''}
      </div>"""
        html += "\n    </div>"

    # LATAM Pipeline
    if latam:
        html += """
    <div style='margin-bottom:8px;'>
      <h3 style='font-size:13px;font-weight:700;color:#0d1b2a;border-bottom:2px solid #e63946;padding-bottom:6px;margin:0 0 10px;'>🌎 LATAM Pipeline</h3>"""
        for c in latam:
            notes_short = c["notes"][:80] + "..." if len(c["notes"]) > 80 else c["notes"]
            fu_str = f"Follow-up: {c['followup']}" if c["followup"] else ""
            html += f"""
      <div style='padding:10px 12px;background:#f8f9fa;border-radius:6px;border-left:3px solid #7eb8f7;margin-bottom:8px;'>
        <div style='display:flex;justify-content:space-between;align-items:center;'>
          <span style='font-size:13px;font-weight:600;color:#0d1b2a;'>{c['funnel_emoji']} {c['name']}</span>
          <span style='font-size:11px;color:#888;'>{c['level']} · {c['type']}</span>
        </div>
        <div style='font-size:12px;color:#666;margin-top:4px;'>{c['funnel_label']} · {c['city']} · {fu_str}</div>
        {'<div style="font-size:12px;color:#555;margin-top:4px;">' + notes_short + '</div>' if notes_short else ''}
      </div>"""
        html += "\n    </div>"

    html += "\n  </div>\n</div>"
    return html

def build_pipeline_markdown(customers):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    active = [c for c in customers if c["status"] not in ["暂无需求", "已失败"]]

    lines = [
        "## 📊 Sales Pipeline — " + today_str,
        f"Active accounts: {len(active)}",
        "",
    ]

    for stage_label in ["线索", "线索→机会", "机会", "机会→合同"]:
        stage_customers = [c for c in active if c["funnel_label"] == stage_label]
        if stage_customers:
            lines.append(f"### {stage_label} ({len(stage_customers)})")
            for c in stage_customers:
                fu = f" | Follow-up: {c['followup']}" if c["followup"] else ""
                lines.append(f"- {c['funnel_emoji']} **{c['name']}** — {c['region']} · {c['type']}{fu}")
                if c["notes"]:
                    lines.append(f"  {c['notes'][:100]}")
            lines.append("")

    return "\n".join(lines)

def get_pipeline_report():
    try:
        data = fetch_notion_customers()
        customers = parse_customers(data)
        html = build_pipeline_html(customers)
        md   = build_pipeline_markdown(customers)
        print("  Pipeline: " + str(len(customers)) + " customers loaded")
        return html, md
    except Exception as e:
        print("  Pipeline error: " + str(e))
        return "", ""

if __name__ == "__main__":
    # Test run
    html, md = get_pipeline_report()
    print(md)
