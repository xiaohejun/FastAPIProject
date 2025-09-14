import math
from pathlib import Path
from time import time
from uuid import UUID

import aiofiles.os
from app.core.file_storage.schemas import (
    FileChunkUploadResponse,
    FileChunkUploadRetCode,
    FileUploadProgress,
    FileUploadTaskStatus,
    FileChunkUploadRequest,
    FileUploadTaskCreate,
    FileUploadTaskPrivate,
    FileUploadTaskPublic,
)
from redis.asyncio import Redis
from pydantic_settings import BaseSettings
import aiofiles
from fastapi import UploadFile

from app.core.sse import SSEPubSub
import logging


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


class FileUploadSettings(BaseSettings):
    temp_dir: Path = Path("/tmp") / "file_upload" / "temp"
    storge_dir: Path = Path("/tmp") / "file_upload" / "storage"
    chunk_size: int = 1024 * 1024
    buffer_size: int = 64 * 1024


class FileUploader:
    def __init__(
        self,
        settings: FileUploadSettings,
        bucket_name: str,
        redis: Redis,
        sse_pubsub: SSEPubSub,
    ):
        self._bucket_name = bucket_name
        self._settings = settings
        self._redis = redis
        self._sse_pubsub = sse_pubsub
        self._settings.temp_dir.mkdir(parents=True, exist_ok=True)
        self._settings.storge_dir.mkdir(parents=True, exist_ok=True)

    def _progress_channel(self, task_id: UUID) -> str:
        return f"file_upload_progress:{task_id}"

    def _task_key(self, task_id: UUID) -> str:
        return f"file_upload_task:{task_id}"

    async def store_task(self, task: FileUploadTaskPrivate):
        """
        存储文件上传任务
        """
        await self._redis.set(
            self._task_key(task.id),
            task.model_dump_json(),
        )

    async def get_task(self, task_id: UUID) -> FileUploadTaskPrivate | None:
        """
        获取文件上传任务
        """
        task_json = await self._redis.get(self._task_key(task_id))
        if not task_json:
            return None
        return FileUploadTaskPrivate.model_validate_json(task_json)

    async def query_task(self, task_id: UUID) -> FileUploadTaskPublic | None:
        """
        查询文件上传任务
        """
        task = await self.get_task(task_id)
        if not task:
            return None
        return FileUploadTaskPublic.model_validate(task.model_dump())

    async def expire_task(self, task_id: UUID):
        """
        过期文件上传任务
        """
        await self._redis.expire(self._task_key(task_id), 5 * 60)

    async def notify_progress(self, task: FileUploadTaskPrivate):
        """
        通知文件上传进度
        """
        file_size = task.file_size
        uploaded_bytes = task.uploaded_bytes

        p = FileUploadProgress(
            **task.model_dump(),
        )
        p.progress = min(100.0, round((uploaded_bytes / file_size) * 100, 2))
        p.elapsed_time = round(time() - task.start_time, 2)
        p.speed = (
            0
            if p.elapsed_time == 0
            else min(100.0, round((uploaded_bytes / p.elapsed_time) / 1024, 2))
        )
        p.unit = "KB/s"
        await self._sse_pubsub.publish(
            self._progress_channel(task.id),
            p.model_dump_json(),
        )

    async def progress(self, task_id: UUID):
        """
        获取文件上传进度
        """
        return await self._sse_pubsub.subscribe(self._progress_channel(task_id))

    async def create_task(
        self, task_data: FileUploadTaskCreate
    ) -> FileUploadTaskPublic:
        """
        创建文件上传任务
        """
        task_public = FileUploadTaskPublic(**task_data.model_dump())
        task_public.chunk_size = self._settings.chunk_size
        task_public.total_chunks = math.ceil(
            task_public.file_size / task_public.chunk_size
        )
        task = FileUploadTaskPrivate(
            **task_public.model_dump(),
            temp_dir=self._settings.temp_dir / self._bucket_name,
            storge_dir=self._settings.storge_dir / self._bucket_name,
        )
        task.temp_dir.mkdir(parents=True, exist_ok=True)
        task.storge_dir.mkdir(parents=True, exist_ok=True)
        await self.store_task(task)
        await self.notify_progress(task)
        return task_public


