from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALLOW_REGISTRATION: bool = True
    FIRST_USER_IS_ADMIN: bool = True
    BLOCKED_EMAIL_DOMAINS: list[str] = []
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "gemma4:e4b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-latest"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    TTS_PROVIDER: str = "local"  # local | openai
    TTS_BASE_URL: str = "http://kokoro:8880"
    TTS_VOICE: str = "af_heart"
    OPENAI_TTS_MODEL: str = "tts-1"
    OPENAI_TTS_VOICE: str = "nova"
    OPENAI_TTS_SPEED: float = 1.0
    STT_PROVIDER: str = "local"  # local | openai
    STT_BASE_URL: str = "http://whisper:9000"
    OPENAI_STT_MODEL: str = "whisper-1"
    RATE_LIMIT_ENABLED: bool = True
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    COOKIE_SECURE: bool = False
    LOG_LEVEL: str = "INFO"

    # Default AI usage quotas for new/subscribed users. A quota value of 0 means unlimited.
    DEFAULT_CONVERSATION_MAX_DURATION: int = 1800
    DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT: int = 180
    DEFAULT_CONVERSATION_WEEKLY_SESSIONS: int = 0
    DEFAULT_CONVERSATION_DAILY_MINUTES: int = 30
    DEFAULT_CONVERSATION_WEEKLY_MINUTES: int = 90
    DEFAULT_MONTHLY_TOKENS_LIMIT: int = 1_000_000
    ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS: int = 300

    # Freemium quotas for unsubscribed users when STRIPE_ENABLED=true.
    # A quota value of 0 means the feature is entirely blocked for free users.
    FREEMIUM_CHAT_DAILY_MESSAGES: int = 5
    FREEMIUM_LESSONS_DAILY: int = 3
    FREEMIUM_LISTENING_WEEKLY: int = 3
    FREEMIUM_READING_WEEKLY: int = 3
    FREEMIUM_VOICE_WEEKLY_MINUTES: int = 5
    FREEMIUM_TRIAL_ENABLED: bool = True
    FREEMIUM_TRIAL_DAYS: int = 7

    # Stripe (for paid plans and billing management)
    STRIPE_ENABLED: bool = False
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_MONTHLY: str = ""
    STRIPE_PRICE_YEARLY: str = ""
    STRIPE_TRIAL_DAYS: int = 7
    STRIPE_BASE_URL: str = "http://localhost:3000"

    # Display prices (shown on landing page and paywall banner)
    PRICE_MONTHLY: float = 0.0
    PRICE_YEARLY: float = 0.0
    TOTAL_PRICE_MONTHLY: float = 0.0
    TOTAL_PRICE_YEARLY: float = 0.0

    # Email / SMTP
    EMAIL_ENABLED: bool = False
    CONTACT_EMAIL: str = ""
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@freelingo.app"
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    APP_BASE_URL: str = "http://localhost:3000"

    # Listening — path where generated MP3 files are stored (Docker volume)
    AUDIO_STORAGE_PATH: str = "/data/audio"

    # Multi-language — operator-configured subset of supported target languages.
    AVAILABLE_TARGET_LANGUAGES: list[str] = [
        "de-DE",
        "en-GB",
        "en-US",
        "es-ES",
        "fr-FR",
        "it-IT",
        "ja-JP",
        "ko-KR",
        "pt-PT",
        "zh-CN",
    ]

    @field_validator(
        "DEFAULT_CONVERSATION_WEEKLY_SESSIONS",
        "DEFAULT_CONVERSATION_DAILY_MINUTES",
        "DEFAULT_CONVERSATION_WEEKLY_MINUTES",
        "DEFAULT_MONTHLY_TOKENS_LIMIT",
    )
    @classmethod
    def validate_unlimited_quota(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Quota defaults must be greater than or equal to 0")
        return value

    @field_validator("DEFAULT_CONVERSATION_MAX_DURATION")
    @classmethod
    def validate_default_max_duration(cls, value: int) -> int:
        if value not in (900, 1800):
            raise ValueError("DEFAULT_CONVERSATION_MAX_DURATION must be 900 or 1800")
        return value

    @field_validator("DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT")
    @classmethod
    def validate_default_inactivity_timeout(cls, value: int) -> int:
        if value not in (60, 180, 300):
            raise ValueError("DEFAULT_CONVERSATION_INACTIVITY_TIMEOUT must be 60, 180, or 300")
        return value

    @field_validator(
        "FREEMIUM_CHAT_DAILY_MESSAGES",
        "FREEMIUM_LESSONS_DAILY",
        "FREEMIUM_LISTENING_WEEKLY",
        "FREEMIUM_READING_WEEKLY",
        "FREEMIUM_VOICE_WEEKLY_MINUTES",
        "FREEMIUM_TRIAL_DAYS",
    )
    @classmethod
    def validate_freemium_quotas(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Freemium quota values must be >= 0")
        return value

    @field_validator("ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS")
    @classmethod
    def validate_trial_duration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS must be greater than 0")
        if value > 1800:
            raise ValueError("ASSESSMENT_VOICE_TRIAL_DURATION_SECONDS must not exceed 1800")
        return value

    model_config = {"env_file": ".env"}


settings = Settings()
