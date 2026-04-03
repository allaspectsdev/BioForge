"""Authentication and authorization utilities.

Placeholder for future auth implementation. Currently allows all requests.
"""

from fastapi import Request


async def get_current_user(request: Request) -> dict:
    """Extract current user from request. Returns a default user for now."""
    return {"id": "default", "name": "Default User"}
