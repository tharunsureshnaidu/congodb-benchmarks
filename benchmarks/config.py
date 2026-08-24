"""Platform connection config, read from environment (.env via python-dotenv)."""
import os
from dotenv import load_dotenv

load_dotenv()

# platform name -> (driver kind, env var prefix)
PLATFORMS = {
    "cognodb": ("bolt", "COGNODB"),
    "aura": ("bolt", "AURA"),
    "memgraph": ("bolt", "MEMGRAPH"),
    "falkordb": ("falkordb", "FALKORDB"),
    "arango": ("arango", "ARANGO"),
}


def bolt_config(prefix: str) -> dict:
    return {
        "uri": os.environ[f"{prefix}_URI"],
        "user": os.environ[f"{prefix}_USER"],
        "password": os.environ[f"{prefix}_PASSWORD"],
    }


def arango_config(prefix: str) -> dict:
    return {
        "uri": os.environ[f"{prefix}_URI"],
        "user": os.environ[f"{prefix}_USER"],
        "password": os.environ[f"{prefix}_PASSWORD"],
        "db": os.environ.get(f"{prefix}_DB", "benchmark"),
    }


def falkordb_config(prefix: str) -> dict:
    return {
        "host": os.environ[f"{prefix}_HOST"],
        "port": int(os.environ.get(f"{prefix}_PORT", 6379)),
        "username": os.environ.get(f"{prefix}_USER", ""),
        "password": os.environ.get(f"{prefix}_PASSWORD", ""),
        "graph": os.environ.get(f"{prefix}_GRAPH", "benchmark"),
        "ssl": os.environ.get(f"{prefix}_SSL", "false").lower() == "true",
    }


CONFIG_LOADERS = {"bolt": bolt_config, "arango": arango_config, "falkordb": falkordb_config}


def load_platform(name: str):
    if name not in PLATFORMS:
        raise ValueError(f"Unknown platform '{name}'. Choices: {list(PLATFORMS)}")
    kind, prefix = PLATFORMS[name]
    cfg = CONFIG_LOADERS[kind](prefix)
    return kind, cfg
