from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import litellm

from backend.config import settings
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer

log = get_logger(__name__)

litellm.api_key = settings.gemini_api_key


# ---------------------------------------------------------------------------
# Response container for tool-calling completions
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRequest:
    """
    Represents a single tool call the LLM wants to make.

    Attributes:
        id:        Unique call ID returned by the LLM (needed for tool result messages).
        name:      Tool name — matches a key in executor._HANDLERS.
        arguments: Parsed argument dict ready to pass to execute_tool_call().
    """
    id: str
    name: str
    arguments: dict


@dataclass
class ToolCallResponse:
    """
    Unified return type from complete_with_tools().

    Exactly one of text or tool_calls will be populated:
      - text       → LLM gave a final answer, no tool needed
      - tool_calls → LLM wants to call one or more tools before answering
    """
    text: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def wants_tool(self) -> bool:
        """True if the LLM requested at least one tool call."""
        return len(self.tool_calls) > 0


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class LLMGateway:
    """Unified gateway for all LLM calls in the application."""

    def __init__(self) -> None:
        self.primary_model = settings.primary_model
        self.fallback_model = settings.fallback_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        trace=None,
        trace_name: str = "llm_complete",
    ) -> str:
        """Make a single non-streaming LLM call. Returns text only."""
        target_model = model or self.primary_model

        try:
            log.info("llm_call_start", model=target_model, messages=len(messages))

            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            completion = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            log.info(
                "llm_call_success",
                model=target_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            tracer.log_generation(
                trace=trace,
                name=trace_name,
                model=target_model,
                prompt=str(messages),
                completion=completion,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            return completion

        except Exception as e:
            log.warning("llm_call_failed", model=target_model, error=str(e))
            if target_model == self.primary_model and self.fallback_model:
                log.info("llm_fallback_triggered", fallback=self.fallback_model)
                return await self.complete(
                    messages=messages,
                    model=self.fallback_model,
                    trace=trace,
                    trace_name=trace_name,
                )
            raise

    async def stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the LLM one by one."""
        target_model = model or self.primary_model

        try:
            log.info("llm_stream_start", model=target_model)

            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )

            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

            log.info("llm_stream_complete", model=target_model)

        except Exception as e:
            log.error("llm_stream_failed", model=target_model, error=str(e))
            raise

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
    ) -> ToolCallResponse:
        """
        Send messages + tool definitions to the LLM.

        The LLM will either:
          (a) Return a final text answer  → ToolCallResponse(text="...")
          (b) Request tool calls          → ToolCallResponse(tool_calls=[...])

        Args:
            messages: Full conversation history in OpenAI format.
            tools:    Tool definitions from registry.get_tools_for_context().
            model:    Override model. Defaults to primary_model.

        Returns:
            ToolCallResponse with either text or tool_calls populated.
        """
        target_model = model or self.primary_model

        log.info(
            "llm_tool_call_start",
            model=target_model,
            num_tools=len(tools),
            num_messages=len(messages),
        )

        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",   # let the LLM decide when to use tools
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        except Exception as e:
            log.error("llm_tool_call_failed", model=target_model, error=str(e))
            raise

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        message = choice.message

        log.info("llm_tool_call_response", finish_reason=finish_reason)

        # LLM wants to call one or more tools
        if finish_reason == "tool_calls" and message.tool_calls:
            requests = []
            for tc in message.tool_calls:
                # arguments come back as a JSON string — parse to dict
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                    log.warning(
                        "tool_args_parse_failed",
                        raw=tc.function.arguments,
                    )
                requests.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
                log.info(
                    "tool_call_requested",
                    tool=tc.function.name,
                    args=args,
                )
            return ToolCallResponse(tool_calls=requests)

        # LLM gave a direct text answer
        text = message.content or ""
        log.info("llm_tool_call_text_response", length=len(text))
        return ToolCallResponse(text=text)


llm = LLMGateway()