"""Verify the real localhost API, authentication, submission, and idempotency."""

from __future__ import annotations

import json
import socket
from tempfile import gettempdir
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from yt_transcriber.api import ApiServer


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    queued: list[dict] = []
    server = ApiServer(
        on_enqueue=lambda jobs: queued.extend(jobs),
        default_settings={
            "output_dir": gettempdir(),
            "model_name": "small",
            "language": None,
            "keep_video": False,
            "device_preference": "cpu",
        },
        port=free_port(),
    )
    server.start()
    if not server.wait_until_started():
        raise RuntimeError(f"API did not start: {server._start_error!r}")
    try:
        with urlopen(f"{server.base_url}/health", timeout=5) as response:
            health = json.load(response)
        try:
            urlopen(f"{server.base_url}/v1/capabilities", timeout=5)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("Protected API endpoint accepted a request without authentication")
        request = Request(
            f"{server.base_url}/v1/capabilities",
            headers={"Authorization": f"Bearer {server.token}"},
        )
        with urlopen(request, timeout=5) as response:
            capabilities = json.load(response)
        assert health["status"] == "ok"
        assert capabilities["queue_mode"] == "sequential"
        payload = json.dumps(
            {
                "url": "https://youtu.be/api-smoke-test",
                "model": "small",
                "device": "cpu",
                "idempotency_key": "api-smoke-test",
            }
        ).encode("utf-8")
        submit_request = Request(
            f"{server.base_url}/v1/jobs",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {server.token}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(submit_request, timeout=5) as response:
            submitted = json.load(response)
        assert submitted["status"] == "queued"
        assert len(queued) == 1
        with urlopen(submit_request, timeout=5) as response:
            duplicate = json.load(response)
        assert duplicate["job_id"] == submitted["job_id"]
        assert duplicate["deduplicated"] is True
        assert len(queued) == 1

        status_request = Request(
            f"{server.base_url}/v1/jobs/{submitted['job_id']}",
            headers={"Authorization": f"Bearer {server.token}"},
        )
        with urlopen(status_request, timeout=5) as response:
            job = json.load(response)
        assert job["status"] == "queued"
        print(f"API smoke test passed at {server.base_url}")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
