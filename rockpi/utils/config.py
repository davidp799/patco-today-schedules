"""
Configuration loader utility
"""

import json
from pathlib import Path

_config_cache = None

def load_config():
    """Load configuration from config.json file."""
    global _config_cache
    
    if _config_cache is None:
        config_path = Path(__file__).parent.parent / 'config.json'
        with open(config_path, 'r') as f:
            _config_cache = json.load(f)
    
    return _config_cache
