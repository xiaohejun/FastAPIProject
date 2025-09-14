from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse, JSONServerSentEvent

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


# @file_router.get("/upload/get_tasks")
# async def query_upload_task(
#     task_ids: list[UUID],
#     srv: FileUploadService = Depends(get_file_upload_service),
# ) -> list[FileUploadTaskPublic]:
#     return await srv.query_task(task_ids)


@file_router.post("/upload/progress")
async def upload_task_progress(
    task_ids: list[UUID],
    srv: FileUploadService = Depends(get_file_upload_service),
):
    return await srv.progress(task_ids)


# @file_router.post("/upload/progress")
# async def auth_events(task_ids: list[UUID]):
#     # print(task_ids)

#     async def events():
#         yield JSONServerSentEvent(
#             data={
#                 "event": "login",
#                 "data": '{"user_id": "4135"}',
#             }
#         )

#     return EventSourceResponse(events())
