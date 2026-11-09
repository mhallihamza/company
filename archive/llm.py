"""طبقة موحدة للنماذج اللغوية. غيّر المزود من .env فقط:
LLM_PROVIDER=mistral | anthropic
LLM_MODEL=codestral-latest (للاختبار) أو mistral-large-latest أو claude-sonnet-5-5
"""
import os, json, re, requests
from dotenv import load_dotenv
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")

def ask(prompt: str, max_tokens=4000) -> str:
    if PROVIDER == "mistral":
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"},
            json={"model": MODEL, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    import anthropic
    r = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}])
    return r.content[0].text

def ask_json(prompt: str, max_tokens=4000):
    txt = ask(prompt + "\n\nReturn ONLY valid JSON, no markdown fences.", max_tokens)
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    return json.loads(txt)
