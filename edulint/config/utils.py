from typing import Any, Optional, Union
from loguru import logger

from edulint.options import Option


def print_invalid_type_message(option: Union[Option, str], val: Any) -> None:
    logger.warning(
        "invalid value type {type} of value {val} for option {option}",
        type=type(val),
        val=val,
        option=option.to_name() if isinstance(option, Option) else option,
    )


def config_file_val_to_str(option: Union[Option, str], val: Any) -> Optional[str]:
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return ",".join(val)
    if isinstance(val, tuple):
        key, value = val
        value = config_file_val_to_str(option, value)
        return f"--{key}={value}" if value is not None else None
    print_invalid_type_message(option, val)
    return None
