"""
xray_model_tool.py  (Version 4)
----------------------------------
Chest X-ray / bone X-ray abnormality detection using a HuggingFace vision model.

Model:
    openai/clip-vit-base-patch16 via zero-shot-image-classification pipeline.

V4 fix:
    ZeroShotImageClassificationPipeline requires the image as the FIRST
    positional argument AND candidate_labels as a keyword argument.
    Previous call used `images=img` (wrong keyword) which caused a
    TypeError: "missing 1 required positional argument: 'image'"
    that was silently caught, returning empty results, causing downstream
    LLaMA to hallucinate generic "cold and fever" for every X-ray upload.

Anti-hallucination:
    This tool ONLY returns model predictions with confidence scores.
    It does NOT confirm any diagnosis. LLaMA explains the findings
    with a mandatory medical disclaimer.

Returns:
    dict: {"findings": str, "confidence": float, "raw_labels": list}
"""

import io

try:
    from PIL import Image
    from transformers import pipeline
except ImportError:
    Image = None        # type: ignore
    pipeline = None     # type: ignore

# Lazy singleton for the classification pipeline
_classifier = None


def _get_classifier():
    """Lazily initializes the HuggingFace image classifier."""
    global _classifier
    if _classifier is None and pipeline is not None:
        try:
            _classifier = pipeline(
                "zero-shot-image-classification",
                model="openai/clip-vit-base-patch16",
            )
        except Exception as e:
            print(f"[xray_model_tool] Failed to load model: {e}")
    return _classifier


# Candidate labels for chest X-ray / bone X-ray classification
# Added "bone fracture" and "broken bone" so the model can detect limb fractures
_XRAY_LABELS = [
    "normal chest x-ray",
    "pneumonia",
    "pleural effusion",
    "cardiomegaly",
    "lung opacity",
    "atelectasis",
    "pneumothorax",
    "fracture",
    "bone fracture",
    "broken bone",
    "consolidation",
    "edema",
]


def analyze_xray(image_bytes: bytes) -> dict:
    """
    Classifies a chest/bone X-ray image against common abnormality labels.

    Accepts raw image bytes (JPEG, PNG, WebP, BMP, TIFF, GIF) directly
    from the in-memory upload pipeline — no temp file required.

    Args:
        image_bytes: Raw bytes of the X-ray image file.

    Returns:
        dict: {
            "findings": str (human-readable summary),
            "confidence": float (top prediction confidence),
            "raw_labels": list (top 3 predictions with scores)
        }
    """
    empty_result = {
        "findings": "Unable to analyze X-ray image.",
        "confidence": 0.0,
        "raw_labels": [],
    }

    if pipeline is None or Image is None:
        print("[xray_model_tool] transformers or Pillow not installed.")
        return empty_result

    if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
        print("[xray_model_tool] No image bytes provided.")
        return empty_result

    classifier = _get_classifier()
    if classifier is None:
        return empty_result

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # ── V4 Fix: correct pipeline call signature ───────────────────────────
        # ZeroShotImageClassificationPipeline call signature:
        #   pipeline(image, candidate_labels=...)  ← image as FIRST positional arg
        # NOT:
        #   pipeline(images=img, ...)              ← 'images' is the wrong keyword
        # The wrong keyword caused TypeError that was caught and returned empty_result,
        # so LLaMA had no X-ray context and hallucinated generic symptoms.
        results = classifier(img, candidate_labels=_XRAY_LABELS)

        # Take top 3 predictions
        top_3 = results[:3] if len(results) >= 3 else results
        raw_labels = [
            {"label": r["label"], "score": round(r["score"], 3)}
            for r in top_3
        ]

        top_label = top_3[0]["label"] if top_3 else "unknown"
        top_score = top_3[0]["score"] if top_3 else 0.0

        # Build human-readable findings
        if top_label == "normal chest x-ray" and top_score > 0.5:
            findings = "No significant abnormalities detected in the X-ray."
        else:
            findings_list = ", ".join(
                f"{r['label']} ({r['score']:.0%})" for r in raw_labels
            )
            findings = f"Potential findings: {findings_list}."

        findings += (
            "\n\n⚠️ DISCLAIMER: This is an AI-assisted screening tool. "
            "These findings MUST be reviewed by a qualified radiologist. "
            "Do NOT use this as a definitive diagnosis."
        )

        return {
            "findings": findings,
            "confidence": round(top_score, 3),
            "raw_labels": raw_labels,
        }

    except Exception as e:
        print(f"[xray_model_tool] X-ray analysis failed: {e}")
        return empty_result
