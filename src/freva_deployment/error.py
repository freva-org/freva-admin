"""Definition of custom Errors."""

import sys
from functools import partial, wraps
from types import TracebackType
from typing import Any, Callable, Optional, Type

from rich import print as pprint

from .logger import logger


class DeploymentError(BaseException):
    """Define an error for when the deployment goes wrong.

    For this error suppresses the stack trace, since it has nothing to do
    with the code."""

    def __init__(self, message: str = "") -> None:
        print(message)
        logger.error(f"{self.__class__.__name__}: Deployment failed!")
        self.error = message

    def __str__(self) -> str:
        return ""

    def __rep__(self) -> str:
        return f"{self.__class__.__name__}: {self.error}"


class ConfigurationError(BaseException):
    """Define an error when something was mis-configured."""

    def __init__(self, message: str = "") -> None:
        self.error = message

    def __str__(self) -> str:
        return ""

    def __rep__(self) -> str:
        return f"{self.__class__.__name__}: {self.error}"


def handled_exception(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap the exception handler around a function."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrapper function that handles the exception."""
        sys.excepthook = partial(exception_hook, _sys_handler=sys.excepthook)
        try:
            return func(*args, **kwargs)
        except (ConfigurationError, DeploymentError) as exception:
            raise strip_traceback(exception) from None

    return wrapper


def exception_hook(
    exception_type: Type[BaseException],
    exception: BaseException,
    traceback: TracebackType,
    _sys_handler: Callable[
        [Type[BaseException], BaseException, Optional[TracebackType]], Any
    ] = sys.excepthook,
) -> Any:
    """Make certain types of exceptions silent."""
    if isinstance(exception, ConfigurationError):
        while traceback.tb_next:
            traceback = traceback.tb_next
        code = traceback.tb_frame.f_code
        msg = (
            "Traceback (offending line only):\n"
            f'File "{code.co_filename}", in line {traceback.tb_lineno}, '
            f"in {code.co_name}"
        )
        logger.critical("%s\n%s", exception.__rep__(), msg)
        return exception
    if isinstance(exception, DeploymentError):
        return exception
    return _sys_handler(exception_type, exception, traceback)


def strip_traceback(exception: BaseException) -> BaseException:
    """Get rid of all the tracbacks, expect the last one."""
    traceback = exception.__traceback__
    if traceback is None:
        return exception
    while traceback.tb_next:
        traceback = traceback.tb_next
    exception.__traceback__ = traceback
    return exception
