"""مصنع النماذج اللغوية — يختار المزود من .env أو وضع المحاكاة.

LLM_PROVIDER = mistral | anthropic | openai | fake
لا حاجة لأي مزود عند KIDBOOK_FAKE_LLM=1 أو غياب كل المفاتيح.

النموذج الحقيقي مغلّف بـ ResilientChatModel: أي فشل (تجاوز حد 429، شبكة،
مفاتيح) يرتد فوراً إلى المحاكي الحتمي مع تسجيل السبب في llm_last_note()
ليظهر في اللوحة والتقارير بدل أن يفشل القسم كله.
"""
from __future__ import annotations
import os
import threading
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from kidbook import config

_last_note = "nothing yet"
_note_lock = threading.Lock()


def llm_last_note() -> str:
    return _last_note


def _note(msg: str):
    global _last_note
    with _note_lock:
        _last_note = msg


def _fake() -> BaseChatModel:
    from kidbook.fake_llm import ScriptedChatModel
    return ScriptedChatModel()


class ResilientChatModel(BaseChatModel):
    """يرفع للنموذج الحقيقي ويرتد للمحاكي عند أي عطل — بلا انقطاع للقسم."""

    primary: Any
    fallback: Any
    label: str

    @property
    def _llm_type(self) -> str:
        try:
            return f"resilient({self.primary._llm_type})"  # noqa: SLF001
        except Exception:  # noqa: BLE001
            return "resilient"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        try:
            result = self.primary._generate(  # noqa: SLF001 — نعيد الاستخدام الحرفي
                messages, stop=stop, run_manager=run_manager, **kwargs)
            _note(f"لوكلات {self.label}: استُخدم النموذج الحقيقي")
            return result
        except Exception as e:  # noqa: BLE001 — نعرض السبب ثم نتابع بالمحاكي
            reason = str(e)[:300]
            _note(f"لوكلات {self.label}: فشل النموذج الحقيقي ({reason}) — استُخدم المحاكي")
            return self.fallback._generate(messages, stop=stop,  # noqa: SLF001
                                           run_manager=run_manager, **kwargs)


def get_chat_model(temperature: float = 0.4, max_tokens: int = 4000) -> BaseChatModel:
    """يعيد نموذجاً جاهزاً. يسقط إلى وضع المحاكاة إن غابت المفاتيح."""
    if config.FAKE_LLM:
        return _fake()

    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("LLM_MODEL", "")
    try:
        if provider == "mistral":
            if not os.getenv("MISTRAL_API_KEY"):
                _note("لا مفتاح Mistral — المحاكي")
                return _fake()
            from langchain_mistralai import ChatMistralAI
            primary = ChatMistralAI(model=model or "mistral-small-latest",
                                    temperature=temperature, max_tokens=max_tokens)
            return ResilientChatModel(primary=primary, fallback=_fake(),
                                      label=f"mistral:{model or 'mistral-small'}")
        if provider == "anthropic":
            if not os.getenv("ANTHROPIC_API_KEY"):
                if os.getenv("MISTRAL_API_KEY"):
                    os.environ["LLM_PROVIDER"] = "mistral"  # يعاد تدويره في الاستدعاء القادم
                    return get_chat_model(temperature, max_tokens)
                _note("لا مفتاح Anthropic — المحاكي")
                return _fake()
            from langchain_anthropic import ChatAnthropic
            primary = ChatAnthropic(model=model or "claude-sonnet-4-5",
                                    temperature=temperature, max_tokens=max_tokens)
            return ResilientChatModel(primary=primary, fallback=_fake(),
                                      label=f"anthropic:{model or 'sonnet'}")
        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                _note("لا مفتاح OpenAI — المحاكي")
                return _fake()
            from langchain_openai import ChatOpenAI
            primary = ChatOpenAI(model=model or "gpt-4o-mini",
                                 temperature=temperature, max_tokens=max_tokens)
            return ResilientChatModel(primary=primary, fallback=_fake(),
                                      label=f"openai:{model or 'gpt4o-mini'}")
    except ImportError:
        _note(f"مزود {provider} غير مثبت — المحاكي")
        return _fake()
    _note(f"مزود غير معروف {provider} — المحاكي")
    return _fake()


def mode_label() -> str:
    if config.FAKE_LLM:
        return "fake (تجريبي)"
    provider = os.getenv("LLM_PROVIDER", "?")
    return f"live:{provider}"
