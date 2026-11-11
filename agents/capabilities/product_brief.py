"""Product brief generator — approved idea → concrete, production-ready brief.

Central to the flow: the CEO recommends, the founder approves the brief, and only then
does books.content generate. Never generate a full product before a brief is approved.
"""
from __future__ import annotations
import json

PRODUCT_TYPES = {
    "coloring_book": {
        "label": "Coloring Book",
        "page_count": 24,
        "format": "printable",
        "default_price_usd": 6.99,
        "description": "Black & white coloring pages with thick outlines, no numbers on pages",
        "structure": "Cover + 22 coloring pages + activities intro page + back page",
    },
    "drawing_workbook": {
        "label": "Drawing Workbook",
        "page_count": 24,
        "format": "trim_6x9",
        "default_price_usd": 9.99,
        "description": "Step-by-step drawing instructions, finish the drawing, practice sections",
        "structure": "Cover + how-to-draw title + 21 skill pages + encouragement last page",
    },
    "painting_workbook": {
        "label": "Painting Activity Book",
        "page_count": 24,
        "format": "trim_6x9",
        "default_price_usd": 9.99,
        "description": "Simple painting prompts, color-by-shape, mixing exercises",
        "structure": "Cover + color theory intro + 21 painting exercises + back page",
    },
    "activity_workbook": {
        "label": "Activity Workbook",
        "page_count": 32,
        "format": "trim_6x9",
        "default_price_usd": 12.99,
        "description": "Tracing, mazes, matching, sorting, counting - mixed skills",
        "structure": "Cover + alphabet tracing + 30 skill pages + final certificate",
    },
    "tracing_workbook": {
        "label": "Tracing & Handwriting Workbook",
        "page_count": 32,
        "format": "trim_6x9",
        "default_price_usd": 9.99,
        "description": "Letter tracing, word tracing, line control, dotted guides",
        "structure": "Cover + A-Z tracing + 30 pages of guided writing practice",
    },
    "alphabet_workbook": {
        "label": "Alphabet Activity Workbook",
        "page_count": 32,
        "format": "trim_6x9",
        "default_price_usd": 9.99,
        "description": "ABC recognition, matching, tracing, vocabulary, simple phonics",
        "structure": "Cover + A-Z sections + 30 pages + certificate of completion",
    },
    "matching_activity": {
        "label": "Matching Activities Pack",
        "page_count": 24,
        "format": "printable",
        "default_price_usd": 7.99,
        "description": "Match shapes, match letters, match animals, find the pair",
        "structure": "Cover + instructions + 22 matching worksheets",
    },
    "maze_book": {
        "label": "Mazes Book",
        "page_count": 24,
        "format": "printable",
        "default_price_usd": 6.99,
        "description": "Progressive maze difficulty + themed illustrations",
        "structure": "Cover + simple mazes → harder mazes + word searches bonus",
    },
    "educational_bundle": {
        "label": "Educational Bundle",
        "page_count": 42,
        "format": "bundle",
        "default_price_usd": 19.99,
        "description": "Coloring + tracing + counting + matching in one ZIP",
        "structure": "Cover + 6 sub-activity packs + instructions + print guide",
    },
}


def product_types() -> list[dict]:
    return [{"key": k, **v} for k, v in PRODUCT_TYPES.items()]


def build_brief(approved_niche: dict, marketplace: str, product_type: str) -> dict | None:
    spec = PRODUCT_TYPES.get(product_type)
    if not spec:
        return None
    age = approved_niche.get("age", "3-5") or "3-5"
    return {
        "product_type": product_type,
        "title": approved_niche.get("title") or spec["label"],
        "target_age": age,
        "target_audience": f"Parents of children aged {age}",
        "format": spec["format"],
        "page_count": spec["page_count"],
        "marketplace": marketplace,
        "description": spec["description"],
        "structure": spec["structure"],
        "content_plan": _content_plan(product_type, approved_niche),
        "differentiation": approved_niche.get("differentiation", "See competitor examples in the research envelope."),
        "price_range": {"low": round(spec["default_price_usd"] * 0.8, 2),
                        "suggested": spec["default_price_usd"],
                        "high": round(spec["default_price_usd"] * 1.3, 2)},
        "niche": approved_niche.get("niche", "drawing"),
        "keywords": approved_niche.get("keywords") or _keywords_for(product_type, approved_niche),
        "approval_policy": "brief_approval",
        "status": "pending_approval",
    }


def _content_plan(product_type: str, approved_niche: dict) -> list[str]:
    plan = {
        "coloring_book":      ["Cover", "Title page", "Instructions page", "Animals (6 pages)",
                               "Vehicles (5 pages)", "Nature (5 pages)", "Daily life (4 pages)",
                               "Bonus: hidden object page"],
        "drawing_workbook":   ["Cover", "How to hold a pencil", "Lines & shapes (3 page practice)",
                               "Simple characters (10 pages)", "Animals (4 pages)",
                               "Your own drawing (1 page)", "Certificate of completion"],
        "painting_workbook":  ["Cover", "Color wheel intro", "Primary colors (4 pages)",
                               "Brush strokes (3 pages)", "Paint-by-number (9 pages)",
                               "My painting (1 page)", "Certificate"],
        "activity_workbook":  ["Cover", "Letters A-E (5 pages)", "Numbers 1-10 (5 pages)",
                               "Matching animals (5 pages)", "Mazes (5 pages)",
                               "Color & count (5 pages)", "Certificate"],
        "tracing_workbook":   ["Cover", "Lines (curves, zigzags) (5 pages)",
                               "Lowercase a-m (7 pages)", "Uppercase A-M (7 pages)",
                               "Small words (matching) (5 pages)", "Certificate"],
        "alphabet_workbook":  ["Cover", "A-F (6 pages)", "G-L (6 pages)", "M-R (6 pages)",
                               "S-Z (6 pages)", "Alphabetical order (2 pages)",
                               "Word hunt (1 page)", "Certificate"],
        "matching_activity":  ["Cover", "Shapes (4 pages)", "Animals (4 pages)",
                               "Letters (5 pages)", "Fruit (4 pages)", "Vehicles (4 pages)",
                               "Answer key (1 page)"],
        "maze_book":          ["Cover", "Simple mazes (8 pages)", "Intermediate mazes (8 pages)",
                               "Hard mazes (5 pages)", "Word search bonus (1 page)"],
        "educational_bundle": ["Cover", "Contents (1 page)","ABC tracing (4 pages)",
                               "Numbers (4 pages)", "Animals coloring (4 pages)",
                               "Matching (4 pages)", "Mazes (4 pages)"],
    }
    return plan.get(product_type, plan["coloring_book"])


def _keywords_for(product_type: str, approved_niche: dict) -> list[str]:
    base = ["kids book", product_type.replace("_", " "), "ages 3-5", "preschool"]
    seeds = approved_niche.get("seeds", []) if isinstance(approved_niche.get("seeds"), list) else []
    return list(dict.fromkeys(base + [str(s) for s in seeds[:5]]))[:13]
