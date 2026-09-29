import unittest
import json
from app.services.ai_compact_generator import (
    is_reference_required,
    sanitize_compact_reference_tokens,
    ensure_reference_in_compact_prompt,
    truncate_preserving_token
)

class TestImproveAndCompactReference(unittest.TestCase):

    def test_is_reference_required_detection(self):
        # 1. Image category
        self.assertTrue(is_reference_required({"category": "image", "requires_reference": 0}))
        # 2. requires_reference explicit
        self.assertTrue(is_reference_required({"category": "content", "requires_reference": 1}))
        # 3. Text containing [ATTACHED_PHOTO]
        self.assertTrue(is_reference_required(text="Portrait photo matching [ATTACHED_PHOTO] in studio"))
        # 4. Text containing keywords
        self.assertTrue(is_reference_required(text="Prompt có ảnh tham chiếu khuôn mặt cô gái"))
        self.assertTrue(is_reference_required(text="RAW portrait with --cref image_0.png"))
        # 5. Non-reference content prompt
        self.assertFalse(is_reference_required({"category": "content", "requires_reference": 0}, text="Viết bài SEO về du lịch Đà Lạt"))

    def test_sanitize_compact_reference_tokens(self):
        # Should replace filename and old tokens
        text1 = "A portrait of girl matching image_0.png in garden"
        self.assertIn("[ATTACHED_PHOTO]", sanitize_compact_reference_tokens(text1))
        self.assertNotIn("image_0.png", sanitize_compact_reference_tokens(text1))

        text2 = "Selfie with <IMAGE 0>, casual lighting"
        self.assertIn("[ATTACHED_PHOTO]", sanitize_compact_reference_tokens(text2))
        self.assertNotIn("<IMAGE 0>", sanitize_compact_reference_tokens(text2))

        text3 = "Ảnh tham chiếu tải lên khuôn mặt cô gái"
        self.assertIn("[ATTACHED_PHOTO]", sanitize_compact_reference_tokens(text3))

    def test_ensure_reference_in_compact_prompt(self):
        # Midjourney format without ref -> adds --cref [ATTACHED_PHOTO]
        mj_text = "Cinematic 8k portrait of young woman, soft lighting, 35mm --ar 16:9 --v 6.0"
        result_mj = ensure_reference_in_compact_prompt(mj_text, requires_reference=True)
        self.assertIn("--cref [ATTACHED_PHOTO]", result_mj)
        self.assertLessEqual(len(result_mj), 1000)

        # Vietnamese format without ref -> adds reference note
        vn_text = "Ảnh chân dung cô gái Việt Nam trong tà áo dài trắng tại phố cổ Hà Nội lúc hoàng hôn"
        result_vn = ensure_reference_in_compact_prompt(vn_text, requires_reference=True)
        self.assertIn("[ATTACHED_PHOTO]", result_vn)
        self.assertLessEqual(len(result_vn), 1000)

        # Already has [ATTACHED_PHOTO] -> preserved
        has_ref_text = "Portrait strictly matching [ATTACHED_PHOTO], studio lighting"
        result_has = ensure_reference_in_compact_prompt(has_ref_text, requires_reference=True)
        self.assertEqual(has_ref_text, result_has)

    def test_truncate_preserving_token(self):
        # Long prompt exceeding 1000 chars with [ATTACHED_PHOTO]
        long_body = "A " + ("very detailed cinematic scene with high resolution studio lighting " * 25)
        full_text = f"{long_body} --cref [ATTACHED_PHOTO]"
        self.assertGreater(len(full_text), 1000)

        truncated = truncate_preserving_token(full_text, "[ATTACHED_PHOTO]", 1000)
        self.assertLessEqual(len(truncated), 1000)
        self.assertIn("[ATTACHED_PHOTO]", truncated)

if __name__ == "__main__":
    unittest.main()
