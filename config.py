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
 
settings = Settings()