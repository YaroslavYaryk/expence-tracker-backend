from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal


CategoryType = Literal["expense", "income"]


class CategoryDto(BaseModel):
    id: str
    type: CategoryType
    name: str
    icon: str | None = None
    color: str | None = None
    isDefault: bool
    isArchived: bool
    position: int


class CategoriesResponse(BaseModel):
    items: list[CategoryDto]


class CategoryCreate(BaseModel):
    type: CategoryType
    name: str = Field(min_length=1, max_length=40)
    icon: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=32)
    position: int = Field(default=100, ge=0, le=10000)


class CategoryCreateResponse(BaseModel):
    id: str


class CategoryUpdate(BaseModel):
    # Приймає isArchived, але всередині коду використовується is_archived
    is_archived: bool | None = Field(None, validation_alias="isArchived")

    model_config = ConfigDict(
        # Це дозволяє звертатися до поля за обома іменами
        populate_by_name=True,
        # Налаштування, які ви вже використовуєте у config.py
        extra="ignore"
    )

    name: str | None = Field(default=None, min_length=1, max_length=40)
    icon: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=32)
    position: int | None = Field(default=None, ge=0, le=10000)
