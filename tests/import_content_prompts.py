import json
import re
import sys
import sqlite3
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "prompts.db"
JSON_PATH = Path(r"C:\Users\Windows\.gemini\antigravity\brain\56f6a51b-4231-407f-a5c5-cc174b4c3fb6\scratch\input_content_prompts.json")

def get_clean_tags(group: str, name: str, prompt_text: str):
    tags = set()
    grp_upper = group.upper()

    # Nhóm number tag
    grp_match = re.search(r'NHÓM\s*(\d+)', grp_upper)
    if grp_match:
        tags.add(f"Nhóm {grp_match.group(1)}")

    # Core functional group tags
    if "VIẾT CONTENT" in grp_upper:
        tags.add("Viết Content")
    if "KỊCH BẢN VIDEO" in grp_upper:
        tags.add("Kịch bản Video")
    if "CHỌN & NGHIÊN CỨU" in grp_upper or "NGHIÊN CỨU SẢN PHẨM" in grp_upper:
        tags.add("Nghiên cứu Sản phẩm")
        tags.add("Chọn Sản phẩm")
    if "TẠO HÌNH ẢNH" in grp_upper or "VISUAL" in grp_upper:
        tags.add("Hình ảnh & Visual")
    if "TẠO VIDEO AI" in grp_upper:
        tags.add("Video AI")
    if "TỐI ƯU" in grp_upper or "PHÂN TÍCH" in grp_upper:
        tags.add("Tối ưu & Phân tích")
    if "TỰ ĐỘNG HÓA" in grp_upper or "NÂNG CAO" in grp_upper:
        tags.add("Tự động hóa")
        tags.add("Nâng cao")
    if "TEEDOO" in grp_upper:
        tags.add("Ngành Sách")
        tags.add("Thực chiến TEEDOO")
        tags.add("Teedoo")

    # Content & Tool rules
    full_text = f"{name} {prompt_text}".lower()
    rules = [
        ("TikTok", ["tiktok", "tiktok shop"]),
        ("YouTube", ["youtube", "shorts"]),
        ("Facebook", ["facebook", "fanpage", "fb feed"]),
        ("Shopee", ["shopee", "shopee mall"]),
        ("Veo 3", ["veo 3", "veo3"]),
        ("Sora", ["sora"]),
        ("HeyGen", ["heygen"]),
        ("Kling", ["kling"]),
        ("Grok", ["grok"]),
        ("Midjourney", ["midjourney"]),
        ("Gemini", ["gemini"]),
        ("Canva", ["canva"]),
        ("Alex Hormozi", ["hormozi", "grand slam offer"]),
        ("AIDA", ["aida"]),
        ("PAS", ["pas", "problem-agitate-solution"]),
        ("SEO", ["seo", "từ khóa seo"]),
        ("Review", ["review", "đánh giá", "unbox", "unboxing"]),
        ("Hook", ["hook", "câu mở đầu", "dừng scroll"]),
        ("KOC", ["koc", "ugc", "không lộ mặt"]),
        ("Affiliate", ["affiliate", "tiếp thị liên kết", "hoa hồng"]),
        ("Vlog", ["vlog", "day in my life"]),
        ("Thumbnail", ["thumbnail", "ảnh bìa", "cover photo"]),
        ("Bán Sách", ["sách", "lollibooks", "bản thảo", "đọc sách"]),
        ("Storytelling", ["storytelling", "tứ hóa", "kể chuyện"]),
        ("Kịch bản Video", ["kịch bản", "script", "voiceover", "phân cảnh"]),
    ]

    for tag_name, keywords in rules:
        if any(kw in full_text for kw in keywords):
            tags.add(tag_name)

    return sorted(list(tags))

