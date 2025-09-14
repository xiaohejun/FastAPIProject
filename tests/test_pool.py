import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from app.core.docker.image import ImageSpec


# @pytest.mark.asyncio
# async def test_first():
#     await asyncio.sleep(2)  # Takes 2 seconds
#
#
# @pytest.mark.asyncio
# async def test_second():
#     await asyncio.sleep(2)  # Takes 2 seconds
#

import aiodocker
from app.core.docker.pool import DockerContainerPool, AsyncDockerContainer
import  logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest_asyncio.fixture
async def python_docker_pool() -> AsyncGenerator[DockerContainerPool]:
    client = aiodocker.Docker()
    image_spec = ImageSpec(image="python:3.11-slim")
    async with DockerContainerPool(client=client, image_spec=image_spec) as p:
        p: DockerContainerPool
        yield p
        logger.info(f"label: {p.labels}")
        # containers = await p.list_containers()

        # logger.info(f"containers: {containers}")
        # for container in containers:
        #     logger.info(f"  - {container.name}")
    # 校验容器都删除了，防止资源泄漏
    # assert len(p.list_containers()) == 0
    await client.close()


@pytest.mark.asyncio
async def test_basic_usage():
    docker = aiodocker.Docker()
    logger.info('== Running a hello-world container ==')
    cmd = ["python3", "-c", "'import time;\nfor i in range(100):\n    time.sleep(1)\n    print(i)'"]
    container = await docker.containers.create_or_replace(
        config={
            'Cmd': cmd,
            'Image': 'python:3.11-slim',
        },
        name='testing',
    )
    await container.start()
    logs = await container.log(stdout=True)
    logger.info(''.join(logs))
    await container.delete(force=True)
    await docker.close()
