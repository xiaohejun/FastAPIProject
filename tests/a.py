import asyncio
from pydoc import cli

from fastapi import FastAPI
import httpx
from httpx_sse import aconnect_sse
from sse_starlette.sse import EventSourceResponse
from fastapi.responses import StreamingResponse
from starlette.applications import Starlette
from starlette.routing import Route


app = FastAPI()


async def fake_video_streamer():
    for i in range(10):
        yield b"some fake video bytes"


@app.post("/")
async def main(task_id: str):
    return StreamingResponse(fake_video_streamer())


async def main():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with client.stream(
            "POST",
            "/",
            params={"task_id": "123"},
            # headers={"Accept": "text/event-stream"},
            # follow_redirects=True,
        ) as response:
            # 确保是SSE响应
            # response.raise_for_status()
            print(response)
            # print(response.json())
            async for chunk in response.aiter_bytes():
                # Process each chunk of bytes
                print(f"Received chunk of size: {chunk}")
            # print(response.json())
            # if response.headers.get("content-type") != "text/event-stream":
            #     raise ValueError("Response is not an event stream")

            # # 使用 EventSource 处理事件流
            # async for event in EventSource(response.aiter_lines()):
            #     # 处理服务器发送的事件
            #     if event.event == "message":
            #         print(f"收到消息: {event.data}")
            #     elif event.event == "update":
            #         print(f"收到更新: {event.data}")
            #     # 可以根据event.event类型处理不同事件


# async with httpx.AsyncClient(transport=httpx.ASGITransport(app)) as client:
#     async for x in client.stream("GET", "http://localhost:8000/sse/auth/"):
#         print(x)


asyncio.run(main())