def extract_prompt_fields(prompt_text: str):
    fields = []
    seen = set()

    # Pattern 1: Lines like "- Sản phẩm: [tên sản phẩm]"
    line_pattern = re.compile(r'^[ \t]*[-*•]?[ \t]*([A-Za-zÀ-ỹ0-9\s/_\-–]+)[ \t]*[:=][ \t]*(\[[^\[\]\n\r]{2,80}\])', re.M)
    for match in line_pattern.finditer(prompt_text):
        label = match.group(1).strip()
        raw_ph = match.group(2).strip()
        ph_inner = raw_ph.strip('[]').strip()

        label_clean = re.sub(r'^(Thông tin|Yêu cầu|Input|Dữ liệu đầu vào|Cấu trúc)\s*', '', label, flags=re.I).strip()
        if not label_clean or len(label_clean) < 2 or len(label_clean) > 50:
            label_clean = ph_inner.split(',')[0].split('/')[0].strip()

        if raw_ph not in seen:
            seen.add(raw_ph)
            field_key = re.sub(r'[^a-zA-Z0-9_]', '_', label_clean.lower()).strip('_')[:40]
            if not field_key: field_key = f"param_{len(fields)+1}"
            fields.append({
                "path": raw_ph,
                "key": field_key,
                "label": label_clean.title() if not label_clean.isupper() else label_clean,
                "default": ph_inner,
                "type": "text"
            })

    # Pattern 2: Input: [SẢN PHẨM], [TARGET]
    input_line_match = re.search(r'Input:[ \t]*([^\n\r]+)', prompt_text, re.I)
    if input_line_match:
        items = re.findall(r'(\[[A-Za-zÀ-ỹ0-9\s/_\-–+]+\])', input_line_match.group(1))
        for item in items:
            if item not in seen:
                seen.add(item)
                inner = item.strip('[]').strip()
                label = inner.split('+')[0].split('/')[0].strip()
                field_key = re.sub(r'[^a-zA-Z0-9_]', '_', label.lower()).strip('_')[:40]
                fields.append({
                    "path": item,
                    "key": field_key,
                    "label": label,
                    "default": inner,
                    "type": "text"
                })

    # Pattern 3: Remaining placeholders
    all_brackets = re.findall(r'(\[[A-Za-zÀ-ỹ0-9\s/_\-–,"\'’+]{2,60}\])', prompt_text)
    for b in all_brackets:
        if b in seen: continue
        inner = b.strip('[]').strip()
        if any(inner.lower().startswith(sk) for sk in ['dán', 'upload file', 'hình ảnh:', 'lưu ý', 'http']):
            continue
        if len(inner) <= 40 and not re.match(r'^\d', inner):
            seen.add(b)
            label = inner.split(',')[0].split('/')[0].split('(')[0].strip()
            field_key = re.sub(r'[^a-zA-Z0-9_]', '_', label.lower()).strip('_')[:40]
            if not field_key: field_key = f"field_{len(fields)+1}"
            fields.append({
                "path": b,
                "key": field_key,
                "label": label.title() if not label.isupper() else label,
                "default": inner,
                "type": "text"
            })

    return fields

