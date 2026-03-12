"""
Configuration management for AnyPlot server

Loads configuration from anyplot.config.json with environment variable overrides.
"""

import os
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass
class PrivacyConfig:
    """Privacy and differential privacy settings"""
    default_epsilon: float = 1.0
    max_budget_per_session: float = 10.0
    clip_percentiles: list[int] = field(default_factory=lambda: [1, 99])
    min_samples_for_stats: int = 10


@dataclass
class SandboxConfig:
    """Sandbox execution settings"""
    timeout_seconds: int = 30
    memory_limit_mb: int = 512
    allowed_imports: list[str] = field(default_factory=lambda: [
        "matplotlib", "matplotlib.pyplot", "pandas", "numpy",
        "seaborn", "plotly", "altair", "scipy"
    ])
    blocked_imports: list[str] = field(default_factory=lambda: [
        "os", "subprocess", "socket", "sys", "__import__",
        "eval", "exec", "compile"
    ])
    temp_dir: str = "/tmp/anyplot-sandbox"


@dataclass
class ModelConfig:
    """LLM model configuration"""
    provider: str = "anthropic"
    model_name: str = "claude-sonnet-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None


@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = "localhost"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173", "http://localhost:3000"
    ])
    max_request_size_mb: int = 50
    session_timeout_minutes: int = 60


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "json"
    output: str = "stdout"
    privacy_audit_log: Optional[str] = "./logs/privacy_audit.log"
    performance_log: Optional[str] = "./logs/performance.log"


@dataclass
class DevelopmentConfig:
    """Development mode settings"""
    mock_mode: bool = False
    hot_reload: bool = True
    verbose_errors: bool = True
    save_generated_code: bool = False
    code_output_dir: str = "./generated_code"


@dataclass
class Config:
    """Main configuration object"""
    version: str = "1.0"
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    development: DevelopmentConfig = field(default_factory=DevelopmentConfig)


class ConfigLoader:
    """Load and manage application configuration"""
    
    DEFAULT_CONFIG_PATHS = [
        "anyplot.config.json",
        "config/anyplot.config.json",
        "../anyplot.config.json",
        "../../anyplot.config.json",
    ]
    
    @staticmethod
    def find_config_file() -> Optional[Path]:
        """Find configuration file in common locations"""
        # Check environment variable first
        env_path = os.getenv("ANYPLOT_CONFIG")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path
        
        # Check default locations
        for config_path in ConfigLoader.DEFAULT_CONFIG_PATHS:
            path = Path(config_path)
            if path.exists():
                return path
        
        return None
    
    @staticmethod
    def load_json_config(path: Path) -> dict[str, Any]:
        """Load configuration from JSON file"""
        with open(path) as f:
            return json.load(f)
    
    @staticmethod
    def apply_env_overrides(config_dict: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides"""
        # Environment variable format: ANYPLOT_SECTION_KEY
        # Example: ANYPLOT_PRIVACY_DEFAULT_EPSILON=0.5
        
        for key, value in os.environ.items():
            if key.startswith("ANYPLOT_"):
                parts = key[8:].lower().split("_", 1)  # Remove ANYPLOT_ prefix
                if len(parts) == 2:
                    section, config_key = parts
                    if section in config_dict:
                        # Try to parse as JSON first, then as string
                        try:
                            parsed_value = json.loads(value)
                        except json.JSONDecodeError:
                            parsed_value = value
                        
                        config_dict[section][config_key] = parsed_value
        
        return config_dict
    
    @staticmethod
    def dict_to_config(config_dict: dict[str, Any]) -> Config:
        """Convert dictionary to Config object"""
        return Config(
            version=config_dict.get("version", "1.0"),
            privacy=PrivacyConfig(**config_dict.get("privacy", {})),
            sandbox=SandboxConfig(**config_dict.get("sandbox", {})),
            model=ModelConfig(**config_dict.get("model", {})),
            server=ServerConfig(**config_dict.get("server", {})),
            logging=LoggingConfig(**config_dict.get("logging", {})),
            development=DevelopmentConfig(**config_dict.get("development", {})),
        )
    
    @classmethod
    def load(cls) -> Config:
        """Load configuration with all overrides applied"""
        config_file = cls.find_config_file()
        
        if config_file:
            print(f"Loading configuration from: {config_file}")
            config_dict = cls.load_json_config(config_file)
        else:
            print("No configuration file found, using defaults")
            config_dict = {}
        
        # Apply environment variable overrides
        config_dict = cls.apply_env_overrides(config_dict)
        
        # Convert to Config object
        return cls.dict_to_config(config_dict)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Get the application configuration (cached)
    
    This function is cached so configuration is only loaded once.
    To reload configuration, clear the cache: get_config.cache_clear()
    """
    return ConfigLoader.load()


# Convenience functions for accessing specific configs
def get_privacy_config() -> PrivacyConfig:
    """Get privacy configuration"""
    return get_config().privacy


def get_sandbox_config() -> SandboxConfig:
    """Get sandbox configuration"""
    return get_config().sandbox


def get_model_config() -> ModelConfig:
    """Get model configuration"""
    return get_config().model


def get_server_config() -> ServerConfig:
    """Get server configuration"""
    return get_config().server


def get_logging_config() -> LoggingConfig:
    """Get logging configuration"""
    return get_config().logging


def get_development_config() -> DevelopmentConfig:
    """Get development configuration"""
    return get_config().development


# Example usage
if __name__ == "__main__":
    config = get_config()
    print(f"Configuration version: {config.version}")
    print(f"Privacy epsilon: {config.privacy.default_epsilon}")
    print(f"Sandbox timeout: {config.sandbox.timeout_seconds}s")
    print(f"Model: {config.model.provider}/{config.model.model_name}")
