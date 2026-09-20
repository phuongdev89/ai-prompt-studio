import base64
import json
import os
import sys
import time
import requests

# Đảm bảo in tiếng Việt / Unicode chuẩn trên console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# =====================================================================
# CẤU HÌNH API - BẠN HÃY THAY TOKEN CỦA BẠN VÀO ĐÂY:
# =====================================================================
API_KEY = "sk-a78fc4c78e41759505afdc271b60063461cff5cbfb2e5efc4c2c4bfaa5f95a49"  # <-- Thay token của bạn vào đây

API_URL = "https://api.zpro.io.vn/v1/images/generations"

# Cấu trúc nội dung prompt dạng dictionary (được tuần tự hóa thành chuỗi JSON như lệnh cURL)
PROMPT_DATA = {
    "subject": {
        "description": (
            "A young adult woman is seated on a dark wooden indoor staircase, photographed from a very close "
            "and steep overhead angle. She lifts her face directly toward the camera. The close wide-angle "
            "perspective makes the face the dominant visual anchor while the body folds compactly down the "
            "staircase toward the lower-left area. The image should feel like a private spontaneous snapshot "
            "rather than a formally directed portrait."
        ),
        "mirror_rules": (
            "This is not a mirror selfie. Preserve the original left-right orientation and spatial relationships. "
            "Do not automatically flip the frame. Keep the extended hand toward the upper-left step, the "
            "supporting hand toward the lower-right side, and the staircase props on their corresponding sides."
        ),
        "age": "Young adult woman, visually around 20-25 years old; clearly adult, with no childlike styling.",
        "expression": {
            "eyes": {
                "look": "Eyes opened slightly wide, looking directly into the lens with clearly visible irises and catchlights.",
                "energy": "Alert, curious, softly surprised, not a mature seductive gaze.",
                "direction": "Looking upward toward a camera positioned above and slightly in front of her."
            },
            "mouth": {
                "position": "Lips gently pushed forward into a small soft pout, closed or separated only by a tiny gap.",
                "energy": "Playful and unconscious, more like an instinctive reaction than an exaggerated kissing pose."
            },
            "overall": "Direct, intimate and casually playful, with the feeling that she has just noticed the camera and may be about to say something."
        },
        "face": {
            "preserve_original": (
                "Preserve the compact oval-to-soft-V facial outline, visually large eyes, natural nose bridge, "
                "small lip shape and subtle real-world facial asymmetry. Do not transform the face into a sharply "
                "sculpted Western commercial-model structure. Avoid excessive face slimming or eye enlargement."
            ),
            "makeup": (
                "Fresh K-beauty / Korean-idol-inspired everyday makeup language without referencing any specific "
                "celebrity or identity. Thin semi-matte base, warm pink blush centered on the cheeks and softly "
                "extending beneath the eyes, delicate brown-black tightlining, individually separated curled "
                "lashes with visible upper and lower lashes, restrained aegyo-sal definition, naturally straight "
                "brows, and low-saturation rose-pink or peach-pink lips with a faint moist reflection. Avoid "
                "heavy contouring, smoky eyes and intense Western-style highlighting."
            )
        }
    },
    "facial_extraction_details": {
        "instructions": (
            "Trích xuất từ ảnh upload: Hình dáng khuôn mặt, đặc điểm ngũ quan, màu mắt, kiểu tóc v.v. "
            "Extracted strictly from the uploaded input source image. Do not change the underlying face structure. "
            "Preserve exact facial features, identity, proportions, skin texture, age, and facial structure. "
            "Do not redesign, beautify, or stylize. The generated subject must be the exact same person as the "
            "reference across all 6 panels."
        ),
        "features": {
            "face_shape": "Exact match to reference image",
            "eyes": "Exact match to reference image, including exact eye color",
            "nose": "Exact match to reference image",
            "lips": "Exact match to reference image",
            "skin": "Exact match to reference image",
            "hair": "Exact match to reference image's base hair color and style"
        },
        "shadows": "realistic soft indoor shadows"
    },
    "hair": {
        "color": "Natural deep brown-black to black.",
        "style": (
            "Center-parted or nearly center-parted straight hair around shoulder length, naturally falling into "
            "two low sections on either side of the face. Several very fine face-framing strands cross the forehead "
            "and cheek area, with one or two strands passing close to the eyes."
        ),
        "effect": (
            "Straight and smooth but not advertising-perfect, with realistic strand separation, slight flyaways and "
            "a mild natural sheen. Hair sits relatively close to the scalp and the ends remain slightly irregular "
            "rather than professionally curled."
        )
    },
    "body": {
        "frame": (
            "Slender and compact adult frame. The seated position makes the body appear small, while the close "
            "wide-angle perspective enlarges the face and upper body relative to the lower body."
        ),
        "waist": "Most of the waist is obscured by the seated pose, fabric folds and bent legs. Do not intentionally emphasize or exaggerate the waistline.",
        "chest": "Only a restrained amount of clavicle and upper-chest skin is visible. The top provides natural coverage with no cleavage emphasis or exaggerated chest contour.",
        "legs": (
            "Both legs are bent and folded compactly on the staircase. Thighs and knees form prominent visible "
            "skin areas. Due to the steep overhead angle and close wide lens, the legs naturally become smaller as "
            "they recede away from the camera."
        ),
        "skin": {
            "visible_areas": [
                "full face",
                "neck",
                "clavicles and a small amount of upper chest",
                "both shoulders",
                "upper arms",
                "forearms",
                "hands and fingers",
                "thighs",
                "knees",
                "small portions of lower legs and ankle area"
            ],
            "tone": "Light to light-medium warm-neutral beige skin. Warm indoor lighting adds subtle peach and apricot tones to the cheeks, arms and legs. Avoid bleaching the skin into cool porcelain white or making it heavily bronzed.",
            "texture": "Fine-grained, natural and soft-looking skin with a slightly velvety semi-matte finish. It should suggest a soft, fine natural surface to the touch rather than synthetic smoothness. Allow very mild texture variation around knees, joints and hands instead of plastic retouching.",
            "lighting_effect": "Warm indoor light falls softly from above and slightly in front of the subject, creating broad gentle highlights across the forehead, nose bridge, shoulders, forearms and thighs. Natural soft shadows appear beneath the chin, under the hair, between overlapping legs and where the body meets the staircase. No dedicated rim light and no hard studio highlights."
        }
    },
    "pose": {
        "position": "The subject sits on a dark wooden stair tread, her body running diagonally from the upper-right area toward the lower-left. Her head tilts upward toward the elevated camera. Her left arm reaches widely toward the upper-left step, while the right arm extends downward or nearly straight with the palm resting on a check-patterned cushion beside her.",
        "base": "Her hips and thighs are supported by the staircase, with the right palm adding slight secondary support. Both knees are bent and gathered compactly in front of and toward the lower-left side of the body, creating an asymmetrical center of gravity.",
        "overall": "Keep the pose slightly cramped, asymmetrical and naturally imperfect. The neck tilts backward to look up. Avoid stretching the body into a conventional fashion-model pose; preserve a small amount of spontaneous awkwardness created by the candid moment."
    },
    "clothing": {
        "top": {
            "type": "Lightweight white ruched and ruffle-trimmed top with narrow shoulder connections or straps and low-set short sleeves, creating a cold-shoulder or softly off-shoulder appearance.",
            "color": "Soft slightly warm white rather than blue-white.",
            "details": "Natural gathering, small ruffles and elastic ruching around the neckline, sleeves and bodice. The shoulders remain visibly exposed while the front maintains restrained coverage. Fabric resembles lightweight cotton or a cotton blend.",
            "effect": "Fabric is naturally compressed and wrinkled by the seated posture, slightly fitted in some places and loose in others. Do not make it perfectly ironed or convert it into glossy luxury fabric."
        },
        "bottom": {
            "type": "A short dark lower garment, likely black shorts or a short skirt, mostly obscured by the seated posture and bent legs.",
            "color": "Black to very dark charcoal.",
            "details": "Only retain the limited amount of dark lower garment that is actually visible. Do not invent prominent belts, metallic decorations or elaborate skirt structure. White ankle socks and black footwear remain visible near the lower portion of the frame, producing a clear black-and-white contrast."
        }
    },
    "accessories": {
        "jewelry": "Very small silver-toned earrings or studs are visible, along with a simple metallic ring on the right hand. Jewelry should remain tiny, casual and visually secondary.",
        "prop": "Near the extended hand in the upper-left is a small cream-colored soft toy or fabric object with a few red or dark accents. The right palm rests on a small black-and-white or brown-and-white check-patterned stair cushion."
    },
    "photography": {
        "camera_style": "Casual consumer smartphone or compact-digital-camera snapshot, approximately 24-28mm full-frame equivalent wide angle. The camera is physically close to the subject, making the face slightly enlarged while the body and stairs shrink rapidly into depth. Use automatic-exposure realism, mild JPEG character and limited post-processing. A phone-main-camera feeling around f/1.8-f/2.4, roughly 1/60 sec and moderate indoor ISO can be simulated, but avoid professional full-frame studio polish.",
        "angle": "Strong overhead angle, with the camera positioned above and slightly forward of the subject and tilted downward around 60-75 degrees. The camera does not need to be perfectly level; allow a mild rotational tilt. The subject looks upward, producing natural high-angle facial perspective.",
        "shot_type": "Close overhead environmental portrait ranging from medium to nearly full-body. The head and face occupy the upper-right region and form the strongest visual focus. Bent legs extend toward the lower-left while the arms pull the composition outward in opposing directions.",
        "aspect_ratio": "Vertical frame around 5:6, close to the reference image's approximately 708x850 ratio. Keep the composition slightly off-center with mild edge cropping and spatial compression.",
        "texture": "Slightly soft digital sharpness, fine realistic sensor noise, warm wood color, restrained dynamic range and no excessive skin micro-sharpening. Preserve mild JPEG snapshot character, tiny motion softness, stray hair occlusion and imperfect edges rather than polished commercial cleanliness.",
        "lighting": "Warm indoor ambient lighting around 3200K-4000K, mainly from a soft source above or above-front of the camera, with gentle reflection from the pale staircase wall or side panel. Low-to-medium contrast, no obvious three-point lighting, no separate hair rim light and no strong directional fill. Dark wooden steps retain brown tonal information instead of becoming pure black.",
        "depth_of_field": "Moderately deep depth of field. The face is the sharpest area, but hands, legs, stairs and cushion remain recognizable. Only allow mild natural focus falloff from close shooting distance; avoid aggressive computational portrait-mode blur."
    },
    "background": {
        "setting": "A compact residential-feeling indoor staircase with dark wooden steps.",
        "wall_color": "Deep walnut-brown stair treads paired with pale gray-white or warm off-white stone/wall side surfaces.",
        "elements": [
            "layered dark-brown wooden stair treads",
            "pale gray-white staircase side panel or stone riser surface",
            "a small check-patterned cushion or stair pad beside the subject",
            "a faded beige vintage-style central patch with indistinct handwritten lettering on the cushion",
            "a cream soft toy or fabric accessory near the extended left hand",
            "a small pale-lilac rectangular object or paper edge in the upper-right background"
        ],
        "atmosphere": "Quiet, compact and lived-in rather than staged. Slightly casual background clutter reinforces the feeling of a personal diary photo or home snapshot.",
        "lighting": "The background shares the same warm indoor ambient source as the subject. Stair edges and corners produce soft natural shadows while the pale side panel creates weak reflected fill."
    },
    "the_vibe": {
        "energy": "Light, awake, spontaneous and softly playful.",
        "mood": "Personal and informal, with a hint of being caught off guard while remaining quiet and gentle.",
        "aesthetic": "Late-2000s to 2010s compact-digicam / early-smartphone snapshot residue blended with soft Korean everyday-idol styling: fresh makeup, white gathered top, warm wooden staircase and direct lens contact, without turning into a magazine-perfect fashion image.",
        "authenticity": "Preserve close-range wide-angle proportion shifts, imperfect off-center framing, mild camera tilt, stray hair crossing the face, irregular fabric folds, small background objects and subtle digital noise. Do not automatically correct everything into visual symmetry.",
        "intimacy": "The photographer feels physically close, as if standing one or two stairs above and leaning over to take the photo. Direct eye contact creates a personal snapshot distance without becoming sexualized.",
        "story": "She had already been sitting on the stairs for a moment, with small everyday objects left around her. A second before the shutter, she had just looked up and noticed the camera; the photograph preserves the reaction after it began, while suggesting she is about to say something next.",
        "caption_energy": "A casual social-media diary image with almost no explanation: a tiny inside joke, a timestamp, a two-word caption, or no caption at all."
    },
    "style": {
        "genre": "documentary lifestyle photography",
        "aesthetic": "unposed snapshot aesthetic",
        "colors": "natural colors, slightly warm and tones",
        "quality": "ultra-realistic RAW photo quality",
        "resolution": "4K",
        "focus": "sharp focus on the subject's face"
    },
    "constraints": {
        "must_keep": [
            "clearly adult young woman",
            "very close steep overhead viewpoint",
            "24-28mm equivalent wide-angle perspective",
            "direct upward eye contact",
            "small restrained pout",
            "dark center-parted straight hair with thin stray strands across the face",
            "white ruched ruffled shoulder-baring top",
            "visible thighs and knees created naturally by the seated pose",
            "left arm reaching toward the upper-left stair and right hand resting on the check-patterned pad",
            "dark walnut staircase with pale side panel",
            "soft warm indoor ambient light",
            "slightly tilted",
            "off-center",
            "imperfect candid composition",
            "subtle digital noise and non-commercial skin texture"
        ],
        "avoid": [
            "do not identify or assign real identity",
            "nationality or ethnicity",
            "do not make the subject childlike",
            "do not sexualize the pose or emphasize the chest",
            "do not add cleavage or exaggerated curves",
            "do not replace the facial structure with a Western commercial-model face",
            "do not heavily smooth the skin",
            "do not exaggerate eye size or sharpen the chin",
            "no cinematic rim lighting",
            "no polished three-point studio lighting",
            "no extreme shallow depth of field",
            "no computational portrait-mode blur",
            "no perfectly centered geometric composition",
            "do not remove stray hair",
            "small background objects or clothing wrinkles",
            "do not turn the staircase into a luxury-hotel environment",
            "do not horizontally flip the reference composition"
        ]
    },
    "negative_prompt": [
        "minor appearance",
        "childlike proportions",
        "sexualized pose",
        "cleavage emphasis",
        "exaggerated curves",
        "heavy contour",
        "smoky makeup",
        "plastic skin",
        "over-smoothed",
        "over-retouched face",
        "oversized eyes",
        "extreme V-line",
        "perfect symmetry",
        "inconsistent face",
        "bad anatomy",
        "studio glamour",
        "three-point lighting",
        "strong rim light",
        "cinematic teal-orange",
        "extreme bokeh",
        "portrait-mode blur",
        "HDR",
        "oversharpening",
        "perfectly centered composition",
        "mirror flip",
        "extra fingers",
        "missing fingers",
        "deformed hands",
        "warped stairs",
        "changing clothes",
        "cluttered background",
        "text",
        "fake text",
        "watermark",
        "logo"
    ]
}

