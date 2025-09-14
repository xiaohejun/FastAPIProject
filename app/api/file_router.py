from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_file_upload_service
from app.core.file_storage.schemas import (
    FileChunkUploadResponse,
    FileUploadTaskCreate,
    FileUploadTaskPublic,
    FileChunkUploadRequest,
)
from app.services import FileUploadService


file_router = APIRouter(prefix="/file", tags=["file"])


@file_router.post("/upload/create_task")
async def create_upload_task(
    task_data: FileUploadTaskCreate,
    srv: FileUploadService = Depends(get_file_upload_service),
) -> FileUploadTaskPublic:
    return await srv.create_task(task_data)


@file_router.post("/upload/chunk")
async def upload_chunk(
    req: Annotated[FileChunkUploadRequest, Form()],
    srv: FileUploadService = Depends(get_file_upload_service),
) -> FileChunkUploadResponse:
    return await srv.upload_chunk(req)
