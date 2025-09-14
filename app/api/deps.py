from app.core.deps import DepsContainer, ServiceFactory
from fastapi import Depends, Request


async def deps_container(request: Request):
    yield request.app.deps


async def get_user_service(deps: DepsContainer = Depends(deps_container)):
    async with ServiceFactory(deps).user() as service:
        yield service


async def get_file_upload_service(deps: DepsContainer = Depends(deps_container)):
    return ServiceFactory(deps).file_uploader()
