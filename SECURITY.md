# Security policy

## Supported versions

Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature when it is enabled for the repository. Do not open a public issue for vulnerabilities involving command execution, path handling, dependency compromise, credential exposure, or unsafe media parsing.

Include reproduction steps, affected versions, likely impact, and any suggested mitigation. Do not include authentication cookies, private video URLs, tokens, or personal transcript content.

## Data and trust boundaries

- Video media is downloaded from URLs supplied by the user.
- Transcription is local, but model files are downloaded from Hugging Face on first use.
- YouTube access is handled by yt-dlp and may contact YouTube and its supporting services.
- Output files and logs remain local unless the user uploads or shares them.
- This project does not require an OpenAI or other transcription API key.
- The optional integration API is disabled by default and binds only to `127.0.0.1`.
- Every `/v1` API request requires a high-entropy bearer token generated for the current app session.
- The in-app instruction preview masks that token; copying the instructions intentionally includes it.
- The API does not enable CORS or allow clients to choose arbitrary output directories.

## Local API guidance

Treat the session bearer token like a password. Share it only with a trusted local application that needs to call YT Transcriber. Do not place it in source control, screenshots, public logs, analytics, or remote prompts.

The API is not hardened as a public or multi-user network service. Do not expose port `8765` through a public tunnel, reverse proxy, router port forward, or firewall rule. Doing so would require a separate threat review plus TLS, network authentication, rate limiting, access logging, and resource controls.
