import sqlite3
import os
from contextlib import contextmanager
from app.config import DB_PATH, JSON_DATA_PATH

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = dict_factory
    # Enable foreign keys and WAL mode for faster concurrent reads
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def ensure_database():
    if not DB_PATH.exists():
        print(f"[!] Database not found at {DB_PATH}. Initializing and migrating...")
        from tests.migrate_json_to_sqlite import migrate
        migrate(json_path=JSON_DATA_PATH, db_path=DB_PATH)
    else:
        # Check if tables exist
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompts'")
            if not cursor.fetchone():
                print("[!] Tables not found in database. Running migration...")
                from tests.migrate_json_to_sqlite import migrate
                migrate(json_path=JSON_DATA_PATH, db_path=DB_PATH)

    # Ensure columns and tables exist
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Ensure order_index column exists on images table
        cursor.execute("PRAGMA table_info(images)")
        img_cols = [c["name"] for c in cursor.fetchall()]
        if "order_index" not in img_cols:
            print("[*] Adding order_index column to images table...")
            cursor.execute("ALTER TABLE images ADD COLUMN order_index INTEGER DEFAULT 0")
            cursor.execute("UPDATE images SET order_index = id WHERE order_index = 0 OR order_index IS NULL")

        # 2. Ensure category & note columns exist on prompts table
        cursor.execute("PRAGMA table_info(prompts)")
        prompt_cols = [c["name"] for c in cursor.fetchall()]
        if "category" not in prompt_cols:
            print("[*] Adding category column to prompts table...")
            cursor.execute("ALTER TABLE prompts ADD COLUMN category TEXT DEFAULT 'image'")
            cursor.execute("UPDATE prompts SET category = 'image' WHERE category IS NULL OR category = ''")
        if "note" not in prompt_cols:
            print("[*] Adding note column to prompts table...")
            cursor.execute("ALTER TABLE prompts ADD COLUMN note TEXT DEFAULT ''")
        if "requires_reference" not in prompt_cols:
            print("[*] Adding requires_reference column to prompts table...")
            cursor.execute("ALTER TABLE prompts ADD COLUMN requires_reference INTEGER DEFAULT 0")
            # Mark all existing image prompts as requiring reference image as requested
            cursor.execute("UPDATE prompts SET requires_reference = 1 WHERE category = 'image'")

        # Migration: convert legacy 'character' category to 'image'
        cursor.execute("UPDATE prompts SET category = 'image' WHERE category = 'character' OR category IS NULL OR category = ''")

        # Migration: ensure 'Character' tag is assigned to all existing prompts in category = 'image'
        cursor.execute("""
            INSERT OR IGNORE INTO prompt_tags (prompt_id, tag)
            SELECT id, 'Character' FROM prompts WHERE category = 'image'
        """)

        # 3. Ensure is_primary column exists on prompt_fields table
        cursor.execute("PRAGMA table_info(prompt_fields)")
        field_cols = [c["name"] for c in cursor.fetchall()]
        if "is_primary" not in field_cols:
            print("[*] Adding is_primary column to prompt_fields table...")
            cursor.execute("ALTER TABLE prompt_fields ADD COLUMN is_primary INTEGER DEFAULT 0")
            # Mark sensible default primary attributes for existing fields
            primary_keywords = ['topic', 'hook', 'target_audience', 'description', 'outfit', 'wardrobe', 'style', 'lighting', 'camera', 'camera_angle', 'settings', 'composition', 'layout', 'genre', 'aesthetic', 'mood']
            for kw in primary_keywords:
                cursor.execute("""
                    UPDATE prompt_fields 
                    SET is_primary = 1 
                    WHERE LOWER(field_key) = ? 
                      AND LOWER(field_path) NOT LIKE '%features.%' 
                      AND LOWER(field_path) NOT LIKE '%panels_sequence.panel_%'
                      AND is_primary = 0
                """, (kw,))

        # 4. Ensure sample_contents table exists & has order_index
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sample_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT NOT NULL,
                content TEXT NOT NULL,
                title TEXT DEFAULT '',
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sample_contents_prompt_id ON sample_contents(prompt_id);")

        cursor.execute("PRAGMA table_info(sample_contents)")
        sc_cols = [c["name"] for c in cursor.fetchall()]
        if "order_index" not in sc_cols:
            print("[*] Adding order_index column to sample_contents table...")
            cursor.execute("ALTER TABLE sample_contents ADD COLUMN order_index INTEGER DEFAULT 0")
            cursor.execute("UPDATE sample_contents SET order_index = id WHERE order_index = 0 OR order_index IS NULL")

        # 5. Ensure prompt_tags table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT NOT NULL,
                tag TEXT NOT NULL COLLATE NOCASE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
                UNIQUE(prompt_id, tag)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_tags_tag ON prompt_tags(tag);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_tags_prompt_id ON prompt_tags(prompt_id);")

        # 6. Ensure hash & published_at columns for sync
        if "hash" not in prompt_cols:
            print("[*] Adding hash column to prompts table...")
            cursor.execute("ALTER TABLE prompts ADD COLUMN hash TEXT DEFAULT ''")
        if "published_at" not in prompt_cols:
            print("[*] Adding published_at column to prompts table...")
            cursor.execute("ALTER TABLE prompts ADD COLUMN published_at TEXT DEFAULT ''")

        # Ensure sync_meta table for last_synced_at tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # 8. Check if starter tags need to be seeded
        cursor.execute("SELECT COUNT(*) as count FROM prompt_tags")
        tags_count = cursor.fetchone().get("count", 0)
        if tags_count == 0:
            print("[*] Seeding starter tags for prompts...")
            _seed_starter_tags(cursor)

        # 9. Check if starter content prompts need to be seeded
        cursor.execute("SELECT COUNT(*) as count FROM prompts WHERE category = 'content'")
        content_count = cursor.fetchone().get("count", 0)
        if content_count == 0:
            print("[*] Seeding starter Content prompts for the Content tab...")
            _seed_starter_content_prompts(cursor)

        conn.commit()

