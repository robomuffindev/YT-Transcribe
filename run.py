from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import traceback


def setup_logging() -> Path:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "yt-transcriber.log"
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    logging.captureWarnings(True)
    return log_path


def main() -> None:
    log_path = setup_logging()
    try:
        from yt_transcriber.ui import main as run_app

        logging.getLogger(__name__).info("Starting YT Transcriber")
        run_app()
    except Exception as exc:
        logging.getLogger(__name__).exception("Application failed to start or crashed")
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "YT Transcriber",
                f"The app could not start:\n\n{exc}\n\nRun install.bat, then try again.\n\nLog: {log_path}",
            )
            root.destroy()
        except Exception:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
