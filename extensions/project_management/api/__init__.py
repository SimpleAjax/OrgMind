"""
OrgMind AI Project Management - REST API

PM-specific API endpoints that compose OrgMind's generic APIs.

All endpoints are prefixed with `/pm/` and require authentication.
"""

from .router import router

__all__ = ['router']
