from typing import Optional
from sqlmodel import SQLModel, Field
from uuid import uuid4, UUID

class UserBase(SQLModel):
    name: str = Field(index=True)
    email: str = Field(index=True)
    password: str

class UserCreate(UserBase): pass


class FileUploadBase(SQLModel):
    filename: str = Field(index=True)
    file_size: float = Field(index=True)

class FileUploadCreate(FileUploadBase):
    ...


class FileUpload(FileUploadBase):
    __tablename__ = "files"

    file_path: Optional[str] = Field(default=None, index=True)
    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
    )

class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
    )

