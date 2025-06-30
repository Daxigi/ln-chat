import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    
    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER: str = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "digitalform")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "tu-secret-key-super-segura")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    # Vanna
    VANNA_MODEL: str = os.getenv("VANNA_MODEL", "gpt-3.5-turbo")
    VANNA_VECTOR_DB_PATH: str = os.getenv("VANNA_VECTOR_DB_PATH", "./chroma_db")
    
    # API
    API_VERSION: str = "1.0.0"
    API_TITLE: str = "API de Consultas Inteligentes"
    
settings = Settings()

