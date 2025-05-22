import inspect
from collections.abc import Callable
from functools import wraps
from time import time
from logging import getLogger

log = getLogger(__name__)


def time_log(logger_name: str):
    def measure(func: Callable):

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time()
                result = await func(*args, **kwargs)
                print(f"{func.__name__} заняла {time() - start_time} секунд")
                return result

            return async_wrapper

        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time()
                result = func(*args, **kwargs)
                print(f"{func.__name__} заняла {time() - start_time} секунд")
                return result

            return sync_wrapper

    return measure
