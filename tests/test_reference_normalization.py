import unittest
import json
from app.services.ai_converter import normalize_reference_image_in_json
from app.services.image_generator import sanitize_prompt_for_image_generation
from app.db.repository import PromptRepository

class TestReferenceImageNormalization(unittest.TestCase):

    def test_detection_by_vietnamese_reference_phrase(self):
        raw_text = "Tạo một bộ ảnh nghệ thuật với nhân vật nữ, giữ nguyên gương mặt theo ảnh tham chiếu."
        sample_json = {
            "title": "Chân dung nghệ thuật",
            "prompt": "Portrait of a woman, 8k"
        }
        normalized, has_ref = normalize_reference_image_in_json(sample_json, raw_text)
        self.assertTrue(has_ref)
        self.assertIn("reference_image_analysis", normalized)
        self.assertTrue(normalized["reference_image_analysis"]["reference_provided"])
        self.assertEqual(normalized["reference_image_analysis"]["reference_source"], "[ATTACHED_PHOTO]")
        self.assertEqual(normalized["reference_image_analysis"]["identity_lock"]["subject_id"], "REF_ATTACHED_01")
        self.assertEqual(normalized["reference_dependencies"]["primary_reference"]["source"], "[ATTACHED_PHOTO]")

    def test_detection_and_replacement_of_image_filenames(self):
        raw_text = "Style reference --sref style_01.png --cref face_input.jpg"
        sample_json = {
            "task": "consistent_character",
            "reference_image": "face_input.jpg",
            "parameters": {
                "cref_flag": "--cref face_input.jpg --cw 100",
                "sample_file": "sample.png"
            },
            "objects": [
                {
                    "id": "obj_001",
                    "reference_match": "Linked to ref_subject_01"
                }
            ]
        }
        normalized, has_ref = normalize_reference_image_in_json(sample_json, raw_text)
        self.assertTrue(has_ref)
        self.assertIn("[ATTACHED_PHOTO", normalized["reference_image"])
        self.assertIn("[ATTACHED_PHOTO", normalized["parameters"]["cref_flag"])
        self.assertIn("[ATTACHED_PHOTO", normalized["parameters"]["sample_file"])
        self.assertEqual(normalized["objects"][0]["reference_match"], "REF_ATTACHED_01")
        self.assertTrue(normalized["reference_image_analysis"]["reference_provided"])
        self.assertEqual(normalized["reference_image_analysis"]["reference_source"], "[ATTACHED_PHOTO]")

    def test_user_request_directives_and_sanitize_image_0_png(self):
        user_prompt_snippet = {
            "project_directives": {
                "primary_subject_reference": "image_0.png",
                "required_consistency_level": "absolute_facial_identity_match",
                "facial_extraction_details": {
                    "instructions": "Extracted strictly from uploaded image_0.png.",
                    "features": {
                        "face_shape": "Exact match to reference image"
                    }
                }
            },
            "image_generation": {
                "subject": {
                    "description": "Young woman, matching image_0.png"
                }
            }
        }
        normalized, has_ref = normalize_reference_image_in_json(user_prompt_snippet)
        self.assertTrue(has_ref)
        pdir = normalized["project_directives"]
        self.assertEqual(pdir["primary_subject_reference"], "[ATTACHED_PHOTO]")
        self.assertEqual(pdir["reference_image_dependency"], "Mandatory use of uploaded image for character consistency")
        self.assertEqual(pdir["identity_reference"], "[ATTACHED_PHOTO]")
        self.assertEqual(pdir["outfit_reference"], "[ATTACHED_PHOTO]")
        self.assertIn("[ATTACHED_PHOTO]", pdir["facial_extraction_details"]["instructions"])
        self.assertNotIn("image_0.png", json.dumps(normalized))

        # Test sanitize_prompt_for_image_generation
        raw_json_str = json.dumps(user_prompt_snippet)
        sanitized_str = sanitize_prompt_for_image_generation(raw_json_str)
        self.assertNotIn("image_0.png", sanitized_str)
        self.assertIn("[ATTACHED_PHOTO]", sanitized_str)
        self.assertIn("Mandatory use of uploaded image for character consistency", sanitized_str)

    def test_no_reference_present(self):
        raw_text = "Phong cảnh hoàng hôn trên biển, sóng vỗ nhẹ, ánh nắng vàng rực rỡ."
        sample_json = {
            "title": "Hoàng hôn biển",
            "scene": "Sunset at sea"
        }
        normalized, has_ref = normalize_reference_image_in_json(sample_json, raw_text)
        self.assertFalse(has_ref)
        self.assertNotIn("reference_image_analysis", normalized)

    def test_repository_update_prompt_json_structure_with_requires_reference(self):
        test_data = {
            "title": "Test Prompt Ref Normalization",
            "prompt_type": "text",
            "raw_content": "Chụp ảnh chân dung nhân vật theo ảnh mẫu đính kèm",
            "category": "image",
            "requires_reference": False
        }
        created = PromptRepository.create_prompt(test_data)
        self.assertIsNotNone(created)
        prompt_id = created["id"]
        try:
            self.assertEqual(created.get("requires_reference"), 0)

            parsed_json = {
                "task": "portrait",
                "reference_image": "[ATTACHED_PHOTO]",
                "reference_image_dependency": "Mandatory use of uploaded image for character consistency",
                "identity_reference": "[ATTACHED_PHOTO]",
                "outfit_reference": "[ATTACHED_PHOTO]",
                "reference_image_analysis": {
                    "reference_provided": True,
                    "reference_source": "[ATTACHED_PHOTO]"
                }
            }
            prompt_code = json.dumps(parsed_json, ensure_ascii=False)
            success = PromptRepository.update_prompt_json_structure(
                prompt_id=prompt_id,
                parsed_json=parsed_json,
                prompt_code=prompt_code,
                requires_reference=True
            )
            self.assertTrue(success)

            refreshed = PromptRepository.get_prompt_by_id(prompt_id)
            self.assertEqual(refreshed["prompt_type"], "json")
            self.assertEqual(refreshed["requires_reference"], 1)
            self.assertEqual(refreshed["parsed_json"]["reference_image"], "[ATTACHED_PHOTO]")
        finally:
            PromptRepository.delete_prompt(prompt_id)

    def test_get_stats_includes_by_category(self):
        stats = PromptRepository.get_stats()
        self.assertIn("total_prompts", stats)
        self.assertIn("by_category", stats)
        by_cat = stats["by_category"]
        self.assertIn("image", by_cat)
        self.assertIn("video", by_cat)
        self.assertIn("content", by_cat)
        self.assertGreater(stats["total_prompts"], 0)
        self.assertEqual(by_cat["image"] + by_cat["video"] + by_cat["content"], stats["total_prompts"])

if __name__ == "__main__":
    unittest.main()
