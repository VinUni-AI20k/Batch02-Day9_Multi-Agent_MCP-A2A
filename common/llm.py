"""Shared LLM factory for all agents.

Uses OpenRouter as an OpenAI-compatible API, so any provider's model
can be selected via the OPENROUTER_MODEL env var.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Sequence
from uuid import uuid4

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import Field

DEFAULT_OPENROUTER_MODEL = "openrouter/free"
_fallback_warning_keys: set[str] = set()


def _warn_fallback(reason: str) -> None:
    show = os.getenv("OPENROUTER_SHOW_FALLBACK_REASON", "true").lower()
    if show not in {"1", "true", "yes", "on"}:
        return
    if reason in _fallback_warning_keys:
        return
    _fallback_warning_keys.add(reason)
    print(f"[OpenRouter fallback] {reason}", file=sys.stderr)


class LocalFallbackChatModel(BaseChatModel):
    """Small deterministic fallback used when no OpenRouter API key is configured."""

    bound_tools: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "local-fallback-chat-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "LocalFallbackChatModel":
        return self.model_copy(update={"bound_tools": list(tools)})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        content, tool_calls = self._next_response(messages)
        message = AIMessage(content=content, tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, **kwargs)

    def _next_response(self, messages: list[BaseMessage]) -> tuple[str, list[dict[str, Any]]]:
        question = self._last_human_text(messages)
        prompt_text = "\n".join(str(getattr(msg, "content", "")) for msg in messages)

        if "needs_tax" in prompt_text and "needs_compliance" in prompt_text:
            return json.dumps(self._route_flags(question)), []

        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
        if tool_messages:
            combined = "\n\n".join(str(msg.content) for msg in tool_messages)
            return self._summarize_tool_results(question, combined), []

        tool_calls = self._choose_tool_calls(question)
        if tool_calls:
            return "", tool_calls

        return self._direct_answer(question, prompt_text), []

    def _choose_tool_calls(self, question: str) -> list[dict[str, Any]]:
        question_lower = question.lower()
        calls: list[dict[str, Any]] = []

        for tool in self.bound_tools:
            name = self._tool_name(tool)
            args: dict[str, Any] | None = None

            if name == "delegate_to_legal_agent":
                args = {"question": question}
            elif name in {"search_legal_knowledge", "search_legal_database"}:
                args = {"query": question}
            elif name == "check_statute_of_limitations" and any(
                kw in question_lower for kw in ["statute", "limitations", "thoi hieu", "thời hiệu", "contract", "hợp đồng"]
            ):
                args = {"case_type": "contract"}
            elif name == "search_case_law" and any(
                kw in question_lower for kw in ["breach", "contract", "negligence", "tort"]
            ):
                args = {"keywords": question}
            elif name == "calculate_penalty" and any(
                kw in question_lower for kw in ["tax", "privacy", "data", "contract", "penalty", "fine"]
            ):
                args = {
                    "violation_type": self._violation_type(question_lower),
                    "severity": "high",
                    "annual_revenue": 5_000_000.0,
                }
            elif name == "check_compliance_requirements" and any(
                kw in question_lower for kw in ["startup", "company", "compliance", "regulatory", "technology", "tech"]
            ):
                args = {"industry": "technology", "company_size": "startup"}
            elif name == "search_tax_law" and any(
                kw in question_lower for kw in ["tax", "irs", "thuế", "evasion", "avoid"]
            ):
                args = {"query": question}
            elif name == "search_compliance_law" and any(
                kw in question_lower for kw in ["compliance", "regulatory", "sec", "privacy", "data", "gdpr"]
            ):
                args = {"query": question}

            if args is not None:
                calls.append({"name": name, "args": args, "id": f"call_{uuid4().hex}"})

        return calls

    @staticmethod
    def _tool_name(tool: Any) -> str:
        return str(getattr(tool, "name", getattr(tool, "__name__", "")))

    @staticmethod
    def _last_human_text(messages: list[BaseMessage]) -> str:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return str(msg.content)
        return str(getattr(messages[-1], "content", "")) if messages else ""

    @staticmethod
    def _route_flags(question: str) -> dict[str, bool]:
        question_lower = question.lower()
        tax_keywords = ["tax", "taxes", "irs", "thuế", "evasion", "avoid", "offshore", "fbar", "fatca"]
        compliance_keywords = [
            "compliance",
            "regulatory",
            "regulation",
            "sec",
            "sox",
            "aml",
            "fcpa",
            "gdpr",
            "privacy",
            "data",
        ]
        return {
            "needs_tax": any(kw in question_lower for kw in tax_keywords),
            "needs_compliance": any(kw in question_lower for kw in compliance_keywords),
        }

    @staticmethod
    def _violation_type(question_lower: str) -> str:
        if "tax" in question_lower:
            return "tax_evasion"
        if "privacy" in question_lower or "data" in question_lower:
            return "data_privacy"
        if "contract" in question_lower or "breach" in question_lower:
            return "contract_breach"
        return "regulatory_violation"

    @staticmethod
    def _summarize_tool_results(question: str, combined: str) -> str:
        return (
            "Based on the retrieved specialist information, here is the concise analysis:\n\n"
            f"Question: {question}\n\n"
            f"{combined}\n\n"
            "Key takeaway: preserve evidence, quantify exposure, remediate quickly, and consult "
            "qualified counsel for jurisdiction-specific advice."
        )

    @staticmethod
    def _direct_answer(question: str, prompt_text: str) -> str:
        text = f"{prompt_text}\n{question}".lower()
        if "tổng hợp" in text or "synthesising" in text or "synthesizing" in text or "combine the following" in text:
            return (
                "Báo cáo tổng hợp:\n\n"
                f"{prompt_text[-1800:]}\n\n"
                "Khuyến nghị: lưu giữ chứng cứ, lượng hóa thiệt hại, khắc phục sớm, "
                "và tham vấn luật sư/chuyên gia phù hợp trước khi hành động."
            )
        if "chuyên gia thuế" in text or "tax attorney" in text or "specialist tax" in text:
            return (
                "Tax analysis: possible back taxes, interest, civil fraud penalties, audits, "
                "and criminal exposure if the conduct was willful."
            )
        if (
            "chuyên gia về gdpr" in text
            or "bảo vệ dữ liệu" in text
            or "data protection" in text
            or "privacy attorney" in text
        ):
            return (
                "Privacy analysis: a data incident can trigger notification duties, regulator "
                "investigations, GDPR/CCPA exposure, remediation costs, and customer claims."
            )
        if "chuyên gia compliance" in text or "compliance officer" in text or "regulatory compliance" in text:
            return (
                "Compliance analysis: regulators may impose civil penalties, monitoring, "
                "disgorgement, governance reforms, and individual accountability."
            )
        if "chuyên gia phân tích thiệt hại" in text or "financial" in text or "damage" in text or "thiệt hại" in text:
            return (
                "Financial analysis: estimate direct losses, consequential damages, penalties, "
                "legal fees, remediation costs, and business interruption."
            )
        if "tax" in text or "thuế" in text:
            return (
                "Tax analysis: possible back taxes, interest, civil fraud penalties, audits, "
                "and criminal exposure if the conduct was willful."
            )
        if "privacy" in text or "data" in text or "gdpr" in text:
            return (
                "Privacy analysis: a data incident can trigger notification duties, regulator "
                "investigations, GDPR/CCPA exposure, remediation costs, and customer claims."
            )
        if "compliance" in text or "regulatory" in text or "sec" in text:
            return (
                "Compliance analysis: regulators may impose civil penalties, monitoring, "
                "disgorgement, governance reforms, and individual accountability."
            )
        return (
            "Legal analysis: identify the governing law, contractual duties, breach evidence, "
            "available remedies, limitation periods, and practical mitigation steps."
        )


class ResilientChatModel(BaseChatModel):
    """OpenRouter model with local fallback for credit/auth/network failures."""

    primary: BaseChatModel
    fallback: LocalFallbackChatModel = Field(default_factory=LocalFallbackChatModel)
    tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "resilient-openrouter-chat-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ResilientChatModel":
        return self.model_copy(
            update={
                "primary": self.primary.bind_tools(tools, tool_choice=tool_choice, **kwargs),
                "fallback": self.fallback.bind_tools(tools, tool_choice=tool_choice, **kwargs),
                "tool_names": [self._tool_name(tool) for tool in tools],
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            message = self.primary.invoke(messages, stop=stop, **kwargs)
            if not isinstance(message, BaseMessage):
                message = AIMessage(content=str(message))
            self._normalize_tool_calls(message)
            return ChatResult(generations=[ChatGeneration(message=message)])
        except Exception as exc:
            _warn_fallback(f"{type(exc).__name__}: {exc}")
            self._close_primary_sync()
            return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            message = await asyncio.wait_for(
                self.primary.ainvoke(messages, stop=stop, **kwargs),
                timeout=_get_timeout_seconds(),
            )
            if not isinstance(message, BaseMessage):
                message = AIMessage(content=str(message))
            self._normalize_tool_calls(message)
            return ChatResult(generations=[ChatGeneration(message=message)])
        except Exception as exc:
            _warn_fallback(f"{type(exc).__name__}: {exc}")
            await self._close_primary_async()
            return await self.fallback._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _close_primary_sync(self) -> None:
        client = getattr(self.primary, "root_client", None)
        close = getattr(client, "close", None)
        if close:
            try:
                close()
            except Exception:
                pass

    async def _close_primary_async(self) -> None:
        client = getattr(self.primary, "root_async_client", None)
        close = getattr(client, "close", None)
        if close:
            try:
                await close()
            except Exception:
                pass

    def _normalize_tool_calls(self, message: BaseMessage) -> None:
        """Clean provider-specific suffixes that some free models append to tool names."""
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return
        for tool_call in tool_calls:
            raw_name = str(tool_call.get("name", ""))
            normalized = raw_name.split("<|", 1)[0].strip()
            if normalized in self.tool_names:
                tool_call["name"] = normalized

    @staticmethod
    def _tool_name(tool: Any) -> str:
        return str(getattr(tool, "name", getattr(tool, "__name__", "")))


def _get_max_tokens() -> int:
    raw = os.getenv("OPENROUTER_MAX_TOKENS", "4096")
    try:
        return int(raw)
    except ValueError:
        return 4096


def _get_timeout_seconds() -> float:
    raw = os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60")
    try:
        return float(raw)
    except ValueError:
        return 60.0


def _is_free_model(model: str) -> bool:
    return model == "openrouter/free" or model.endswith(":free")


def _get_model_name() -> str:
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
    force_free = os.getenv("OPENROUTER_FORCE_FREE", "true").lower() in {"1", "true", "yes", "on"}
    if force_free and not _is_free_model(model):
        return DEFAULT_OPENROUTER_MODEL
    return model


def get_llm() -> BaseChatModel:
    """Return an OpenRouter chat model, or a local fallback when no API key exists."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_key_here":
        _warn_fallback("OPENROUTER_API_KEY is missing or still set to placeholder.")
        return LocalFallbackChatModel()

    primary = ChatOpenAI(
        model=_get_model_name(),
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.3,
        max_completion_tokens=_get_max_tokens(),
        timeout=_get_timeout_seconds(),
        max_retries=0,
    )
    return ResilientChatModel(primary=primary)
