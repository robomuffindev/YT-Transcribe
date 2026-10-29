# Elementor page copy: YT Transcriber

This copy is organized as modular Elementor sections. The headings, body copy, button labels, image alt text, and SEO fields can be pasted directly into an app landing page.

## SEO fields

**Page title:** YT Transcriber — Local YouTube Transcription for People and AI Agents

**Meta title:** YT Transcriber | Local AI-Ready Video Transcription

**Meta description:** Download authorized YouTube videos, transcribe them locally with Whisper, process multi-video queues, and let local AI agents retrieve transcripts through a secure localhost API.

**Suggested URL slug:** `yt-transcriber`

## Hero section

**Eyebrow:** A Robomuffin Labs local AI tool

**Headline:** Turn videos into AI-ready knowledge—on your own computer.

**Subheadline:** YT Transcriber downloads authorized YouTube videos, transcribes them locally with Whisper, and exports clean text, Markdown, subtitles, JSON, and batch ZIPs. Queue several videos, walk away, and return to transcripts ready for research, review, or an LLM.

**Primary button:** View on GitHub

**Secondary button:** Read the setup guide

**Primary button URL:** `https://github.com/robomuffindev/YT-Transcribe`

**Secondary button URL:** `https://github.com/robomuffindev/YT-Transcribe#quick-start`

**Small trust line:** No transcription API key. GPU acceleration and CPU fallback. Localhost agent API is off by default.

**Hero image:** `docs/images/yt-transcriber-feature.png`

**Hero image alt text:** YT Transcriber workflow connecting an online video, audio waveform, transcript document, local AI tools, batch queue, and GPU computer.

## Intro section

**Heading:** One local workflow from video URL to usable context

YT Transcriber is made for the point where watching is too slow and raw captions are not enough. Paste one or more video URLs, choose the quality and processing mode, and let the app create a consistent set of transcript files. The results are easy to read, archive, search, subtitle, or pass to an AI assistant.

Everything is controlled from a Windows desktop interface. Transcription runs locally through faster-whisper. The app can use a correctly configured NVIDIA GPU for maximum speed and quality, or fall back to lighter Whisper models on CPU-only systems.

## Feature cards

### Batch it and walk away

Add several videos to one sequential queue. A failed item is isolated, the next item continues, and every successful transcript remains ready to export.

### Built for AI context

Create clean text and AI-ready Markdown alongside timestamped text, SRT subtitles, and structured JSON. Export all completed transcript formats in one ZIP without including the large media files.

### Local transcription

Speech recognition happens on the computer running the app. No OpenAI transcription key or paid speech-to-text service is required.

### Quality when you have the hardware

Use Whisper `large-v3` with a capable NVIDIA GPU for the best general accuracy. YT Transcriber validates the CUDA runtime before starting and can retry on CPU if Auto mode encounters a GPU inference failure.

### Practical CPU options

No GPU is required. Choose `small`, `base`, or `tiny` for computers where speed and memory use matter more than maximum accuracy.

### A secure local API for agents

Turn on the localhost API only when another app needs it. Your local agent can submit one video or a batch, monitor progress, retrieve transcripts, or download generated files using a session bearer token and a discoverable OpenAPI schema.

## How it works

**Heading:** From link to transcript in four steps

1. Paste one or more authorized YouTube URLs and add them to the queue.
2. Choose the Whisper model, language, output folder, and Auto, NVIDIA GPU, or CPU processing.
3. Run the queue while YT Transcriber downloads and processes each item in sequence.
4. Copy the transcript, save a file, export the completed batch, or let a local AI agent retrieve the result through the optional API.

## Agent and application integration section

**Heading:** Let your other AI tools request the context they need

YT Transcriber includes an opt-in API bound to `127.0.0.1`, so it is available only to applications on the same computer. Each app session creates a fresh bearer token. From the desktop interface, the **Agent instructions** button produces a complete, copy-ready prompt with the live URL, token, endpoints, polling rules, and recommended request bodies.

The asynchronous API supports single jobs and batches, idempotency keys for safe retries, queue and progress status, multiple transcript formats, generated-file downloads, Swagger documentation, and a machine-readable OpenAPI schema. The API uses the same sequential queue as desktop work, helping keep GPU memory use predictable.

**Callout:** The API is disabled by default and is not designed to be exposed through a public tunnel or directly to the internet.

## Output formats section

**Heading:** The right file for the next step

