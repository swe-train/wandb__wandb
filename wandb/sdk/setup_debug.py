"""Helper module to debug `wandb.init()` code that runs before logging."""

import os
import pathlib
import time


def log(msg: str) -> None:
    """Appends to the debugging file."""
    with _debug_output_file().open("a") as out:
        out.writelines([f"time={time.time():.3f} pid={os.getpid()} {msg}\n"])


def _debug_output_file() -> pathlib.Path:
    return pathlib.Path(
        os.getenv(
            "_WANDB_SETUP_DEBUG_FILE",
            "wandb-setup-debug.txt",
        ),
    )
