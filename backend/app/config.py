"""Configuration management for Ivan Task Manager."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./ivan_tasks.db"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = (
        "https://ai-devteam-resource.cognitiveservices.azure.com"
    )
    azure_openai_deployment: str = "gpt-5.2-codex"

    # ClickUp
    clickup_api_token: str = ""
    clickup_list_id: str = "901215490741"

    # GitHub
    github_token: str = ""
    github_repo: str = "markster-exec/project-tracker"

    # Slack
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_ivan_user_id: str = "U084S552VRD"

    # Writer settings
    clickup_complete_status: str = "complete"

    # Webhook secrets (for signature verification)
    clickup_webhook_secret: str = ""
    github_webhook_secret: str = ""

    # Scheduling
    morning_briefing_time: str = "07:00"
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    sync_interval_minutes: int = 60
    user_timezone: str = "America/Los_Angeles"

    # App
    log_level: str = "INFO"
    env: str = "development"

    # Entity settings
    entities_dir: str = "entities"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
