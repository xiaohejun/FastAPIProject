from app.worker.async_bridge import run_async
from app.core.deps import ServiceFactory
from app.models import UserCreate
from .celery import app, deps_container


@app.task
def add(x, y):
    assert deps_container is not None
    # async def func():
    #     async with ServiceFactory(app.deps).user() as service:
    #         user = UserCreate(
    #             name="hejun",
    #             email="fff",
    #             password="fff"
    #         )
    #         user = await service.add(user)
    #         print(f"{user.model_dump_json(indent=2)}")
    #
    # run_async(func)
    return x + y