class FileChunkUploader(FileUploader):
    async def _write_chunk(
        self,
        task: FileUploadTaskPrivate,
        chunk_idx: int,
        chunk: UploadFile,
    ):
        """
        写入文件分片
        """
        pos = chunk_idx * task.chunk_size
        async with aiofiles.open(
            task.temp_dir / f"{task.file_name}",
            "wb",
        ) as f:
            await f.seek(pos)
            while True:
                buffer = await chunk.read(self._settings.buffer_size)
                if not buffer:
                    break
                await f.write(buffer)
                task.uploaded_bytes += len(buffer)
                await self.notify_progress(task)

    async def _storage_file(self, task: FileUploadTaskPrivate):
        """
        移动文件分片到存储目录
        """
        await aiofiles.os.rename(
            task.temp_dir / f"{task.file_name}",
            task.storge_dir / f"{task.file_name}",
        )

    async def upload_chunk(
        self, req: FileChunkUploadRequest
    ) -> FileChunkUploadResponse:
        """
        上传文件分片
        """
        # TODO: 如果有必要的话加锁，一次只能处理一个分片
        rsp = FileChunkUploadResponse.model_validate(req.model_dump())
        task = await self.get_task(req.id)
        if not task:
            # 任务不存在，应该重新创建任务
            rsp.success = False
            rsp.code = FileChunkUploadRetCode.TASK_NOT_EXIST
            return rsp

        # 默认设置rsp里面需要的nxt_chunk_idx
        nxt_chunk_idx = task.nxt_chunk_idx
        rsp.nxt_chunk_idx = nxt_chunk_idx
        if req.chunk_idx != nxt_chunk_idx:
            # 分片索引错误, 应该根据rsp里面返回的nxt_chunk_idx来进行上传
            rsp.success = False
            rsp.code = FileChunkUploadRetCode.CHUNK_IDX_WRONG
            return rsp

        if task.status == FileUploadTaskStatus.FINISHED:
            # 任务已经完成，不能再上传分片
            rsp.success = False
            rsp.code = FileChunkUploadRetCode.TASK_ALREADY_FINISHED
            return rsp

        if task.status == FileUploadTaskStatus.UPLOADING_ONE_CHUNK:
            # 正在上传中，需要等待上传完成再上传下一个分片
            rsp.success = False
            rsp.code = FileChunkUploadRetCode.CHUNK_UPLOADING
            return rsp

        chunk_idx = req.chunk_idx
        try:
            # 设置任务状态为上传中
            task.status = FileUploadTaskStatus.UPLOADING_ONE_CHUNK
            await self.store_task(task)

            # 写入文件分片
            await self._write_chunk(task, chunk_idx, req.chunk)
            nxt_chunk_idx = chunk_idx + 1
            rsp.nxt_chunk_idx = nxt_chunk_idx
            task.nxt_chunk_idx = nxt_chunk_idx
            if nxt_chunk_idx == task.total_chunks:
                # 上传完成
                rsp.success = True
                rsp.code = FileChunkUploadRetCode.ALL_CHUNKS_UPLOADED

                # 移动文件分片到存储目录
                await self._storage_file(task)
                task.end_time = time()
                task.status = FileUploadTaskStatus.FINISHED
                await self.store_task(task)
                await self.expire_task(task.id)
                await self.notify_progress(task)
            else:
                # 当前分片上传成功，等待上传下个分片
                rsp.success = True
                rsp.code = FileChunkUploadRetCode.WAITING_NEXT_CHUNK
                task.nxt_chunk_idx = nxt_chunk_idx
                task.status = FileUploadTaskStatus.WAITING_NEXT_CHUNK
                await self.store_task(task)
                await self.notify_progress(task)

        except Exception as e:
            # 记录错误信息，发生错误的时候不修改任务状态，需要重新上传
            logger.error(f"上传文件分片{chunk_idx}失败: {e}")
            rsp.success = False
            rsp.code = FileChunkUploadRetCode.INTERNAL_ERROR
            return rsp

        return rsp
