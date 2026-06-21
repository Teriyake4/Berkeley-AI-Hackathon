"""
Vision prompt — Claude vision identification of ambulance-cabin camera frames.
"""
from __future__ import annotations

VISION_PROMPT = (
    "Look at this image from an ambulance cabin camera. Identify if it shows: "
    "a medication vial/bottle/ampoule (read the label if legible), a medical "
    "alert bracelet, or a visible wound/injury. Respond ONLY with JSON, no "
    "other text: {\"identified\": boolean, \"type\": \"medication\"|\"bracelet\"|"
    "\"wound\"|\"none\", \"label_text\": string|null, \"confidence\": \"high\"|"
    "\"medium\"|\"low\"}"
)


def to_capture_type(t: str) -> str:
    """Map the VLM's `type` field to a VisionCapturedPayload.captureType."""
    return {
        "medication": "vial_label",
        "bracelet": "bracelet",
        "wound": "wound",
    }.get((t or "").lower(), "none")
