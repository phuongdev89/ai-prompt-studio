import unittest
import sqlite3
import json
from app.db.database import get_db, ensure_database
from app.db.repository import PromptRepository

class TestImprovePreservationAndCategory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_database()

    def test_original_raw_content_preserved_across_multiple_improvements(self):
        # 1. Create a prompt with distinct original raw text
        original_text = "ORIGINAL_RAW_V0: A highly detailed portrait of a cyberpunk hacker in rain, neon lighting."
        created = PromptRepository.create_prompt({
            "title": "Cyberpunk Hacker v0",
            "prompt_type": "text",
            "raw_content": original_text,
            "prompt_code": original_text,
            "category": "image"
        })
        self.assertIsNotNone(created)
        pid = created["id"]

        # Verify initial state
        fetched_v0 = PromptRepository.get_prompt_by_id(pid)
        self.assertEqual(fetched_v0["raw_content"], original_text)
        self.assertEqual(fetched_v0["original_raw_content"], original_text)

        # 2. First Improvement: OVERWRITE with improved code
        improved_code_v1 = "IMPROVED_CODE_V1: Masterpiece, 8k photo of a cyberpunk coder, ultra-detailed textures."
        overwritten_v1 = PromptRepository.overwrite_prompt(
            prompt_id=pid,
            title="Cyberpunk Hacker v1 (Improved)",
            prompt_code=improved_code_v1,
            raw_content=improved_code_v1, # Attempt to pass improved code as raw_content
            prompt_type="text",
            fields=[{"path": "topic", "key": "topic", "label": "Chủ đề", "value": "Cyberpunk", "type": "text", "is_primary": True}]
        )
        self.assertIsNotNone(overwritten_v1)
        self.assertEqual(overwritten_v1["prompt_code"], improved_code_v1)
        # raw_content and original_raw_content MUST REMAIN the original v0 text!
        self.assertEqual(overwritten_v1["raw_content"], original_text)
        self.assertEqual(overwritten_v1["original_raw_content"], original_text)

        # 3. Second Improvement: OVERWRITE again (simulating multiple iterations)
        improved_code_v2 = "IMPROVED_CODE_V2: Cinematic wide shot, cyberpunk coder in volumetric neon rain, anamorphic lens."
        overwritten_v2 = PromptRepository.overwrite_prompt(
            prompt_id=pid,
            title="Cyberpunk Hacker v2 (Improved 2nd time)",
            prompt_code=improved_code_v2,
            raw_content=improved_code_v2,
            prompt_type="text"
        )
        self.assertIsNotNone(overwritten_v2)
        self.assertEqual(overwritten_v2["prompt_code"], improved_code_v2)
        # MUST STILL be original v0 text!
        self.assertEqual(overwritten_v2["raw_content"], original_text)
        self.assertEqual(overwritten_v2["original_raw_content"], original_text)

        # 4. Third Improvement: SAVE AS NEW VERSION from overwritten_v2
        improved_code_v3 = "IMPROVED_CODE_V3: Unreal Engine 5 render, cyberpunk hacker, photorealistic raytracing."
        new_version_prompt = PromptRepository.save_as_new_version(
            parent_prompt_id=pid,
            title="Cyberpunk Hacker v3 (Branch Version)",
            prompt_code=improved_code_v3,
            raw_content=improved_code_v3,
            prompt_type="text"
        )
        self.assertIsNotNone(new_version_prompt)
        self.assertNotEqual(new_version_prompt["id"], pid)
        self.assertEqual(new_version_prompt["prompt_code"], improved_code_v3)
        # The new branch version MUST ALSO inherit the parent's original v0 text!
        self.assertEqual(new_version_prompt["raw_content"], original_text)
        self.assertEqual(new_version_prompt["original_raw_content"], original_text)

        # Clean up created test records
        PromptRepository.delete_prompt(pid)
        PromptRepository.delete_prompt(new_version_prompt["id"])

    def test_update_prompt_category(self):
        # 1. Create a prompt in category 'image'
        test_p = PromptRepository.create_prompt({
            "title": "Test Category Prompt",
            "prompt_type": "text",
            "raw_content": "KOC review video script about cosmetic products",
            "category": "image"
        })
        pid = test_p["id"]
        self.assertEqual(test_p["category"], "image")

        # 2. Switch category to 'video'
        success = PromptRepository.update_prompt_category(pid, "video")
        self.assertTrue(success)
        fetched = PromptRepository.get_prompt_by_id(pid)
        self.assertEqual(fetched["category"], "video")

        # 3. Switch category to 'content'
        success = PromptRepository.update_prompt_category(pid, "content")
        self.assertTrue(success)
        fetched = PromptRepository.get_prompt_by_id(pid)
        self.assertEqual(fetched["category"], "content")

        # 4. Switch category back to 'image'
        success = PromptRepository.update_prompt_category(pid, "image")
        self.assertTrue(success)
        fetched = PromptRepository.get_prompt_by_id(pid)
        self.assertEqual(fetched["category"], "image")

        # 5. Invalid category rejected
        success_invalid = PromptRepository.update_prompt_category(pid, "invalid_cat")
        self.assertFalse(success_invalid)

        # Clean up
        PromptRepository.delete_prompt(pid)

if __name__ == "__main__":
    unittest.main()
