from pydantic import BaseModel


class MeResponse(BaseModel):
    id: str
    externalAuthId: str
    email: str
    fullName: str | None
    timezone: str
    currency: str
    createdAt: str
    updatedAt: str
