# import asyncio
# import aiodocker
#
# async def main():
#     docker = aiodocker.Docker()
#     # await docker.images.pull("python:3.11-slim")
#
#     # 1) 创建一个常驻容器：["sleep", "infinity"]
#     container = await docker.containers.create_or_replace(
#         name="py-sandbox",
#         config={
#             "Image": "python:3.11-slim",
#             "Cmd": ["sleep", "infinity"],
#             "Tty": False,            # 不开 TTY，普通非交互命令更好区分 stdout/stderr
#             "AttachStdout": True,
#             "AttachStderr": True,
#         },
#     )
#     await container.start()
#     print("容器已启动")
#
#     # ========== 场景 A：多次执行非交互 python 命令，拿到输出 ==========
#     async def run_once_py(code: str) -> str:
#         exec_obj = await container.exec(
#             cmd=["python3", "-u", "-c", code],
#             stdin=False, stdout=True, stderr=True, tty=False,
#         )
#         # 注意：此处不 await
#         stream = exec_obj.start(detach=True)   # 返回 aiodocker.stream.DockerStream
#
#         buf = []
#         async for chunk in stream:
#             # chunk 可能是 bytes 或 dict，做个兼容
#             if isinstance(chunk, (bytes, bytearray)):
#                 buf.append(chunk.decode(errors="ignore"))
#             else:
#                 buf.append(str(chunk))
#         # 有的版本还支持 stream.read() / stream.read_out()，也可用
#         await stream.close()
#
#         info = await exec_obj.inspect()
#         return f"[exit={info.get('ExitCode')}]\n{''.join(buf)}"
#
#     print(await run_once_py("print('hello from exec1')"))
#     print(await run_once_py("import sys; print(sys.version.split()[0])"))
#
#     # ========== 场景 B：交互式执行（需要向进程写入并读取输出） ==========
#     # 方式 B1：执行一个会从 stdin 读取的脚本
#     # async def run_with_stdin(py_snippet: str, input_data: str) -> str:
#     #     # 例子：脚本里从标准输入读一行再 print
#     #     code = (
#     #         "import sys\n"
#     #         + py_snippet
#     #     )
#     #     exec_obj = await container.exec(
#     #         cmd=["python3", "-u", "-c", code],
#     #         stdin=True,   # 允许写入 stdin
#     #         stdout=True,
#     #         stderr=True,
#     #         tty=False,    # 交互但不启 TTY，方便区分通道
#     #     )
#     #     # 使用 socket=True 拿到 websocket 进行读写
#     #     ws = await exec_obj.start(detach=False, socket=True, tty=False)
#     #     # 写入数据（记得换行让脚本读取到）
#     #     await ws.send_bytes((input_data + "\n").encode())
#     #     # 关闭写入端，告诉对方 EOF（有些脚本等 EOF）
#     #     await ws.send_eof()
#     #
#     #     # 读取输出
#     #     chunks = []
#     #     async for msg in ws:
#     #         # 不同版本可能用 .data / .extra；统一处理
#     #         data = getattr(msg, "data", None) or getattr(msg, "extra", b"")
#     #         if isinstance(data, (bytes, bytearray)):
#     #             chunks.append(data.decode(errors="ignore"))
#     #         else:
#     #             chunks.append(str(data))
#     #     await ws.close()
#     #
#     #     info = await exec_obj.inspect()
#     #     exit_code = info.get("ExitCode")
#     #     return f"[exit={exit_code}]\n{''.join(chunks)}"
#
#     # 这个 py_snippet 会从 stdin 读一行，再打印
#     # snippet = (
#     #     "line = sys.stdin.readline().strip()\n"
#     #     "print('ECHO:', line)\n"
#     # )
#     # print(await run_with_stdin(snippet, "hello from stdin"))
#     #
#     # # ========== 场景 C：真正的 REPL 式交互 ==========
#     # # REPL 更推荐开 TTY，但要注意提示符与缓冲行为
#     # async def interactive_python(lines):
#     #     exec_obj = await container.exec(
#     #         cmd=["python3", "-i", "-u"],   # -i 进入交互模式；-u 取消缓冲
#     #         stdin=True,
#     #         stdout=True,
#     #         stderr=True,
#     #         tty=True,                      # 开启 TTY，像终端一样交互
#     #     )
#     #     ws = await exec_obj.start(detach=False, socket=True, tty=True)
#     #
#     #     # 逐行发送
#     #     for ln in lines:
#     #         await ws.send_str(ln + "\n")
#     #         await asyncio.sleep(0.05)  # 给对方处理时间（简单节流）
#     #
#     #     # 退出 REPL
#     #     await ws.send_str("exit()\n")
#     #
#     #     # 读回所有输出
#     #     output = []
#     #     async for msg in ws:
#     #         data = getattr(msg, "data", "")
#     #         output.append(data if isinstance(data, str) else str(data))
#     #     await ws.close()
#     #
#     #     info = await exec_obj.inspect()
#     #     exit_code = info.get("ExitCode")
#     #     return f"[exit={exit_code}]\n{''.join(output)}"
#     #
#     # # 简单演示：在 REPL 里执行两行代码
#     # out = await interactive_python([
#     #     "import math",
#     #     "print('pi=', round(math.pi, 3))"
#     # ])
#     # print(out)
#
#     # 清理
#     await container.delete(force=True)
#     await docker.close()
#
# if __name__ == "__main__":
#     asyncio.run(main())
