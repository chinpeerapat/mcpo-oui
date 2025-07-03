# api/index.py  –  env-aware version
import json, os, re
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))
from mcpo.utils.auth import get_verify_api_key, APIKeyMiddleware
from mcpo.main import lifespan, create_dynamic_endpoints

# ──────────────────────────────────────────────────────────────
# 1. Load configuration: env > path > default file
# ──────────────────────────────────────────────────────────────
CFG_ENV_VAR   = "MCPO_CONFIG_JSON"
CFG_PATH_ENV  = "MCPO_CONFIG_PATH"
DEFAULT_FILE  = Path(__file__).resolve().parent.parent / "config.json"

if os.getenv(CFG_ENV_VAR):                                      # raw JSON wins
    cfg_raw = json.loads(os.getenv(CFG_ENV_VAR))
elif os.getenv(CFG_PATH_ENV):                                   # custom path
    cfg_path = Path(os.getenv(CFG_PATH_ENV)).expanduser()
    with cfg_path.open() as f:
        cfg_raw = json.load(f)
else:                                                           # default file
    with DEFAULT_FILE.open() as f:
        cfg_raw = json.load(f)

# ──────────────────────────────────────────────────────────────
# 2. Replace ${VAR} placeholders
# ──────────────────────────────────────────────────────────────
_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
def resolve(obj):
    if isinstance(obj, dict):
        return {k: resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(i) for i in obj]
    if isinstance(obj, str):
        return _ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), obj)
    return obj
cfg = resolve(cfg_raw)

# ──────────────────────────────────────────────────────────────
# 3. Build FastAPI root (rest of wrapper unchanged from earlier)
# ──────────────────────────────────────────────────────────────
cors_allow = cfg.get("corsAllowOrigins", ["*"])

app_root = FastAPI(
    title=cfg.get("name", "MCP OpenAPI Proxy"),
    description=cfg.get("description", "Auto-generated API from MCP tool schemas"),
    version=cfg.get("version", "1.0"),
    lifespan=lifespan,
)
app_root.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key       = os.getenv("MCP_API_KEY", cfg.get("apiKey", ""))
strict_auth   = cfg.get("strictAuth", False)
api_dep       = get_verify_api_key(api_key) if api_key else None
if api_key and strict_auth:
    app_root.add_middleware(APIKeyMiddleware, api_key=api_key)

# …(same configure_subapp / multi-vs-single logic as before)…

app = app_root   # Vercel looks for “app”