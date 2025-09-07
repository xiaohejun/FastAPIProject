# app/worker/celery.py
from app.worker.async_bridge import run_async
import os
import logging
from celery import Celery
from celery.signals import (
    worker_process_init,
    worker_process_shutdown,
    worker_init,
    worker_ready,
)
from app.core.deps import DepsContainer, init_resources, shutdown_resources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("celery")

# 每个“子进程内”的全局容器（prefork 下各子进程各自一份）
deps_container: DepsContainer | None = None


def create_app() -> Celery:
    app = Celery(
        "worker",
        broker=os.getenv("CELERY_BROKER_URL", "pyamqp://guest:@localhost:5672//"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        include=["app.worker.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        enable_utc=True,
        # 强烈建议 CLI 明确 -P prefork；也可以在这里固定：
        worker_pool="prefork",
    )
    return app


app = create_app()  # 启动：celery -A app.worker.celery:app worker -l INFO -P prefork


@worker_init.connect
def _on_worker_init(**kwargs):
    logger.info(f"[worker_init] pid={os.getpid()} kwargs={list(kwargs.keys())}")


@worker_ready.connect
def _on_worker_ready(**kwargs):
    logger.info(f"[worker_ready] pid={os.getpid()} worker is ready.")


@worker_process_init.connect
def _on_child_start(**kwargs):
    """prefork 子进程启动：创建并初始化本进程的 DepsContainer"""
    global deps_container
    logger.info(f"[worker_process_init] pid={os.getpid()} creating DepsContainer...")

    # 先创建局部变量并完成初始化，成功后再挂到全局，避免半初始化状态被读到
    deps = DepsContainer()
    try:
        run_async(init_resources, deps)
    except Exception as e:
        logger.exception("[worker_process_init] init_resources failed: %s", e)
        raise
    else:
        deps_container = deps
        logger.info(f"[worker_process_init] pid={os.getpid()} DepsContainer {id(deps_container)} ready")


@worker_process_shutdown.connect
def _on_child_shutdown(**kwargs):
    """prefork 子进程退出前：释放资源"""
    global deps_container
    logger.info(f"[worker_process_shutdown] pid={os.getpid()} shutting down DepsContainer {id(deps_container)}")
    deps, deps_container = deps_container, None  # 先摘掉全局引用，防止并发/重复调用

    if deps is None:
        logger.info("[worker_process_shutdown] nothing to shutdown (deps_container is None)")
        return

    try:
        run_async(shutdown_resources, deps)
    except Exception as e:
        logger.exception("[worker_process_shutdown] shutdown_resources failed: %s", e)
    finally:
        logger.info(f"[worker_process_shutdown] pid={os.getpid()} done")
