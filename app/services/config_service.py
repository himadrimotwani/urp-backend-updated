"""
Configuration service for loading and managing negotiation configuration.
"""

from pathlib import Path
import json

from app.schemas import NegotiationConfigData

DEFAULT_NEGOTIATION_CONFIG_PATH = Path("config/negotiation_config.json")
DEFAULT_NEGOTIATION_CONFIG: NegotiationConfigData | None = None


def load_negotiation_config() -> NegotiationConfigData:
    """
    Loads negotiation configuration from JSON file or returns cached/default values.
    
    Inputs:
        None (reads from global config file path).
    
    What happens:
        Checks if config is already loaded in memory (returns cached version if so).
        If not cached, tries to read from negotiation_config.json file.
        Parses JSON and creates NegotiationConfigData object.
        Caches the loaded config in global variable.
        If file doesn't exist or has errors, returns default values.
    
    Output:
        Returns a NegotiationConfigData object containing:
        - Available contract types
        - Length ranges (min/max)
        - Cap value ranges (min/max)
        - Revenue share ranges (min/max)
        - Allowed cap types
        - System prompt template
        - Example dialog
    
    Context:
        Called whenever negotiation configuration is needed.
        Used by negotiation endpoints to validate proposals.
        Used by config endpoints to return current settings.
    """
    global DEFAULT_NEGOTIATION_CONFIG
    
    if DEFAULT_NEGOTIATION_CONFIG is not None:
        return DEFAULT_NEGOTIATION_CONFIG
    
    if DEFAULT_NEGOTIATION_CONFIG_PATH.exists():
        try:
            with DEFAULT_NEGOTIATION_CONFIG_PATH.open() as f:
                data = json.load(f)
                DEFAULT_NEGOTIATION_CONFIG = NegotiationConfigData(**data)
                return DEFAULT_NEGOTIATION_CONFIG
        except Exception as e:
            print(f"Error loading negotiation config: {e}")
    
    # Return default config
    default_config = NegotiationConfigData(
        contract_types_available=["buyback", "revenue_sharing", "hybrid"],
        length_min=1,
        length_max=10,
        cap_type_allowed="fraction",
        cap_value_min=0.0,
        cap_value_max=0.5,
        revenue_share_min=0.0,
        revenue_share_max=1.0,
        system_prompt_template="",
        example_dialog=[],
    )
    DEFAULT_NEGOTIATION_CONFIG = default_config
    return default_config


def reload_negotiation_config():
    """
    Forces reload of negotiation configuration from disk.
    
    Inputs:
        None.
    
    What happens:
        Clears the cached negotiation config from memory.
        Forces the next load_negotiation_config() call to read from file again.
    
    Output:
        None (modifies global state).
    
    Context:
        Called after updating negotiation config to ensure changes are reflected.
        Used when instructor updates config and wants to see changes immediately.
    """
    global DEFAULT_NEGOTIATION_CONFIG
    DEFAULT_NEGOTIATION_CONFIG = None
    load_negotiation_config()