# Payload gửi lên API
payload = {
    "model": "gpt-image-2.5",
    "prompt": json.dumps(PROMPT_DATA, ensure_ascii=False),
    "n": 1,
    "size": "auto",
    "quality": "auto",
    "background": "auto",
    "image_detail": "high",
    "output_format": "png",
    "image": "https://s3.us-west-004.backblazeb2.com/phuongdev89-draft/references/7f4c9993ea7b41bea2faa1d3f4380f81.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=004fb885102c2790000000002%2F20260920%2Fus-west-004%2Fs3%2Faws4_request&X-Amz-Date=20260920T045028Z&X-Amz-Expires=3600&X-Amz-Signature=5da74e9cf16105b6fc755a36df4c66e8f8aeecbb49608899ecbc05f85529952f&X-Amz-SignedHeaders=host"
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "text/event-stream"
}

def save_image_from_url(url: str, filename: str = "generated_image.png"):
    try:
        print(f"\n[+] Đang tải ảnh từ URL về máy: {url}")
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                f.write(r.content)
            print(f"[✓] Đã lưu ảnh thành công vào: {os.path.abspath(filename)}")
        else:
            print(f"[!] Tải ảnh thất bại, mã HTTP: {r.status_code}")
    except Exception as e:
        print(f"[!] Lỗi khi tải ảnh: {e}")

