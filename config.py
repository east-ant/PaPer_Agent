import os
from dotenv import load_dotenv
 
load_dotenv()
 
class Settings:
    core_api_key = os.getenv("CORE_API_KEY")
    semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    jwt_secret = os.getenv("JWT_SECRET", "change-this-in-production")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Phase 2: Discord OAuth 설정
    discord_client_id = os.getenv("DISCORD_CLIENT_ID")
    discord_client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    discord_oauth_redirect_uri = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "http://localhost:8000/api/discord/oauth/callback")
    discord_bot_token = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    
    # Phase 4: 스케줄러 설정
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
 
settings = Settings()