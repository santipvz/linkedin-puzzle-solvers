"""ASGI entry point. Dependencies are wired in bootstrap, not in the HTTP adapter."""

from .bootstrap import create_app


app = create_app()
