"""Containers module."""

from contextlib import asynccontextmanager

from dependency_injector import containers, providers
from app.core.db import Database
from app.core.file_storage.file_upload import FileChunkUploader, FileUploadSettings
from app.core.redis import init_redis_pool
from app.core.sse import SSEPubSub
from app.repositories import UserRepository
from app.services import FileUploadService, UserService


class DepsContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration()

    config = providers.Configuration(yaml_files=["config.yml"])

    db = providers.Resource(Database, url=config.db.url)

    redis = providers.Resource(init_redis_pool, url=config.redis.url)

    sse_pubsub = providers.ThreadSafeSingleton(SSEPubSub, redis=redis)

    file_uploader = providers.Factory(
        FileChunkUploader,
        settings=FileUploadSettings(),
        sse_pubsub=sse_pubsub,
        redis=redis,
    )


async def init_resources(deps: DepsContainer):
    await deps.init_resources()


async def shutdown_resources(deps: DepsContainer):
    await deps.shutdown_resources()


class ServiceFactory:
    def __init__(self, deps: DepsContainer):
        self.deps = deps

    @asynccontextmanager
    async def user(self):
        db: Database = await self.deps.db()
        async with db.scope_session() as session:
            yield UserService(UserRepository(session))

    async def file_uploader(self):
        return FileUploadService(await self.deps.file_uploader(bucket_name="test"))


#
# if __name__ == "__main__":
#     deps = DepsContainer()
#     deps1 = DepsContainer()
#     deps2 = DepsContainer()
#     print(f"{id(deps)}, {id(deps1)}, {id(deps2)}")
#
