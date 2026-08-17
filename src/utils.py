import re
import random
import logging
from typing import Optional
from rich.logging import RichHandler

USER_AGENTS = [
    # macOS Chrome & Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Windows Chrome & Edge & Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Linux Chrome & Firefox
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
]

def get_random_user_agent() -> str:
    """Return a random realistic desktop browser User-Agent."""
    return random.choice(USER_AGENTS)

def clean_text(text: Optional[str]) -> str:
    """Normalize whitespace and strip text."""
    if not text:
        return ""
    # Collapse multiple spaces, newlines and tabs
    return re.sub(r"\s+", " ", text).strip()

def hex_to_discord_color(hex_color: Optional[str], default: int = 0x0A66C2) -> int:
    """Convert hex string (e.g., '#3776AB' or '3776AB') to Discord embed integer color."""
    if not hex_color:
        return default
    clean_hex = hex_color.lstrip("#")
    try:
        return int(clean_hex, 16)
    except ValueError:
        return default

def setup_logger(log_level: str = "INFO") -> logging.Logger:
    """Setup and configure formatted rich logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
    )
    logger = logging.getLogger("job_bot")
    logger.setLevel(level)
    return logger