def _seed_starter_content_prompts(cursor):
    import json
    from app.services.parser import extract_flat_fields

    starter_prompts = [
        {
            "id": "content_1",
            "title": "Kịch bản Video TikTok 60s Review Mỹ Phẩm KOC",
            "note": "Kịch bản video ngắn 60 giây đánh giá serum mờ thâm, giữ chân người xem cao, chốt đơn giỏ hàng",
            "category": "content",
            "prompt_type": "json",
            "parsed_json": {
                "topic": "Review Serum Niacinamide dưỡng sáng mờ thâm",
                "target_audience": "Nữ từ 18-28 tuổi, da dầu mụn có thâm sau mụn",
                "tone_of_voice": "Thân thiện, chân thực như bạn bè chia sẻ, nhấn mạnh trải nghiệm cá nhân",
                "hook_first_3s": "Đừng mua chai serum này nếu bạn không muốn hết sạch thâm mụn chỉ sau 14 ngày!",
                "pain_point": "Dùng đủ loại treatment đắt tiền mà vết thâm đỏ, thâm đen vẫn dai dẳng, da lại bị bí rít",
                "solution_product": "Serum Niacinamide 10% + Zinc 1% thẩm thấu tức thì không bết dính",
                "call_to_action": "Bấm ngay vào góc trái giỏ hàng phía dưới để săn voucher giảm 30% hôm nay nha!",
                "duration_seconds": 60
            },
            "sample_content": """[00:00 - 00:03] HOOK MỞ ĐẦU:
(Cận cảnh mặt KOC, tay chỉ vào một vùng da sáng mịn, biểu cảm bất ngờ)
"Ê, nói thật là đừng có dại mà rước chai serum này về nếu bà nào không muốn hết sạch thâm mụn chỉ sau đúng 2 tuần nha!"

[00:03 - 00:15] NÊU NỖI ĐAU (PAIN POINT):
(Chuyển cảnh zoom vào ảnh cũ lúc da còn nhiều thâm mụn)
"Bà nào da dầu mụn như tui thì hiểu cái cảm giác này nè: cứ hết mụn là để lại một 'bầu trời' thâm đỏ thâm đen. Dùng treatment nặng đô thì sợ kích ứng bung bét, mà kem đặc thì bí da lên mụn ẩn tiếp, trầm cảm thực sự luôn á!"

[00:15 - 00:35] GIẢI PHÁP & TRẢI NGHIỆM THỰC TẾ:
(Cảnh KOC test kết cấu serum lên mu bàn tay, sau đó apply lên mặt)
"Cho đến khi bà chị da liễu ném cho tui chai Niacinamide 10% kết hợp Kẽm ZinC này. Điểm tui mê nhất là texture dạng lỏng nhẹ như nước, thoa lên da tầm 5 giây là thấm ráo mịn hoàn toàn, không hề nhờn rít hay châm chích gì hết trơn. Thành phần có ZinC kiềm dầu cực đỉnh, còn Niacinamide tinh khiết giúp chặn đứng sắc tố thâm mới hình thành."

[00:35 - 00:50] BẰNG CHỨNG KẾT QUẢ (PROOF):
(Quay cận cảnh làn da dưới ánh sáng tự nhiên)
"Sau đúng 14 ngày kiên trì sáng tối, mấy vết thâm mới mờ đi trông thấy tầm 80%, da sáng đều màu và vùng chữ T đỡ đổ dầu hẳn luôn. Không phải khen lố đâu mà chất lượng vượt xa cái giá hạt dẻ của nó!"

[00:50 - 00:60] KÊU GỌI HÀNH ĐỘNG (CTA):
(KOC cầm sản phẩm chỉ tay xuống góc dưới màn hình)
"Hôm nay hãng đang có deal flash sale trợ giá độc quyền trong giỏ hàng góc trái video này nè, kèm quà mini size nữa. Tranh thủ bấm vào góc trái rinh ngay kẻo hết mã nha mọi người ơi!"""
        },
        {
            "id": "content_2",
            "title": "Bài viết Blog Chuẩn SEO 1500 Từ Affiliate Marketing",
            "note": "Cấu trúc bài viết chuẩn SEO On-page top Google, lồng ghép link tiếp thị liên kết tự nhiên, tỷ lệ click cao",
            "category": "content",
            "prompt_type": "json",
            "parsed_json": {
                "niche": "Đồ gia dụng thông minh cho căn hộ nhỏ",
                "primary_keyword": "nồi chiên không dầu tốt nhất cho người độc thân",
                "secondary_keywords": "nồi chiên không dầu mini, review nồi chiên không dầu giá rẻ, nồi chiên 2L tiết kiệm điện",
                "target_persona": "Người đi làm bận rộn, sống một mình hoặc 2 người, không gian bếp nhỏ",
                "article_structure": "Tiêu đề H1 hấp dẫn -> Mở bài PAS -> Tiêu chí chọn mua -> Top 3 sản phẩm đánh giá chi tiết -> Bảng so sánh -> Kết luận & Lời khuyên",
                "affiliate_insertion": "Đặt nút CTA nổi bật sau mỗi sản phẩm và bảng so sánh trực quan"
            },
            "sample_content": """# Top 3 Nồi Chiên Không Dầu Cho Người Độc Thân Tốt Nhất 2026 (Nhỏ Gọn, Bền, Giá Dưới 1 Triệu)

Bạn sống một mình trong căn hộ studio nhỏ, thèm ăn đồ chiên rán giòn rụm nhưng ngại mùi dầu mỡ ám khắp phòng và lười rửa chiếc chảo ngập mỡ?

Một chiếc **nồi chiên không dầu mini (dung tích 2L - 3.5L)** chính là "cứu tinh" hoàn hảo cho gian bếp của bạn. Trong bài viết này, chúng tôi đã trực tiếp thử nghiệm và chọn lọc ra 3 mẫu nồi chiên nhỏ gọn, tiết kiệm điện và đáng đồng tiền bát gạo nhất hiện nay.

---

## 1. Tiêu Chí Chọn Nồi Chiên Không Dầu Cho Người Sống Một Mình
- **Dung tích lý tưởng:** Từ 2.0L đến 3.5L (đủ chiên 1 góc đùi gà, 4-5 cánh gà hoặc 200g khoai tây chiên).
- **Công suất:** 1200W - 1400W giúp chín nhanh mà không tốn nhiều điện.
- **Lớp chống dính:** Phải là chống dính Ceramic hoặc Teflon cao cấp, dễ rửa chỉ trong 1 phút.
- **Kích thước:** Chiếm diện tích mặt bàn không quá 1 tờ giấy A4.

---

## 2. Đánh Giá Chi Tiết Top 3 Sản Phẩm Đáng Mua Nhất

### 🏆 Top 1: Lock&Lock Eco Fryer 2.5L - Bền Bỉ, Thiết Kế Bắc Âu
- **Ưu điểm:** Gia nhiệt cực đều, chống dính siêu bền sau 1 năm sử dụng, tiếng quạt êm.
- **Nhược điểm:** Núm xoay cơ truyền thống, không có màn hình cảm ứng.
- **Giá tham khảo:** ~890.000 VNĐ.
👉 [Xem giá ưu đãi chính hãng Lock&Lock trên Shopee Mall]

### 🥈 Top 2: Xiaomi Smart Air Fryer 3.5L - Kết Nối Điện Thoại, Đa Năng
- **Ưu điểm:** Điều khiển qua App Mi Home, có thể hẹn giờ nấu trước khi đi làm về.
- **Nhược điểm:** Mặt kính bóng dễ bám vân tay.
- **Giá tham khảo:** ~990.000 VNĐ.
👉 [Xem giá ưu đãi chính hãng Xiaomi trên Lazada]

---

## 3. Lời Khuyên Cho Bạn
Nếu bạn ưu tiên độ bền và sự đơn giản, hãy chọn ngay **Lock&Lock Eco Fryer 2.5L**. Còn nếu bạn là tín đồ công nghệ thích hẹn giờ sẵn, **Xiaomi 3.5L** sẽ là trợ thủ đắc lực không thể thiếu!"""
        },
        {
            "id": "content_3",
            "title": "Kịch bản Livestream Chốt Đơn Shopee / TikTok Shop",
            "note": "Kịch bản livestream bán hàng đẩy cảm xúc, tạo khan hiếm, dồn dập tung deal chớp nhoáng (flash sale) bùng nổ mắt xem",
            "category": "content",
            "prompt_type": "json",
            "parsed_json": {
                "product_category": "Thời trang công sở nữ / Áo sơ mi & chân váy",
                "live_phase": "Giai đoạn dồn đơn chớp nhoáng (Flash Sale 3 phút)",
                "host_energy": "Năng lượng cao, nhịp nói dồn dập, liên tục đếm ngược thời gian và số lượng tồn kho",
                "deal_mechanic": "Mua 1 áo tặng 1 phụ kiện cao cấp, freeship toàn quốc, giảm trực tiếp 50K",
                "urgency_triggers": "Chỉ còn đúng 15 suất cuối cùng cho 15 khách hàng nhanh tay nhất"
            },
            "sample_content": """(Trợ lý hậu trường bật nhạc nền beat nhanh, sôi động, đếm chuông leng keng)

MC (Nói to, dõng dạc, tay giơ mẫu áo sơ mi lụa):
"CẢ NHÀ ƠI! DỪNG LẠI NGAY Ở MÀN HÌNH NÀY CHO EM ĐÚNG 3 PHÚT THÔI!
Ai đang tìm một chiếc sơ mi lụa tơ tằm mặc đi làm sang chảnh, không nhăn, không lộ nội y thì gõ ngay chữ 'XIN DEAL' vào ô chat cho em thấy cánh tay của các chị nào!

Mẫu này giá niêm yết tại showroom là 380K, NHƯNG DUY NHẤT trong 3 phút đồng hồ này trên livestream:
👉 Giảm trực tiếp còn 199K!
👉 TẶNG KÈM NGAY một cài áo mạ vàng trị giá 85K!
👉 Miễn phí ship tận giường cho ai chốt đơn trước tiếng đếm số 0!

Em chỉ xin phép kho mở đúng 15 SUẤT duy nhất cho 15 chị bấm nhanh nhất!
Kho ơi ghim mã số 03 lên màn hình cho các chị em săn ngay nào!
3... 2... 1... LINK ĐÃ LÊN! Các chị bấm chữ MUA NGAY, chọn size S, M, L rồi bấm ĐẶT HÀNG liền tay, đừng để trong giỏ kẻo người khác thanh toán trước là bay mất suất nha!"

(MC liên tục đọc tên khách hàng chốt đơn):
"Chúc mừng chị Ngọc Bích chốt thành công size M! Chúc mừng chị Lan Anh vừa săn được áo màu kem!
Kho báo em chỉ còn 4 suất cuối cùng thôi cả nhà ơi! Nhanh tay bấm Mua Ngay ở góc dưới bên trái nào!"""
        }
    ]

    cursor.execute("SELECT COUNT(*), MAX(original_index) FROM prompts")
    row = cursor.fetchone()
    current_count = row["COUNT(*)"] if "COUNT(*)" in row else row[list(row.keys())[0]]
    max_idx = row["MAX(original_index)"] if "MAX(original_index)" in row else 0
    if max_idx is None:
        max_idx = current_count

    for item in starter_prompts:
        max_idx += 1
        p_id = item["id"]
        # Ensure unique id
        cursor.execute("SELECT id FROM prompts WHERE id = ?", (p_id,))
        if cursor.fetchone():
            continue

        title = item["title"]
        note = item["note"]
        category = item["category"]
        prompt_type = item["prompt_type"]
        parsed_json = item["parsed_json"]
        prompt_code = json.dumps(parsed_json, indent=2, ensure_ascii=False)
        raw_content = prompt_code

        cursor.execute("""
            INSERT INTO prompts (id, original_index, title, raw_title, prompt_type, raw_content, prompt_code, parsed_json, category, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (p_id, max_idx, title, title, prompt_type, raw_content, prompt_code, prompt_code, category, note))

        # Insert fields with sensible is_primary
        flat_fields = extract_flat_fields(parsed_json)
        for idx, f in enumerate(flat_fields):
            is_primary = 1 if idx < 4 else 0
            cursor.execute("""
                INSERT INTO prompt_fields (prompt_id, field_path, field_key, label, field_value, field_type, is_list, is_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p_id,
                f.get("path", ""),
                f.get("key", ""),
                f.get("label", ""),
                str(f.get("value", "")),
                f.get("type", "text"),
                1 if f.get("is_list") else 0,
                is_primary
            ))

        # Insert sample content
        sample_text = item.get("sample_content", "")
        if sample_text:
            cursor.execute("""
                INSERT INTO sample_contents (prompt_id, content, title)
                VALUES (?, ?, ?)
            """, (p_id, sample_text, "Content mẫu #1"))

