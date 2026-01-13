from pydantic import BaseModel, Field
from typing import Optional, List


class OkResponse(BaseModel):
    ok: bool = True


class CursorPage(BaseModel):
    nextCursor: str | None = None


class ItemsResponse(BaseModel):
    items: list
