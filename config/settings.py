from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_APPROVED_USER_ID: int
    CRON_SECRET: str = ""
    RSS_FEEDS: str = "https://techcrunch.com/feed/,https://feeds.feedburner.com/oreilly/radar/blogcomments"
    LOG_LEVEL: str = "INFO"

    @property
    def rss_feed_list(self) -> list[str]:
        return [f.strip() for f in self.RSS_FEEDS.split(",") if f.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