def save_image_from_b64(b64_data: str, filename: str = "generated_image.png"):
    try:
        print(f"\n[+] Đang giải mã và lưu ảnh Base64...")
        image_bytes = base64.b64decode(b64_data)
        with open(filename, "wb") as f:
            f.write(image_bytes)
        print(f"[✓] Đã lưu ảnh thành công vào: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"[!] Lỗi khi giải mã ảnh Base64: {e}")

def check_and_extract_image(data_obj):
    """Kiểm tra và bóc tách link ảnh hoặc base64 nếu có trong response"""
    if isinstance(data_obj, dict):
        # Trường hợp chuẩn OpenAI format: {"data": [{"url": "..."}, {"b64_json": "..."}]}
        if "data" in data_obj and isinstance(data_obj["data"], list):
            for i, item in enumerate(data_obj["data"]):
                if isinstance(item, dict):
                    if "url" in item and item["url"]:
                        save_image_from_url(item["url"], f"generated_image_{i+1}.png")
                    elif "b64_json" in item and item["b64_json"]:
                        save_image_from_b64(item["b64_json"], f"generated_image_{i+1}.png")
        # Trường hợp trả về trực tiếp { "url": "..." } hoặc { "image": "..." }
        for key in ["url", "image", "image_url"]:
            if key in data_obj and isinstance(data_obj[key], str) and data_obj[key].startswith("http"):
                save_image_from_url(data_obj[key])
                break

def main():
    if API_KEY == "xxxxxxxxxxxxxxxxx":
        print("[!] Chú ý: Bạn chưa điền API Token vào biến API_KEY ở đầu file.")
        print("[!] Hãy mở file và thay đổi 'xxxxxxxxxxxxxxxxx' thành token của bạn trước khi chạy.\n")

    print(f"[*] Đang gửi request tới: {API_URL}")
    print(f"[*] Model: {payload['model']}")
    print("-" * 60)

    try:
        # Gửi request với stream=True để nhận cả SSE lẫn response thông thường
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=120
        )

        content_type = response.headers.get("Content-Type", "")
        print(f"[*] Trạng thái phản hồi: {response.status_code}")
        print(f"[*] Content-Type: {content_type}\n")

        if response.status_code != 200:
            print("[X] Yêu cầu thất bại:")
            print(response.text)
            return

        # Nếu server trả về SSE (text/event-stream)
        if "text/event-stream" in content_type:
            print("[*] Đang nhận luồng sự kiện (SSE stream)...")
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8")
                print(line)

                if line.startswith("data: "):
                    data_part = line[6:].strip()
                    if data_part == "[DONE]":
                        print("\n[✓] Luồng sự kiện kết thúc ([DONE]).")
                        break
                    try:
                        parsed = json.loads(data_part)
                        check_and_extract_image(parsed)
                    except json.JSONDecodeError:
                        pass
        else:
            # Nếu server trả về JSON tiêu chuẩn
            try:
                result = response.json()
                print("[*] Kết quả JSON nhận được:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                check_and_extract_image(result)
            except Exception:
                print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"[X] Lỗi kết nối mạng: {e}")
    except Exception as e:
        print(f"[X] Đã xảy ra lỗi: {e}")

if __name__ == "__main__":
    main()
