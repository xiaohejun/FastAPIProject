"""Services module."""

from uuid import UUID
from app.core.file_storage.file_upload import FileChunkUploader, FileUploader
from app.core.file_storage.schemas import (
    FileChunkUploadRequest,
    FileChunkUploadResponse,
    FileUploadTaskCreate,
    FileUploadTaskPublic,
)
from .repositories import UserRepository
from .models import UserCreate, User


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def add(self, user: UserCreate) -> User:
        user = User.model_validate(user)
        return await self._repo.add(user)


class FileUploadService:
    def __init__(self, uploader: FileChunkUploader) -> None:
        self._uploader = uploader

    async def create_task(
        self, task_data: FileUploadTaskCreate
    ) -> FileUploadTaskPublic:
        return await self._uploader.create_task(task_data)

    async def upload_chunk(
        self, req: FileChunkUploadRequest
    ) -> FileChunkUploadResponse:
        return await self._uploader.upload_chunk(req)

    # async def query_task(self, task_ids: list[UUID]) -> list[FileUploadTaskPublic]:
    #     return await self._uploader.query_task(task_ids)

    async def progress(self, task_ids: list[UUID]) -> FileUploadTaskPublic:
        return await self._uploader.progress(task_ids)
