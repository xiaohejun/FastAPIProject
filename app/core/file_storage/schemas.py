from enum import Enum
from time import time
from pydantic import BaseModel, Field
from fastapi import UploadFile, File
from uuid import UUID, uuid4
from pathlib import Path


class FileUploadTaskBase(BaseModel):
    file_name: str
    file_size: int = Field(gt=0)


class FileUploadTaskCreate(FileUploadTaskBase): ...


class FileUploadTaskStatus(str, Enum):
    STARTED = "started"
    UPLOADING_ONE_CHUNK = "uploading_one_chunk"
    WAITING_NEXT_CHUNK = "waiting_next_chunk"
    FINISHED = "finished"
    FAILED = "failed"


class FileUploadTaskPublic(FileUploadTaskBase):
    id: UUID = Field(default_factory=uuid4)
    total_chunks: int = Field(default=1, gt=0)
    chunk_size: int = Field(default=1024 * 1024, gt=0)
    uploaded_bytes: int = Field(default=0, ge=0)
    status: FileUploadTaskStatus = Field(default=FileUploadTaskStatus.STARTED)
    start_time: float = Field(default_factory=time)
    end_time: float | None = Field(default=None)
    nxt_chunk_idx: int = Field(default=0, ge=0)


class FileUploadTaskPrivate(FileUploadTaskPublic):
    temp_dir: Path
    storge_dir: Path


class FileChunkUploadRequest(BaseModel):
    id: UUID
    chunk: UploadFile = File(...)
    chunk_idx: int = Field(default=0, ge=0)


class FileUploadProgress(FileUploadTaskPublic):
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    elapsed_time: float = Field(default=0.0, ge=0.0)
    speed: float = Field(default=0.0, ge=0.0)
    unit: str = Field(default="KB/s")


class FileChunkUploadRetCode(str, Enum):
    WAITING_NEXT_CHUNK = "waiting_next_chunk"
    CHUNK_UPLOADING = "chunk_uploading"
    CHUNK_IDX_WRONG = "chunk_idx_wrong"
    TASK_NOT_EXIST = "task_not_exist"
    TASK_ALREADY_FINISHED = "task_already_finished"
    TASK_FINISHED = "task_finished"
    INTERNAL_ERROR = "internal_error"


class FileChunkUploadResponse(BaseModel):
    id: UUID
    chunk_idx: int = Field(default=0, ge=0)
    nxt_chunk_idx: int = Field(default=0, ge=0)
    success: bool = Field(default=False)
    code: FileChunkUploadRetCode = Field(default=FileChunkUploadRetCode.INTERNAL_ERROR)
