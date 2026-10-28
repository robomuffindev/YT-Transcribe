# Changelog

All notable changes to this project will be documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases should use semantic versioning.

## [Unreleased]

### Added

- Sequential multi-video queue.
- Plain text, timestamped text, AI-ready Markdown, SRT, JSON, and ZIP exports.
- Automatic GPU/CPU selection with CUDA runtime validation.
- Rotating local diagnostic logs.
- Windows installation, launch, and diagnostics scripts.

### Fixed

- Auto mode no longer treats an NVIDIA driver alone as a working faster-whisper GPU runtime.
- GPU inference failures retry on CPU instead of silently abandoning the queue.

## [1.0.0] - 2026-10-28

### Added

- Initial local YouTube download and faster-whisper transcription application.
