import sys
from pathlib import Path


DEBUG = False
SHOULD_LOG_TO_FILE = True
_LOG_FILE = None


if SHOULD_LOG_TO_FILE:
    output_log = Path("output.log")
    if output_log.exists():
        output_log.unlink()
    _LOG_FILE = output_log.open("w", encoding="utf-8")


def _write_file(message: str) -> None:
    if not SHOULD_LOG_TO_FILE or _LOG_FILE is None:
        return
    _LOG_FILE.write(message + "\n")
    _LOG_FILE.flush()


def msg(text: str) -> None:
    print(text)
    _write_file(text)


def warning(text: str) -> None:
    old = "\033[0m"
    sys.stdout.write("\033[33m")
    print(text)
    sys.stdout.write(old)
    _write_file(text)


def error(text: str) -> None:
    old = "\033[0m"
    sys.stdout.write("\033[31m")
    print(text)
    sys.stdout.write(old)
    _write_file(text)


def debug_msg(text: str) -> None:
    if not DEBUG:
        return
    old = "\033[0m"
    sys.stdout.write("\033[34m")
    formatted = f"[DEBUG] {text}"
    print(formatted)
    sys.stdout.write(old)
    _write_file(formatted)
