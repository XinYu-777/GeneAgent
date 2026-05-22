"""uvicorn 入口：uvicorn api.main:app --reload"""

from api.app import app

__all__ = ["app"]
