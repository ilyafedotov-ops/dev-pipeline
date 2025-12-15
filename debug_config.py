import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from devgodzilla.config import get_config, load_config
    
    print("Loading config...")
    config = load_config()
    print(f"Config path: {config.agent_config_path}")
    if config.agent_config_path:
        print(f"Exists: {config.agent_config_path.exists()}")
        print(f"Absolute: {config.agent_config_path.absolute()}")
    else:
        print("Config path is None")

    print(f"Pydantic imported successfully.")
    
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
