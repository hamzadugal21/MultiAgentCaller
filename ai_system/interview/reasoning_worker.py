"""Isolated local inference worker for the bounded interview reasoning agent."""

import contextlib
import ctypes
import io
import json
import sys

from ai_system.interview.reasoning_agent import LocalOnnxRuntime


def _working_set_bytes() -> int | None:
    """Return this Windows worker's memory without adding a runtime dependency."""
    if sys.platform != "win32":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("page_fault_count", ctypes.c_ulong),
            ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    ):
        return None
    return int(counters.working_set_size)


def main() -> None:
    try:
        request = json.loads(sys.stdin.read())
        with contextlib.redirect_stdout(io.StringIO()):
            if request.get("runtime") != "onnx":
                raise ValueError("unsupported runtime")
            runtime = LocalOnnxRuntime(
                model_path=request["model_path"],
                max_new_tokens=request["max_new_tokens"],
                max_seconds=request["max_seconds"],
            )
            output, latency_ms = runtime.generate(request["prompt"])
        print(
            json.dumps(
                {
                    "output": output,
                    "latency_ms": latency_ms,
                    "working_set_bytes": _working_set_bytes(),
                }
            )
        )
    except (KeyError, TypeError, ValueError, OSError):
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
