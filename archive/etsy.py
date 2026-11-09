"""ينشئ مسودة (draft) فقط. أنت تراجع وتنشر يدوياً من لوحة Etsy."""
import os, requests
B = "https://openapi.etsy.com/v3/application"

def _h():
    return {"x-api-key": os.environ["ETSY_API_KEY"],
            "Authorization": f"Bearer {os.environ['ETSY_ACCESS_TOKEN']}"}

def create_draft(meta, pdf_path, cover_path, price=4.99, taxonomy_id=None):
    shop = os.environ["ETSY_SHOP_ID"]
    data = {"quantity": 999, "title": meta["title"][:140], "description": meta["description"],
            "price": price, "who_made": "i_did", "when_made": "made_to_order",
            "taxonomy_id": taxonomy_id or 0, "type": "download",
            "tags": ",".join(meta["tags"][:13]),
            "is_supply": False}
    # ملاحظة: Etsy تطلب الإفصاح عن استخدام AI؛ راجع حقل production partner/وصف المنتج.
    r = requests.post(f"{B}/shops/{shop}/listings", headers=_h(), data=data, timeout=60)
    r.raise_for_status(); lid = r.json()["listing_id"]
    with open(pdf_path, "rb") as f:
        requests.post(f"{B}/shops/{shop}/listings/{lid}/files", headers=_h(),
                      files={"file": f}, data={"name": os.path.basename(pdf_path)}, timeout=120).raise_for_status()
    with open(cover_path, "rb") as f:
        requests.post(f"{B}/shops/{shop}/listings/{lid}/images", headers=_h(),
                      files={"image": f}, timeout=120).raise_for_status()
    return lid
