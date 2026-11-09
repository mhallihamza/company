"""مولّد الصور. لتثبيت شكل الشخصية: نكرر character_sheet + style في كل طلب.
يمكنك استبدال الدالة بأي مزود آخر (Flux, Replicate...)."""
import base64

def generate(story, i, out):
    page = story["pages"][i]
    prompt = (f"Children's book illustration, {story['style']}. "
              f"Characters (keep identical in every page): {story['character_sheet']}. "
              f"Scene: {page['image_prompt']}. No text, no letters in the image.")
    from openai import OpenAI
    r = OpenAI().images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
    open(out, "wb").write(base64.b64decode(r.data[0].b64_json))
