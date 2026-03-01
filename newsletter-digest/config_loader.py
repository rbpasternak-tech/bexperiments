"""Load and validate the config.yaml configuration file."""

import os
import yaml


def load_config(config_path=None):
    """Load configuration from config.yaml.

    Args:
        config_path: Path to config file. Defaults to config.yaml in the same directory.

    Returns:
        dict with validated configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If required fields are missing.
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Validate required sections
    required_sections = ["gmail", "newsletters", "rss_feeds", "summarizer", "digest"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section: {section}")

    if "recipient_email" not in config["gmail"]:
        raise ValueError("Missing gmail.recipient_email in config")

    if not config.get("rss_feeds"):
        raise ValueError("rss_feeds must contain at least one feed")

    # Apply defaults
    config["gmail"].setdefault("lookback_days", 4)
    config["gmail"].setdefault("max_emails", 200)
    config["newsletters"].setdefault("sender_whitelist", [])
    config["newsletters"].setdefault("keywords", [])
    config["summarizer"].setdefault("model", "claude-sonnet-4-20250514")
    config["summarizer"].setdefault("max_tokens", 4096)
    config["digest"].setdefault("subject_prefix", "Your Tech & Legal Tech Digest")

    return config
