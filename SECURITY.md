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
