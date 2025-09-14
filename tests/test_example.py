# from typing import AsyncGenerator
#
# async def exec_command_stream(
#     self, command: str | list[str]
# ) -> AsyncGenerator[tuple[str | None, str | None], None]:
#     """
#     执行命令, 异步流式返回 (stdout, stderr)
#     - Exec.start(detach=False) 返回 Stream；当 tty=False 时，消息的 `extra`=1/2
#       分别表示 stdout/stderr。:contentReference[oaicite:1]{index=1}
#     """
#     env = None
#     if "python" in str(command):
#         env = {"PYTHONUNBUFFERED": "1"}
#
#     exec_obj = await self._c.exec(
#         cmd=command,
#         stdout=True,
#         stderr=True,
#         tty=False,            # 重要：False 才能区分两个通道
#         environment=env,
#     )
#     stream = await exec_obj.start(detach=False)
#
#     # aiodocker 的 Stream 迭代通常产出 aiohttp.WSMessage:
#     #   msg.data 是 bytes，msg.extra == 1/2 表示 stdout/stderr
#     async for msg in stream:
#         data = getattr(msg, "data", None)
#         extra = getattr(msg, "extra", None)
#         if data is None:
#             data = msg  # 兼容极端情况
#         text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
#
#         if extra == 2:
#             yield None, text   # stderr
#         else:
#             yield text, None   # stdout（包括 TTY 情况）
