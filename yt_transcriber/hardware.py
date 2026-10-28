from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareStatus:
    cuda_devices: int
    cuda_ready: bool
    missing_libraries: tuple[str, ...]
    platform: str

    @property
    def summary(self) -> str:
        if self.cuda_ready:
            return f"NVIDIA GPU acceleration is ready ({self.cuda_devices} CUDA device detected)."
        if self.cuda_devices and self.missing_libraries:
            missing = ", ".join(self.missing_libraries)
            return f"NVIDIA GPU detected, but required CUDA libraries are unavailable: {missing}."
        return "No compatible NVIDIA CUDA device/runtime was detected."


def required_cuda_libraries() -> tuple[str, ...]:
    if sys.platform == "win32":
        return ("cublas64_12.dll", "cudnn64_9.dll")
    if sys.platform.startswith("linux"):
        return ("libcublas.so.12", "libcudnn.so.9")
    return ()


def _library_loadable(name: str) -> bool:
    try:
        if sys.platform == "win32":
            ctypes.WinDLL(name)
        else:
            ctypes.CDLL(name)
        return True
    except (OSError, AttributeError):
        return False


def cuda_device_count() -> int:
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def detect_hardware() -> HardwareStatus:
    count = cuda_device_count()
    required = required_cuda_libraries()
    missing = tuple(name for name in required if not _library_loadable(name)) if count else required
    return HardwareStatus(
        cuda_devices=count,
        cuda_ready=bool(count and not missing),
        missing_libraries=missing,
        platform=sys.platform,
    )


def main() -> None:
    status = detect_hardware()
    print(status.summary)
    if status.cuda_ready:
        print("Default: large-v3 with float16 for the best transcription quality.")
    else:
        if status.cuda_devices:
            print("Install CUDA 12 (cuBLAS) and cuDNN 9, then restart Windows or your terminal.")
        print("Auto mode will use the CPU until the complete GPU runtime is available.")
        print("For CPU-only machines, the small model is the recommended balance.")


if __name__ == "__main__":
    main()