- Plain text for quick copy and paste
- AI-ready Markdown with source context
- Timestamped text for human review
- SRT captions and subtitle workflows
- JSON with metadata and timed segments
- ZIP exports containing every transcript format from completed jobs

## Hardware section

**Heading:** Use your RTX card—or run comfortably without one

For a 12 GB RTX-class card, the recommended setup is Whisper `large-v3`, CUDA 12.x cuBLAS, and cuDNN 9 for CUDA 12. GPU mode uses `float16`. Auto mode checks that the required NVIDIA libraries can actually load before using CUDA.

On CPU-only computers, YT Transcriber defaults to the `small` model and `int8` processing. The `base` and `tiny` models provide even lighter options for older machines.

## Requirements section

**Heading:** What you need

- 64-bit Windows 10 or Windows 11
- 64-bit Python 3.11 or 3.12
- FFmpeg for media merging and conversion
- An internet connection for video downloads and the first download of each Whisper model
- Optional NVIDIA GPU acceleration with CUDA 12.x cuBLAS and cuDNN 9 for CUDA 12

The repository includes `install.bat`, `run.bat`, and `diagnose.bat` to make setup, launch, and troubleshooting straightforward.

## Use cases section

**Heading:** Useful wherever video contains the source material

- Researching interviews, lectures, talks, and product demonstrations
- Preparing long-form video context for an LLM conversation
- Building searchable notes from several related videos
- Creating subtitles or timestamped review copies
- Giving a local AI agent a dependable way to request and retrieve transcripts
- Archiving authorized material in consistent, portable formats

## Privacy and responsible-use section

**Heading:** Local by design, responsible by requirement

Transcript text is not sent to OpenAI or another LLM service by YT Transcriber. Network access is used to download source media, fetch Whisper models on first use, and install or update dependencies. Files remain local unless you choose to share them.

Download and transcribe only media you are authorized to use. Users are responsible for YouTube's terms, copyright law, privacy obligations, and any rules governing the source material.

## FAQ

### Does it require an API key?

No transcription API key is required. The optional local integration API creates its own temporary session token for authentication.

### Can I queue several videos?

Yes. Add multiple URLs at once or add several queue groups. Jobs run sequentially so the app does not exhaust GPU memory.

### Which Whisper model should I use?

Use `large-v3` for the best general accuracy on a capable GPU. Use `small` for a good CPU balance, and `base` or `tiny` when lower resource use matters most.

### Does it work without an NVIDIA GPU?

Yes. CPU mode uses `int8` inference. Long videos take longer, but the complete workflow remains available.

### Can another LLM or application use it automatically?

Yes, when that tool runs on the same computer and can make HTTP requests. Enable the API toggle, open **Agent instructions**, and copy the generated instructions into the agent.

### Is the local API exposed to my network?

No. It binds to `127.0.0.1` and is off by default. It is intended only for applications on the same computer.

## Closing call to action

**Heading:** Make the useful information in a video ready to work with.

Queue the source material, let local Whisper handle the transcription, and bring the result into the research or AI workflow of your choice.

**Primary button:** Get YT Transcriber on GitHub

**Secondary button:** Visit Robomuffin Labs

**Primary button URL:** `https://github.com/robomuffindev/YT-Transcribe`

**Secondary button URL:** `https://robomuffinlabs.com/`

## Screenshot gallery copy

### Main desktop workflow

**Image:** `docs/images/app-main.png`

**Alt text:** YT Transcriber desktop app showing URL input, model and processing controls, batch queue, progress, and transcript preview.

### Local API enabled

**Image:** `docs/images/app-api-enabled.png`

**Alt text:** YT Transcriber with the localhost Agent API enabled and authenticated API controls available.

### Copy-ready agent instructions

**Image:** `docs/images/app-agent-instructions.png`

**Alt text:** YT Transcriber agent instructions window showing the local API workflow with the private bearer token hidden.

## Suggested Elementor layout

1. Full-width dark hero using the featured image, with copy positioned in the available negative space.
2. Two-column intro with the main desktop screenshot.
3. Six feature cards in a three-column grid.
4. Four-step process strip.
5. Dark API integration section with the API-enabled and agent-instructions screenshots.
6. Output-format icon row.
7. Two-column GPU/CPU hardware section.
8. Requirements and use cases.
9. FAQ accordion.
10. Responsible-use note and final call to action.

Keep the screenshot images uncropped so interface labels remain readable. Use the feature image as a background or full-bleed visual with a dark overlay behind any added Elementor text.