def run_import():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        prompts_data = json.load(f)

    print(f"Loaded {len(prompts_data)} prompts from JSON.")

    # Get highest original_index for character prompts to maintain nice indexing
    cursor.execute("SELECT MAX(original_index) FROM prompts WHERE category = 'character'")
    row = cursor.fetchone()
    base_index = (row[0] or 340)

    # Delete existing content category prompts if any to ensure fresh clean state
    cursor.execute("SELECT id FROM prompts WHERE category = 'content'")
    existing_content_ids = [r[0] for r in cursor.fetchall()]
    if existing_content_ids:
        print(f"Removing {len(existing_content_ids)} existing content prompt(s) for clean reload...")
        for cid in existing_content_ids:
            cursor.execute("DELETE FROM prompt_fields WHERE prompt_id = ?", (cid,))
            cursor.execute("DELETE FROM prompt_tags WHERE prompt_id = ?", (cid,))
            cursor.execute("DELETE FROM sample_contents WHERE prompt_id = ?", (cid,))
            cursor.execute("DELETE FROM prompts WHERE id = ?", (cid,))
        conn.commit()

    sample_content_seeds = {
        "content_1": """[00:00 - 00:03] HOOK:
(Cận cảnh mặt KOC biểu cảm sốc, tay cầm sản phẩm)
"Đừng có dại mà mua chai Serum Niacinamide này nếu bạn không muốn vết thâm mụn biến mất sạch sẽ sau đúng 14 ngày!"

[00:03 - 00:15] STORY - NỖI ĐAU:
(Hình ảnh da thâm cũ & ánh mắt mệt mỏi)
"Trước đây cứ hết mụn là mặt tui chi chít thâm đỏ, thâm đen. Thử bao nhiêu loại treatment đắt tiền mà da vừa rát vừa bí rít, trầm cảm thực sự luôn."

[00:15 - 00:35] STORY - GIẢI PHÁP:
(Cảnh thoa serum lên da, texture tan nhanh mát mịn)
"Cho đến khi đổi sang em serum Niacinamide 10% kết hợp ZinC này. Kết cấu lỏng nhẹ như nước, thoa 5 giây là ráo mịn, kiềm dầu cực đỉnh mà êm ru không châm chích xíu nào."

[00:35 - 00:50] KẾT QUẢ:
(Gương mặt rạng rỡ dưới ánh nắng tự nhiên)
"Sau 2 tuần kiên trì sáng tối, thâm mờ hẳn 80%, da sáng đều màu và mịn màng rõ rệt."

[00:50 - 00:60] CTA:
"Hôm nay trong giỏ hàng TikTok Shop đang trợ giá giảm 30% kèm quà mini size. Bấm ngay góc trái màn hình rinh deal hời nha cả nhà!" """,
        
        "content_2": """Tôi đã dùng chiếc máy cạo râu mini này liên tục 30 ngày, và đây là review chân thực 100% không nói quá.

1. Unbox & Ấn tượng đầu tiên:
Máy nhỏ gọn đúng bằng quả trứng gà, vỏ kim loại cầm đầm tay, cổng sạc Type-C siêu tiện dùng chung sạc điện thoại.

2. Trải nghiệm thực tế (Ưu điểm):
- Lưỡi dao 3 cánh tự mài bén ngót, cạo sát chân râu mà không bị rát da hay xước da như dao cạo truyền thống.
- Chống nước IPX7 nên rửa trực tiếp dưới vòi nước cực kỳ nhanh gọn.
- Pin trâu: Sạc 1 lần dùng cả tháng trời không cần cắm lại.

3. Điểm trừ nhỏ:
Hộp đựng hơi đơn giản, và tiếng motor hơi rè nhẹ khi pin dưới 20%.

4. Kết luận:
Với mức giá chỉ hơn 200K, đây chắc chắn là món đồ không thể thiếu trong balo của anh em hay đi công tác, du lịch. Link chính hãng bảo hành 12 tháng mình để góc dưới màn hình nhé!""",

        "content_4": """3 lý do tại sao mẫu nồi chiên không dầu mini này đang cháy hàng liên tục trên các sàn thương mại điện tử:

👉 Lý do 1: Giải quyết triệt để nỗi sợ dầu mỡ ám mùi
Dung tích 3.5L vừa vặn cho 1-2 người, nướng gà giòn rụm trong 15 phút mà giảm tới 85% chất béo. Căn hộ nhỏ không lo mùi chiên rán bám rèm cửa hay quần áo.

👉 Lý do 2: Tiết kiệm điện & dễ rửa gấp 3 lần chảo thường
Khay nướng phủ men Ceramic chống dính cao cấp, ăn xong chỉ cần xả nước ấm 30 giây là sạch bóng, không phải cọ rửa dầu mỡ cực nhọc.

👉 Lý do 3: Hơn 15.000 lượt đánh giá 4.9 sao
Hàng nghìn feedback khen ngợi độ bền và khả năng giữ nhiệt đều tuyệt đối.

Link ưu đãi độc quyền hôm nay đang giảm 35% mình gắn ngay tại Bio / Giỏ hàng bên dưới, nhanh tay săn kẻo hết mã voucher nhé!""",

        "content_11": """Bạn có bao giờ thức dậy và cảm thấy đau nhức vai gáy dữ dội vì chiếc gối ngủ sai tư thế?

❌ NỖI ĐAU (PROBLEM):
Ngồi máy tính 8 tiếng ở văn phòng đã mỏi nhừ, tối về nằm ngủ trên chiếc gối bông lún xẹp làm cổ bị bẻ cong suốt đêm. Hậu quả là sáng dậy đầu óc choáng váng, cổ cứng đờ, năng suất làm việc giảm sút trầm trọng.

⚡ KHUẤY ĐỘNG (AGITATE):
Nếu tình trạng này kéo dài, các đốt sống cổ C4-C6 sẽ bị thoái hóa sớm, dẫn tới tê bì tay chân và mất ngủ kinh niên. Chi phí đi vật lý trị liệu có thể lên tới hàng chục triệu đồng!

✅ GIẢI PHÁP (SOLUTION):
Gối Memory Foam Công Thái Học Định Hình Cột Sống — thiết kế đường cong lượn sóng nâng đỡ chính xác đường cong sinh lý cổ, phân tán 100% áp lực, giúp máu lưu thông lên não đều đặn suốt đêm.

Ưu đãi độc quyền hôm nay: Giảm ngay 40% + Miễn phí vận chuyển toàn quốc.
👉 Click vào link bên dưới để nhận mã giảm giá và bảo vệ sức khỏe giấc ngủ của bạn ngay hôm nay!""",

        "content_100": """INSIGHT #1:
- Nỗi đau ngầm: Sợ con bị tụt lại phía sau bạn bè nhưng bất lực vì không biết cách dạy con tập trung đọc sách mà không quát mắng.
- Mong muốn thực sự: Con tự giác ngồi vào bàn học và say mê đọc sách với nụ cười hạnh phúc, bố mẹ được thảnh thơi tự hào.
- Trigger cảm xúc: Cảm giác tội lỗi khi thấy con dán mắt vào màn hình iPad hàng giờ liền.
- Self-talk: "Phải chi có cuốn sách nào hấp dẫn như hoạt hình để con tự giác đọc mà mình không cần phải nhắc nhở..."

INSIGHT #2:
- Nỗi đau ngầm: Mua nhiều sách đắt tiền về con chỉ lật vài trang rồi bỏ xó, lãng phí tiền bạc.
- Mong muốn thực sự: Tìm được bộ sách tương tác cao, kết hợp hình ảnh trực quan giúp con tiếp thu kiến thức thực tế ngay lập tức.
- Trigger cảm xúc: Thấy con nhà người ta ham đọc sách và tự lập từ nhỏ.
- Self-talk: "Mình sẵn sàng đầu tư cho con, miễn là con thực sự thích và học được điều bổ ích." """,

        "content_121": """[HOOK - 5s]
"Bố mẹ nào đang đau đầu vì con lười đọc sách, chỉ mê điện thoại thì dừng lại xem đúng clip này 30 giây nha!"

[DEMO VISUAL - 30s]
(Mở hộp bộ sách: màu sắc tươi sáng, trang giấy dày dặn chống lóa, tranh minh họa 3D sống động)
"Cầm trên tay cuốn sách này các bạn sẽ hiểu tại sao nó lại được hàng vạn phụ huynh săn đón. Từng trang đều có mã QR quét video bài giảng hoạt hình cực kỳ vui nhộn!"

[BENEFIT - 45s]
"Chỉ 15 phút mỗi tối trước khi đi ngủ:
1) Con tự giác bỏ iPad sang một bên.
2) Rèn luyện tư duy ngôn ngữ và phản xạ logic.
3) Gắn kết tình cảm gia đình mà không cần quát mắng."

[SOCIAL PROOF - 20s]
"Hơn 50.000 phụ huynh đã phản hồi con thay đổi thói quen chỉ sau 1 tuần áp dụng!"

[URGENCY CTA - 15s]
"Duy nhất hôm nay: Combo 3 cuốn đang giảm 45% kèm quà tặng sổ tay sáng tạo. Số lượng có hạn, bấm vào giỏ hàng bên dưới để đặt ngay cho bé yêu nhé!"
"""
    }

    inserted_count = 0
    used_ids = set()

    for idx, p in enumerate(prompts_data, start=1):
        name = p.get("name", "").strip()
        group = p.get("group", "").strip()
        raw_prompt = p.get("prompt", "").strip()

        # Generate unique ID: check if PROMPT <N>
        num_match = re.search(r'PROMPT\s*(\d+)', name, re.I)
        if num_match:
            cand_id = f"content_{num_match.group(1)}"
            if cand_id in used_ids:
                cand_id = f"content_{num_match.group(1)}_{idx}"
        else:
            cand_id = f"content_{idx}"
        used_ids.add(cand_id)

        original_index = base_index + idx

        # Generate note: short summary
        note = f"{group} — {name}"
        if len(note) > 120:
            note = note[:117] + "..."

        # Insert prompt
        cursor.execute("""
            INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, category, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cand_id, original_index, name, name, "text", raw_prompt, raw_prompt, None, "content", note))

        # Extract & Insert Tags
        tags = get_clean_tags(group, name, raw_prompt)
        for t in tags:
            cursor.execute("""
                INSERT OR IGNORE INTO prompt_tags (prompt_id, tag)
                VALUES (?, ?)
            """, (cand_id, t))

        # Extract & Insert Fields
        fields = extract_prompt_fields(raw_prompt)
        for f_idx, f in enumerate(fields):
            is_primary = 1 if f_idx < 4 else 0
            cursor.execute("""
                INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cand_id, f["path"], f["key"], f["label"], "", f["type"], 0, is_primary))

        # Check if we have sample content seed for this prompt
        sample_text = sample_content_seeds.get(cand_id)
        if sample_text:
            cursor.execute("""
                INSERT INTO sample_contents (prompt_id, content, title)
                VALUES (?, ?, ?)
            """, (cand_id, sample_text, "Content Mẫu Thực Chiến #1"))

        inserted_count += 1

    conn.commit()
    print(f"\nSuccessfully inserted {inserted_count} content prompts into SQLite!")

    # Verify counts
    cursor.execute("SELECT COUNT(*) FROM prompts WHERE category = 'content'")
    total_content = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT tag) FROM prompt_tags")
    total_tags = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM prompt_fields WHERE prompt_id LIKE 'content_%'")
    total_fields = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sample_contents")
    total_samples = cursor.fetchone()[0]

    print(f"\n--- Verification Summary ---")
    print(f"Total Content Prompts in DB: {total_content}")
    print(f"Total Unique Tags in DB: {total_tags}")
    print(f"Total Fields extracted for Content Prompts: {total_fields}")
    print(f"Total Sample Contents: {total_samples}")

    conn.close()

if __name__ == "__main__":
    run_import()
