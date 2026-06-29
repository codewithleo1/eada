from langfuse import Langfuse
from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)


def get_langfuse_client() -> Langfuse | None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.info("langfuse_disabled", reason="No credentials configured")
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


class Tracer:
    def __init__(self) -> None:
        self.client = get_langfuse_client()
        self.enabled = self.client is not None

    def create_trace(self, name: str, user_id: str = "anonymous", metadata: dict = {}):
        if not self.enabled:
            return None
        try:
            return self.client.trace(name=name, user_id=user_id, metadata=metadata)
        except Exception as e:
            log.warning("langfuse_trace_failed", error=str(e))
            return None

    def log_generation(self, trace, name: str, model: str, prompt: str,
                       completion: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        if not self.enabled or trace is None:
            return
        try:
            trace.generation(
                name=name, model=model, input=prompt, output=completion,
                usage={"input": input_tokens, "output": output_tokens},
            )
        except Exception as e:
            log.warning("langfuse_generation_failed", error=str(e))

    def flush(self) -> None:
        if self.enabled:
            try:
                self.client.flush()
            except Exception:
                pass


tracer = Tracer()