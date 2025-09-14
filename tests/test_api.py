import math
import os
import pytest
import pytest_asyncio
from pathlib import Path

from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from app.core.file_storage.schemas import (
    FileChunkUploadResponse,
    FileUploadTaskCreate,
    FileUploadTaskPublic,
    FileChunkUploadRequest,
)


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def app():
    from app.api.fastapi import app

    async with LifespanManager(app) as manager:
        print("We're in!")
        yield manager.app


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


@pytest.mark.asyncio
async def test_file_upload_task_create(client: AsyncClient):
    # 创建上传任务
    file_path = (Path(__file__).parent / "test.txt").absolute()
    s = os.stat(file_path)
    task_create = FileUploadTaskCreate(file_name=file_path.stem, file_size=s.st_size)
    response = await client.post(
        "/file/upload/create_task", json=task_create.model_dump()
    )
    assert response.status_code == 200
    task = FileUploadTaskPublic.model_validate(response.json())
    assert task.id is not None
    assert task.file_name == file_path.stem
    assert task.file_size == s.st_size
    assert task.chunk_size == 1 * 1024 * 1024
    assert task.total_chunks == math.ceil(s.st_size / task.chunk_size)
    assert task.uploaded_bytes == 0
    assert task.status == "started"
    assert task.start_time is not None
    assert task.end_time is None
    assert task.nxt_chunk_idx == 0

    # 上传文件
    with open(file_path, "rb") as f:
        chunk_size = task.chunk_size
        chunk_idx = 0
        while chunk_idx < task.total_chunks:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            data = {
                "id": str(task.id),
                "chunk_idx": chunk_idx,
            }
            response = await client.post(
                "/file/upload/chunk",
                data=data,
                files=[("chunk", ("test.txt", chunk))],
            )
            assert response.status_code == 200
            resp = FileChunkUploadResponse.model_validate(response.json())
            assert resp.id == task.id
            assert resp.chunk_idx == chunk_idx
            assert resp.success is True
            assert resp.nxt_chunk_idx == chunk_idx + 1
            chunk_idx = resp.nxt_chunk_idx
