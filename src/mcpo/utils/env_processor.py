import os
import re
import json

def substitute_env_vars(json_obj):
    """Recursively substitute environment variables in a JSON object"""
    if isinstance(json_obj, dict):
        return {k: substitute_env_vars(v) for k, v in json_obj.items()}
    elif isinstance(json_obj, list):
        return [substitute_env_vars(item) for item in json_obj]
    elif isinstance(json_obj, str):
        # Replace ${VAR} with the environment variable value
        pattern = r'\${([A-Za-z0-9_]+)}'
        matches = re.findall(pattern, json_obj)
        result = json_obj
        for var_name in matches:
            if var_name in os.environ:
                placeholder = f'${{{var_name}}}'
                result = result.replace(placeholder, os.environ[var_name])
        return result
    else:
        return json_obj

def process_config_file(config_path):
    """Process a config file and substitute environment variables"""
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    processed_config = substitute_env_vars(config_data)
    
    return processed_config
