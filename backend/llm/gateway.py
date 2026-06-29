from collections.abc import AsyncIterator
import litellm
from backend.config import settings
from backend.observability.logging import get_logger
from backend.observability.tracing import tracer

log = get_logger(__name__)

litellm.api_key = settings.gemini_api_key


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
        """Make a single non-streaming LLM call."""
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


llm = LLMGateway()