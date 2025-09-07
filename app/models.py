from typing import Optional
from sqlmodel import SQLModel, Field
from uuid import uuid4, UUID

class UserBase(SQLModel):
    name: str = Field(index=True)
    email: str = Field(index=True)
    password: str

class UserCreate(UserBase): pass


class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
    )

