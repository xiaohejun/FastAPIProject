from asgiref.sync import async_to_sync

def run_async(async_fn, *args, **kwargs):
    """在 Celery 同步任务里调用任意 async 函数。"""
    return async_to_sync(async_fn)(*args, **kwargs)