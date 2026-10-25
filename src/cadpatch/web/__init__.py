"""
CAD Patch Editor Web module.
"""

from .app import create_app, app
from .config import WebConfig, load_web_config

__all__ = ["create_app", "app", "WebConfig", "load_web_config"]
