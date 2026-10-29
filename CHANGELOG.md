# Changelog

All notable changes to this project will be documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases should use semantic versioning.

## [Unreleased]

## [1.1.0] - 2026-10-28

### Added

- Opt-in, bearer-authenticated localhost API for local LLM agents and applications.
- Single-job and batch submission endpoints with idempotency support.
- Queue status, progress, transcript retrieval, and generated-file download endpoints.
- In-app copy-ready agent instructions, interactive API docs, and OpenAPI schema.
- Public-safe application screenshots, website feature artwork, and Elementor page copy.
- API integration tests and a real localhost smoke-test script.
- Sequential multi-video queue.
- Plain text, timestamped text, AI-ready Markdown, SRT, JSON, and ZIP exports.
- Automatic GPU/CPU selection with CUDA runtime validation.
- Rotating local diagnostic logs.
- Windows installation, launch, and diagnostics scripts.

### Changed

- Compacted the desktop layout so the transcript preview remains visible at common display heights.
- API tokens are hidden in the on-screen agent instructions while the copy button still includes the live token.

### Fixed

- Auto mode no longer treats an NVIDIA driver alone as a working faster-whisper GPU runtime.
- GPU inference failures retry on CPU instead of silently abandoning the queue.

## [1.0.0] - 2026-10-28

### Added

- Initial local YouTube download and faster-whisper transcription application.
