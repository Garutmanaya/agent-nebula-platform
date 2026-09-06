"""Opt-in FastAPI route and lifespan integration for agents."""

from .app import FastApiRuntimeAdapter
from .lifespan import runtime_lifespan
from .server import UvicornRuntimeServer, UvicornServerSettings

__all__ = [
    "FastApiRuntimeAdapter",
    "UvicornRuntimeServer",
    "UvicornServerSettings",
    "runtime_lifespan",
]
