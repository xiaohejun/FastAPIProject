# """
# Docker容器池
# """
#
# from __future__ import annotations
#
# import logging
# import os
# import uuid
# from collections.abc import Generator
# from contextlib import AbstractContextManager, contextmanager
# from queue import Queue
# from typing import Any, NoReturn
#
# import docker
# from docker.models.containers import Container
#
# from app.thread_safe.dict import ThreadSafeDict
#
# from .container import DockerContainer
# from .image import ImageSpec
#
# logger = logging.getLogger(__name__)
# from __future__ import annotations
#
# from typing import Any
#
# from pydantic import BaseSettings, Field
#
#
# class ImageSpec(BaseSettings):
#     """
#     Docker镜像规格
#     """
#
#     image: str
#     # Keep the container alive between uses. Override if your image lacks /bin/sh.
#     keepalive_command: list[str] = Field(
#         default_factory=lambda: ["sleep", "infinity"]
#     )  # e.g., ["sleep", "infinity"] or ["tail", "-f", "/dev/null"]
#     env: dict[str, str] = Field(default_factory=dict)
#     extra_run_kwargs: dict[str, Any] = Field(
#         default_factory=dict
#     )  # any additional docker.containers.run kwargs
#
# class DockerContainerPool(AbstractContextManager):
#     """
#     管理docker container的容器池,支持单image,线程安全
#     """
#
#     def __init__(self, client: docker.DockerClient, image_spec: ImageSpec) -> None:
#         self._client = client
#         self._image_spec = image_spec
#         self._queue: Queue[DockerContainer] = Queue()
#
#     @property
#     def image_spec(self) -> ImageSpec:
#         return self._image_spec
#
#     @property
#     def name(self) -> str:
#         return f"sim-{self._image_spec.image}"
#
#     def _generate_container_name(self) -> str:
#         return f"sim-app-container-{uuid.uuid4().hex[:10]}"
#
#     @property
#     def labels(self) -> list[str]:
#         return [f"{self.name}"]
#
#     def __exit__(self, exc_type, exc_value, traceback):
#         """
#         关闭容器池,所有容器docker rm
#         """
#         self.close()
#
#     def close(self):
#         """
#         关闭容器池,所有容器docker rm
#         """
#         while not self._queue.empty():
#             container = self._queue.get()
#             logger.info(
#                 "Removing container %s from image %s", container.short_id, self._image_spec.image
#             )
#             container.remove(force=True)
#
#     def _create_container(self) -> DockerContainer:
#         run_kwargs: dict[str, Any] = {
#             "name": self._generate_container_name(),
#             "image": self._image_spec.image,
#             "detach": True,
#             "tty": True,
#             "stdin_open": True,
#             "auto_remove": False,
#             "environment": self._image_spec.env,
#             "user": os.getuid(),
#             "userns_mode": "host",
#             "labels": self.labels,
#             **(self._image_spec.extra_run_kwargs or {}),
#         }
#         # Give it a moment to transition to running
#         c: Container = self._client.containers.run(
#             command=self._image_spec.keepalive_command, **run_kwargs
#         )
#         # TODO: wait for container to be fully up (e.g., healthcheck)
#         c.reload()
#         logger.info(
#             "Created container %s from image %s, %s", c.short_id, self._image_spec.image, c.status
#         )
#         return DockerContainer(c)
#
#     def _acquire(self) -> DockerContainer:
#         """
#         获取一个容器,如果池为空,则创建一个新容器
#         """
#         if not self._queue.empty():
#             container = self._queue.get()
#             try:
#                 container.reload()
#                 if container.status != "running":
#                     logger.warning("Container %s not running, recreating.", container.short_id)
#                     container.remove(force=True)
#                     container = self._create_container()
#             except docker.errors.NotFound:
#                 logger.warning("Container %s not found, recreating.", container.short_id)
#                 container = self._create_container()
#         else:
#             container = self._create_container()
#         return container
#
#     def _release(self, container: DockerContainer) -> NoReturn:
#         """
#         归还一个容器到池中
#         """
#         self._queue.put(container)
#
#     @contextmanager
#     def get_container(self) -> Generator[DockerContainer]:
#         """
#         获取一个容器,如果池为空,则创建一个新容器,使用完毕后归还到池中
#         """
#         container = self._acquire()
#         try:
#             yield container
#         except Exception as e:
#             logger.exception(
#                 "Error during using container %s, exception: %s", container.short_id, e
#             )
#             raise
#         finally:
#             self._release(container)
#
#     def list_containers(self) -> list[Container]:
#         """
#         列出当前池中所有容器
#         """
#         containers = self._client.containers.list(all=True, filters={"label": self.labels})
#         return containers
#
#
# class DockerConatainerPoolMgr(AbstractContextManager):
#     """
#     Docker容器池管理器
#     """
#
#     def __init__(self):
#         self._client = docker.from_env()
#         self._pools: ThreadSafeDict[str, DockerContainerPool] = ThreadSafeDict()
#
#     def register_pool(self, image_spec: ImageSpec) -> DockerContainerPool:
#         """
#         注册一个容器池，如果已经存在则什么都不做
#         """
#         logger.info("Registering pool for image %s", image_spec.image)
#         default_pool = DockerContainerPool(self._client, image_spec)
#         _, pool = self._pools.put_if_absent(image_spec.image, default_pool)
#         return pool
#
#     def get_pool(self, image_spec: ImageSpec) -> DockerContainerPool:
#         """
#         获取一个容器池
#         """
#         pool = self._pools.get(image_spec.image)
#         if pool is None:
#             raise ValueError(f"Pool for image {image_spec.image} not found")
#         return pool
#
#     def __exit__(self, exc_type, exc_value, traceback):
#         """
#         关闭所有容器池
#         """
#         for pool in self._pools.values():
#             pool.close()