from yt_transcriber import hardware


def test_windows_cuda_library_names(monkeypatch) -> None:
    monkeypatch.setattr(hardware.sys, "platform", "win32")
    assert hardware.required_cuda_libraries() == ("cublas64_12.dll", "cudnn64_9.dll")


def test_complete_cuda_runtime_is_ready(monkeypatch) -> None:
    monkeypatch.setattr(hardware, "cuda_device_count", lambda: 1)
    monkeypatch.setattr(hardware, "required_cuda_libraries", lambda: ("cublas", "cudnn"))
    monkeypatch.setattr(hardware, "_library_loadable", lambda _name: True)
    status = hardware.detect_hardware()
    assert status.cuda_ready
    assert status.missing_libraries == ()


def test_incomplete_cuda_runtime_is_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(hardware, "cuda_device_count", lambda: 1)
    monkeypatch.setattr(hardware, "required_cuda_libraries", lambda: ("cublas", "cudnn"))
    monkeypatch.setattr(hardware, "_library_loadable", lambda name: name == "cublas")
    status = hardware.detect_hardware()
    assert not status.cuda_ready
    assert status.missing_libraries == ("cudnn",)
    assert "cudnn" in status.summary
