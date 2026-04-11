# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    core_api_key = os.getenv("CORE_API_KEY")
    semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

settings = Settings()