def _seed_starter_tags(cursor):
    cursor.execute("SELECT id, title, raw_content, note, category FROM prompts")
    prompts = cursor.fetchall()

    tag_rules = [
        ("Storyboard", ["storyboard", "12 ô", "12 khung", "panel"]),
        ("Chân dung", ["chân dung", "gương mặt", "portrait", "close-up", "khuôn mặt"]),
        ("KOC", ["koc", "người mẫu", "influencer"]),
        ("Siêu thực", ["siêu thực", "photorealistic", "hyperrealistic", "realistic"]),
        ("Studio", ["studio", "phòng chụp", "chụp studio"]),
        ("Ngoại cảnh", ["ngoại cảnh", "ngoài trời", "outdoor", "đường phố", "công viên"]),
        ("Cosplay", ["cosplay", "hóa trang", "cổ trang"]),
        ("Điện ảnh", ["cinematic", "điện ảnh", "chiếu phim"]),
        ("TikTok", ["tiktok", "video ngắn", "reels", "shorts"]),
        ("SEO", ["seo", "bài viết", "google"]),
        ("Affiliate", ["affiliate", "tiếp thị liên kết"]),
        ("Livestream", ["livestream", "live", "chốt đơn", "flash sale"]),
        ("Review", ["review", "đánh giá"]),
        ("Kịch bản Video", ["kịch bản", "script", "scene"])
    ]

    for p in prompts:
        pid = p["id"]
        text_corpus = f"{p.get('title') or ''} {p.get('note') or ''} {p.get('raw_content') or ''}".lower()

        for tag_name, keywords in tag_rules:
            if any(kw in text_corpus for kw in keywords):
                cursor.execute("""
                    INSERT OR IGNORE INTO prompt_tags (prompt_id, tag)
                    VALUES (?, ?)
                """, (pid, tag_name))


