from __future__ import annotations

from contextlib import AbstractAsyncContextManager

import contextlib

from app.core.docker.container import AsyncDockerContainer
from app.core.docker.image import ImageSpec

"""
异步、线程安全（协程安全）的 Docker 容器池实现
- 基于 aiodocker（纯异步 Docker SDK）
- 使用 asyncio.Queue 作为容器租赁/归还的共享结构
- 通过 asyncio.Lock 保护池大小的并发修改
- 通过 labels 关联/清理同一池的容器
- 提供池管理器，支持多 image、多池

依赖：
    pip install aiodocker pydantic

注意：
- aiodocker 与 docker-py API 不同；此实现不依赖 docker-py。
- 若镜像不含 /bin/sh，请按需自定义 keepalive_command。
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Optional, AsyncGenerator

from pydantic import BaseModel, Field

try:  # 局部导入，避免未安装时报错
    import aiodocker
    from aiodocker.containers import DockerContainer as AioDockerContainer
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "aiodocker is required. Please `pip install aiodocker`."
    ) from e


logger = logging.getLogger(__name__)



class DockerContainerPool(AbstractAsyncContextManager):
    """
    管理单 image 的容器池（协程安全）。

    特性：
    - 可配置 max_size / min_idle
    - get_container() 返回异步上下文管理器；退出时自动归还
    - 容器非运行状态会被丢弃并重建
    - close() 会清理由该池创建的容器（通过 label 识别）
    """
    def __init__(
        self,
        client: aiodocker.Docker,
        image_spec: ImageSpec,
    ) -> None:
        self._client = client
        self._spec = image_spec
        self._name = f"sim-{image_spec.image}"
        self._labels = {"container-pool": self._name}
        self._queue: asyncio.Queue[AsyncDockerContainer] = asyncio.Queue()
        self._user_uid = os.getuid()

    # ------------------------------- 公共属性 -------------------------------
    @property
    def image_spec(self) -> ImageSpec:
        return self._spec

    @property
    def name(self) -> str:
        return self._name

    @property
    def labels(self) -> dict[str, str]:
        return self._labels


    async def __aexit__(self, exc_type, exc_value, traceback, /):
        await self.close()

    # ------------------------------- 生命周期 ------------------------------

    async def close(self) -> None:
        while not self._queue.empty():
            c = await self._queue.get()
            await c.remove(force=True)
            await asyncio.sleep(0)  # 让出调度

        # 2) 通过 label 扫描并删除残留容器（包括租出中的、被崩溃中断的）
        await self._remove_all_labeled()

    # ------------------------------- 获取/归还 ------------------------------
    @asynccontextmanager
    async def get_container(self) -> AsyncGenerator[AsyncDockerContainer, Any]:
        """获取一个可用容器；退出上下文时自动归还。"""
        c = await self._acquire()
        try:
            yield c
        except Exception:
            # 发生异常时，不归还，直接销毁，避免污染
            logger.exception("Error while using container %s; removing it.", c.short_id)
            # await self._destroy(c)
            raise
        finally:
            await self._release(c)

    async def _acquire(self) -> AsyncDockerContainer:
        try:
            c = self._queue.get_nowait()
            if await self._is_running(c):
                return c
            # 不可用：销毁并继续
            await self._destroy(c)
        except asyncio.QueueEmpty:
            pass

        # 重新创建一个
        return await self._create_container()


    async def _release(self, c: AsyncDockerContainer) -> None:
        if not await self._is_running(c):
            await self._destroy(c)
            return
        await self._queue.put(c)

    # ------------------------------- 创建/销毁 ------------------------------
    async def _create_container(self) -> AsyncDockerContainer:
        name = f"sim-app-container-{uuid.uuid4().hex[:10]}"
        host_config: dict[str, Any] = {}

        # 用户映射（在 Linux 上常见；Windows/Mac 可忽略）
        if self._user_uid is not None:
            host_config.setdefault("UsernsMode", "host")

        create_kwargs: dict[str, Any] = {
            "name": name,
            "Image": self._spec.image,
            "Cmd": self._spec.keepalive_command,
            # "Tty": True,
            # "OpenStdin": True,
            "Labels": self._labels | self._spec.extra_run_kwargs.pop("labels", {}),
            "Env": [f"{k}={v}" for k, v in (self._spec.env or {}).items()],
            "HostConfig": host_config | self._spec.extra_run_kwargs.pop("HostConfig", {}),
        }

        # aiodocker: containers.create + start
        container = await self._client.containers.create(config=create_kwargs)
        await container.start()

        wrapped = AsyncDockerContainer(container)
        # 等待 running 状态（最多 10s）
        await self._wait_running(wrapped, timeout=10.0)
        logger.info("Created container %s from image %s", wrapped.short_id, self._spec.image)
        return wrapped

    @staticmethod
    async def _destroy(c: AsyncDockerContainer) -> None:
        # 先尝试删除
        await c.remove(force=True)

    # ------------------------------- 状态/工具 ------------------------------
    @staticmethod
    async def _is_running(c: AsyncDockerContainer) -> bool:
        try:
            return (await c.status()) == "running"
        except aiodocker.exceptions.DockerError:
            return False

    async def _wait_running(self, c: AsyncDockerContainer, timeout: float = 10.0) -> None:
        async def _poll():
            while True:
                if await self._is_running(c):
                    return
                await asyncio.sleep(0.2)

        try:
            await asyncio.wait_for(_poll(), timeout=timeout)
        except asyncio.TimeoutError:
            # 未就绪，直接抛错，让上层走销毁逻辑
            raise TimeoutError(f"Container {c.short_id} did not reach running state in time")

    async def _remove_all_labeled(self) -> None:
        # aiodocker 没有像 docker-py 那样的 filters 高阶封装，使用低层 list + 过滤
        all_containers = await self._client.containers.list(all=True)
        for ref in all_containers:
            try:
                info = await ref.show()
                labels = info.get("Config", {}).get("Labels", {}) or {}
                if labels.get("container-pool") == self._name:
                    c = AsyncDockerContainer(ref)
                    await c.remove(force=True)
            except aiodocker.exceptions.DockerError as e:
                logger.warning("Cleanup labeled container failed: %s", e)

    # ------------------------------- 查询接口 -------------------------------
    async def list_containers(self) -> list[dict[str, Any]]:
        """列出与本池关联（通过 label）的容器信息。"""
        result: list[dict[str, Any]] = []
        for ref in await self._client.containers.list(all=True):
            try:
                info = await ref.show()
                labels = info.get("Config", {}).get("Labels", {}) or {}
                if labels.get("container-pool") == self._name:
                    result.append(info)
            except aiodocker.exceptions.DockerError:
                continue
        return result


# class AsyncDockerContainerPoolMgr:
#     """多 image 的容器池管理器（协程安全）。"""
#
#     def __init__(self) -> None:
#         self._client = aiodocker.Docker()
#         self._pools: dict[str, AsyncDockerContainerPool] = {}
#         self._lock = asyncio.Lock()
#
#     async def register_pool(
#         self,
#         image_spec: ImageSpec,
#         *,
#         max_size: int = 4,
#         min_idle: int = 0,
#         acquire_timeout: float | None = 60.0,
#     ) -> AsyncDockerContainerPool:
#         """注册或返回已存在池。"""
#         async with self._lock:
#             pool = self._pools.get(image_spec.image)
#             if pool is None:
#                 pool = AsyncDockerContainerPool(
#                     self._client,
#                     image_spec,
#                     max_size=max_size,
#                     min_idle=min_idle,
#                     acquire_timeout=acquire_timeout,
#                 )
#                 self._pools[image_spec.image] = pool
#                 await pool.start()
#             return pool
#
#     async def get_pool(self, image: str) -> AsyncDockerContainerPool:
#         async with self._lock:
#             pool = self._pools.get(image)
#             if pool is None:
#                 raise KeyError(f"Pool for image {image} not found")
#             return pool
#
#     async def close(self) -> None:
#         async with self._lock:
#             pools = list(self._pools.values())
#             self._pools.clear()
#         for p in pools:
#             await p.close()
#         await self._client.close()
#
#
# # ------------------------------- 使用示例 -------------------------------
# async def main():
#     mgr = AsyncDockerContainerPoolMgr()
#     pool = await mgr.register_pool(ImageSpec(image="python:3.11-slim"), max_size=2, min_idle=1)
#     async with pool.get_container() as c:
#         info = await c.show()
#         print("use", c.short_id, info.get("State", {}).get("Status"))
#     await mgr.close()
#
# if __name__ == "__main__":
#     asyncio.run(main())
