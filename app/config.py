from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "NexusAI"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql://user:password@localhost:5432/nexusai"

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    deepgram_api_key: str

    groq_api_key: str

    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"

    base_url: str = "https://your-ngrok-or-domain.com"

    model_config = {"env_file": ".env"}


settings = Settings()