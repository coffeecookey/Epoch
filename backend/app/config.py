"""
Application configuration.

This module defines the application settings using Pydantic's BaseSettings
for environment variable support and type validation.
"""

from pathlib import Path

from pydantic import BaseModel, Field, validator
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env from backend directory (works regardless of cwd when running uvicorn)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


class Settings(BaseModel):
    """
    Application configuration settings.
    
    Can be configured via environment variables or .env file.
    Environment variable names should be uppercase (e.g., RECIPEDB_BASE_URL).
    
    Attributes:
        RECIPEDB_BASE_URL: Base URL for RecipeDB API
        FLAVORDB_BASE_URL: Base URL for FlavorDB API
        API_TIMEOUT: Request timeout in seconds
        MIN_HEALTHY_SCORE: Minimum health score for recommendations
        MAX_RECOMMENDATIONS: Maximum number of recipe recommendations
        MAX_SWAPS_PER_REQUEST: Maximum number of ingredient swaps
        USE_LLM_EXPLANATIONS: Enable LLM-generated explanations
        LLM_API_KEY: API key for LLM service (optional)
        ENABLE_CACHE: Enable response caching
        CACHE_TTL: Cache time-to-live in seconds
        LOG_LEVEL: Logging level (DEBUG/INFO/WARNING/ERROR)
    """
    
    # API Configuration
    RECIPEDB_BASE_URL: str = Field(
        default="https://cosylab.iiitd.edu.in/recipedb/search_recipedb",
        description="Base URL for RecipeDB API"
    )
    
    FLAVORDB_BASE_URL: str = Field(
        default="https://cosylab.iiitd.edu.in/flavordb",
        description="Base URL for FlavorDB API"
    )
    
    # Cosylab API Key (shared by RecipeDB and FlavorDB)
    COSYLAB_API_KEY: Optional[str] = Field(
        default_factory=lambda: os.getenv("COSYLAB_API_KEY"),
        description="API key for RecipeDB and FlavorDB (cosylab.iiitd.edu.in)"
    )

    # API Timeouts
    API_TIMEOUT: int = Field(
        default=10,
        ge=1,
        le=60,
        description="API request timeout in seconds"
    )
    
    # Health Score Configuration
    MIN_HEALTHY_SCORE: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Minimum health score threshold for recommendations"
    )
    
    # Recommendation Limits
    MAX_RECOMMENDATIONS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of recipe recommendations to return"
    )
    
    # Semantic re-ranking (Phase 1: transformer replacement)
    USE_SEMANTIC_RERANK: bool = Field(
        default=True,
        description="Use sentence-transformers to re-rank substitutes by semantic similarity"
    )

    SEMANTIC_WEIGHT: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Weight for semantic similarity in substitute ranking (flavor+health+semantic sum to 1.0)"
    )

    # Swap Configuration
    MAX_SWAPS_PER_REQUEST: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of ingredient swaps per request"
    )
    
    # LLM Configuration (Optional)
    USE_LLM_EXPLANATIONS: bool = Field(
        default=False,
        description="Enable LLM-generated explanations (uses templates if False)"
    )

    LLM_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for external LLM service (e.g., Anthropic Claude)"
    )

    # Gemini LLM Agent Configuration
    USE_LLM_AGENT: bool = Field(
        default_factory=lambda: os.getenv("USE_LLM_AGENT", "false").lower() == "true",
        description="Use Gemini LLM agent for swap discovery instead of rule-based system"
    )

    GEMINI_API_KEY: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY"),
        description="Google Gemini API key for agentic swap system"
    )

    LLM_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model to use for the swap agent"
    )

    LLM_MAX_ITERATIONS: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Maximum tool-call rounds for the LLM agent"
    )

    LLM_MAX_TOKENS: int = Field(
        default=4096,
        ge=256,
        le=16384,
        description="Maximum tokens per LLM response"
    )
    
    # Caching Configuration (Optional)
    ENABLE_CACHE: bool = Field(
        default=False,
        description="Enable response caching"
    )
    
    CACHE_TTL: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache time-to-live in seconds"
    )
    
    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR)"
    )
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of: {', '.join(valid_levels)}"
            )
        return v_upper
    
    @validator('RECIPEDB_BASE_URL', 'FLAVORDB_BASE_URL')
    def validate_url(cls, v):
        """Ensure URLs are properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip('/')  # Remove trailing slash
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()


# Configure logging based on settings
def configure_logging():
    """Configure application logging based on settings."""
    import logging
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {settings.LOG_LEVEL} level")
    logger.info(f"RecipeDB URL: {settings.RECIPEDB_BASE_URL}")
    logger.info(f"FlavorDB URL: {settings.FLAVORDB_BASE_URL}")
    logger.info(f"LLM Explanations: {'Enabled' if settings.USE_LLM_EXPLANATIONS else 'Disabled (using templates)'}")


# Initialize logging on import
configure_logging()