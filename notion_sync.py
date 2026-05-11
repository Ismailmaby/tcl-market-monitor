import os, json, datetime, urllib.request

NOTION_KEY   = os.environ.get("NOTION_API_KEY", "")
ANTHROPIC_KEY= os.environ.get("ANTHROPIC_API_KEY", "")
INTEL_DB_ID  = "b33ca76c-ad01-44be-9bd7-8ce81f341c13"
API_BASE     = "https://lanyiapi.com"
MODEL        = "claude-sonnet-4-6"

def notion_create_page(parent_db_id, properties, children):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": parent_db_id},
        "properties": properties,
        "children": children
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + NOTION_KEY,
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def notion_append_blocks(page_id, blocks):
    url = "https://api.notion.com/v1/blocks/" + page_id + "/children"
    req = urllib.request.Request(
        url, data=json.dumps({"children": blocks}).encode(),
        headers={
            "Authorization": "Bearer " + NOTION_KEY,
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

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
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
        text = ""
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return text.strip()

def translate_to_chinese_report(sections, articles, session, run_date):
    session_label = "早报" if session == "morning" else "晚报"
    date_str = datetime.datetime.utcnow().strftime("%Y年%m月%d日")

    # Build content summary
    content = ""
    for s in sections:
        content += "\n【" + s.get("title","") + "】\n"
        for item in s.get("items",[]):
            content += "- " + item.get("headline","") + "\n"
            content += "  分析：" + item.get("insight","") + "\n"
            content += "  行动：" + item.get("action","") + "\n"

    news_list = "\n".join(["- " + a["title"] + "（" + a["source"] + "）" for a in articles[:10]])

    prompt = (
        "你是TCL泛智屏BU的市场情报分析师。请将以下市场情报内容整理成中文深度分析报告。\n\n"
        "日期：" + date_str + "，" + session_label + "\n"
        "目标读者：TCL MEA和LATAM区域的Key Account BD经理\n\n"
        "要求：\n"
        "1. 每个板块用中文展开，150-200字\n"
        "2. 结合TCL的业务场景分析市场机会\n"
        "3. 明确指出对Samsung LYNK和LG ProCentric的竞争机会\n"
        "4. 每个洞察后附上具体的BD行动建议\n"
        "5. 语言专业、简洁、可直接用于内部汇报\n"
        "6. 不提及具体客户名称\n\n"
        "原始情报内容：\n" + content + "\n\n"
        "今日新闻来源：\n" + news_list + "\n\n"
        "请按以下结构输出（使用markdown格式）：\n\n"
        "## 今日要点概述\n（3-4句话总结最重要的市场信号）\n\n"
        "## 一、MEA酒店市场动态\n（深度展开，含竞争机会和BD行动）\n\n"
        "## 二、LATAM酒店市场动态\n（深度展开，巴西为重点）\n\n"
        "## 三、竞品格局分析\n（Samsung LYNK和LG ProCentric的弱点及TCL切入点）\n\n"
        "## 四、酒店科技趋势\n（IPTV中间件、Android TV、智能客房）\n\n"
        "## 五、本周BD行动优先级\n（按优先级排列，可直接执行）\n\n"
        "## 今日新闻速览\n（用一两句话总结今日抓取的真实新闻要点）"
    )
    return call_api(prompt, max_tokens=1800)

def markdown_to_notion_blocks(md_text, session, run_date, articles):
    blocks = []
    session_label = "早报 🌅" if session == "morning" else "晚报 🌆"
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Header callout
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content":
                "TCL市场情报 " + session_label + " | " + run_date[:10] + " | 生成时间：" + generated_at
            }}],
            "icon": {"emoji": "📡"},
            "color": "blue_background"
        }
    })

    # News sources
    if articles:
        source_text = "今日新闻来源：" + " · ".join(list(set(a["source"] for a in articles[:10])))
        blocks.append({
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": [{"type": "text", "text": {"content": source_text}}],
                "color": "gray_background"
            }
        })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # Parse markdown
    lines = md_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[3:]}}],
                    "color": "default",
                    "is_toggleable": True
                }
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]
                }
            })
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                }
            })
        elif stripped.startswith("1.") or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == "."):
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:].strip()}}]
                }
            })
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                }
            })
        else:
            # Bold detection
            rich_text = []
            parts = stripped.split("**")
            for i, part in enumerate(parts):
                if part:
                    rich_text.append({
                        "type": "text",
                        "text": {"content": part},
                        "annotations": {"bold": i % 2 == 1}
                    })
            if rich_text:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text}
                })

    return blocks

def sync_report_to_notion(sections, articles, session, run_date):
    today = run_date[:10]
    session_label = "早报" if session == "morning" else "晚报"
    title = "📊 " + today + " " + session_label + " | TCL市场情报"
    article_count = len(articles)

    print("  Translating to Chinese report...")
    chinese_report = translate_to_chinese_report(sections, articles, session, run_date)
    print("  Chinese report: " + str(len(chinese_report)) + " chars")

    # Build Notion blocks
    blocks = markdown_to_notion_blocks(chinese_report, session, run_date, articles)

    # Create page properties
    properties = {
        "标题": {"title": [{"text": {"content": title}}]},
        "日期": {"date": {"start": today}},
        "场次": {"select": {"name": session_label}},
        "市场": {"select": {"name": "MEA+LATAM"}},
        "文章数": {"number": article_count},
        "状态": {"select": {"name": "已同步"}},
    }

    # Create page with first 100 blocks
    first_batch = blocks[:90]
    page = notion_create_page(INTEL_DB_ID, properties, first_batch)
    page_id = page["id"]
    print("  Page created: " + page_id)

    # Append remaining blocks in batches
    if len(blocks) > 90:
        for i in range(90, len(blocks), 90):
            notion_append_blocks(page_id, blocks[i:i+90])

    print("  Synced to Notion: " + title)
    return page_id

def run(sections, articles, session, run_date):
    print("\nNotion Sync - " + session + " - " + run_date[:10])
    if not sections:
        print("  No sections to sync")
        return
    try:
        page_id = sync_report_to_notion(sections, articles, session, run_date)
        print("  Done: https://notion.so/" + page_id.replace("-",""))
    except Exception as e:
        print("  Sync error: " + str(e))

if __name__ == "__main__":
    print("notion_sync.py - run via monitor.py")
