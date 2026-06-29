import logging
import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for the entire application.
    
    Call this once at startup in main.py. After that, every module
    gets a logger via: log = structlog.get_logger()
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure standard library logging first
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    # Configure structlog processors
    structlog.configure(
        processors=[
            # Add log level to every event
            structlog.stdlib.add_log_level,
            # Add timestamp to every event
            structlog.processors.TimeStamper(fmt="iso"),
            # Add file + line number in debug mode
            structlog.stdlib.add_logger_name,
            # Render as JSON in production, colored text in dev
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance for a module.
    
    Usage:
        log = get_logger(__name__)
        log.info("chat_request_received", user_id="123", message_length=42)
    """
    return structlog.get_logger(name)