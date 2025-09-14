from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

try:
    import aiodocker
    from aiodocker.containers import DockerContainer as AioDockerContainer
except Exception as e:  # pragma: no cover
    raise RuntimeError("aiodocker is required. Please `pip install aiodocker`.") from e

logger = logging.getLogger(__name__)


class AsyncDockerContainer:
    """对 aiodocker 容器做一层薄包装，提供常用方法。"""

    def __init__(self, container: AioDockerContainer):
        self._c = container

    @property
    def id(self) -> str:
        return self._c._id

    @property
    def short_id(self) -> str:
        return self.id[:12]

    async def show(self) -> dict[str, Any]:
        return await self._c.show()

    async def status(self) -> str:
        info = await self._c.show()
        return info.get("State", {}).get("Status", "unknown")

    async def remove(self, force: bool = True) -> None:
        try:
            await self._c.delete(force=force)
        except aiodocker.exceptions.DockerError as e:
            logger.warning("Remove container %s failed: %s", self.short_id, e)

    async def exec_command(self, command: str | list[str]) -> tuple[int, str]:
        """
        执行命令, 返回退出码和输出
        """
        # env = None
        # if "python" in str(command):
        #     env = {"PYTHONUNBUFFERED": "1"}

        exec_obj = await self._c.exec(
            cmd=command,
            stdout=True,
            stderr=True,
            tty=False,
            # environment=env,
        )
        # logs = await self._c.log(stdout=True)
        # logger.info(f"logs: {''.join(logs)}")
        # detach=True：等待命令完成并返回输出
        result = exec_obj.start(detach=False)
        async with result as resp:
            logger.info("Exec command: %s, %s", command, resp)
        inspect = await exec_obj.inspect()
        logger.info(f"{inspect}")
        exit_code = inspect.get("ExitCode", -1)
        output = result.decode("utf-8", errors="replace") if isinstance(result, (bytes, bytearray)) else str(result)
        logger.info(f"{exit_code}, {output}")
        return exit_code, output



    async def exec_command_stream(
        self, command: str | list[str]
    ) -> AsyncGenerator[tuple[str | None, str | None], None]:
        """
        执行命令, 返回 stdout, stderr 的异步输出流
        """
        env = None
        if "python" in str(command):
            env = {"PYTHONUNBUFFERED": "1"}

        logger.info(f"Executing command: {command}")
        logger.info(f"state: {await self.status()}")

        exec_obj = await self._c.exec(
            cmd=command,
            stdout=True,
            stderr=True,
            tty=False,
            # stream=True,
            environment=env,
        )

        async with exec_obj.start(detach=False) as stream:
            msg = await stream.read_out()
            out_str, err_str = None, None
            data = getattr(msg, "data", None)
            extra = getattr(msg, "extra", None)
            if data is None:
                data = msg
            if isinstance(data, (bytes, bytearray)):
                text = data.decode("utf-8", errors="replace")
            else:
                text = str(data)
            if extra == 2:
                err_str = text
            else:
                out_str = text
            yield out_str, err_str

        inspect = await exec_obj.inspect()
        logger.info("Command %s finished with code %s", command, inspect.get("ExitCode"))
