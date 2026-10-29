from __future__ import annotations

import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .api import ApiServer
from .core import JobCancelled, JobResult, create_transcript_zip, is_youtube_url, process_video
from .hardware import detect_hardware


APP_NAME = "YT Transcriber"
logger = logging.getLogger(__name__)
MODEL_HELP = {
    "large-v3": "Best quality • recommended for a 12 GB RTX GPU",
    "medium": "High quality • lighter than large-v3",
    "small": "Good quality • recommended for CPU-only machines",
    "base": "Lightweight • faster on older computers",
    "tiny": "Fastest • lowest accuracy",
}
PROCESSING = {
    "Auto (GPU if available)": "auto",
    "NVIDIA GPU (CUDA)": "cuda",
    "CPU": "cpu",
}
LANGUAGES = {
    "Auto-detect": None,
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese": "zh",
    "Hindi": "hi",
}


class TranscriberApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x900")
        self.minsize(840, 740)
        self.configure(bg="#f4f6f8")

        self.events: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_result: JobResult | None = None
        self.jobs: dict[str, dict[str, object]] = {}
        self.results: dict[str, JobResult] = {}
        self.next_job_number = 1
        self.active_job_id: str | None = None
        self.api_server: ApiServer | None = None

        default_output = Path.home() / "Documents" / "YT Transcripts"
        self.hardware_status = detect_hardware()
        self.cuda_ready = self.hardware_status.cuda_ready
        default_model = "large-v3" if self.cuda_ready else "small"
        self.output_var = tk.StringVar(value=str(default_output))
        self.model_var = tk.StringVar(value=default_model)
        self.processing_var = tk.StringVar(value="Auto (GPU if available)")
        self.language_var = tk.StringVar(value="Auto-detect")
        self.keep_video_var = tk.BooleanVar(value=True)
        self.api_enabled_var = tk.BooleanVar(value=False)
        self.api_status_var = tk.StringVar(value="API off — localhost access disabled")
        self.status_var = tk.StringVar(value="Paste a YouTube link to begin.")
        if self.cuda_ready:
            hardware_note = "NVIDIA GPU runtime ready."
        elif self.hardware_status.cuda_devices:
            hardware_note = "GPU found, but CUDA 12/cuDNN 9 is incomplete; using CPU."
        else:
            hardware_note = "CPU mode detected; small is recommended."
        self.detail_var = tk.StringVar(value=f"{hardware_note} The first run downloads the selected model.")

        self._build_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f4f6f8", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#ffffff", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f4f6f8", foreground="#111827", font=("Segoe UI Semibold", 24))
        style.configure("Subtitle.TLabel", background="#f4f6f8", foreground="#64748b", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(18, 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("TCheckbutton", background="#ffffff", font=("Segoe UI", 10))
        style.configure("Horizontal.TProgressbar", troughcolor="#e5e7eb", background="#2563eb")

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, padding=(26, 14))
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="YT Transcriber", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="Download a video and turn its speech into AI-ready text — entirely on this computer.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        card = ttk.Frame(shell, style="Card.TFrame", padding=14)
        card.pack(fill="x")
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="YouTube URLs (one per line)", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.url_entry = tk.Text(card, height=2, font=("Segoe UI", 10), relief="solid", borderwidth=1, padx=8, pady=6)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 10))
        self.url_entry.focus_set()
        self.add_button = ttk.Button(card, text="Add to queue", command=self._add_to_queue)
        self.add_button.grid(row=1, column=2, sticky="nsew", padx=(8, 0), pady=(5, 10))

        ttk.Label(card, text="Save files to", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        output_entry = ttk.Entry(card, textvariable=self.output_var)
        output_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 10), ipady=4)
        ttk.Button(card, text="Browse…", command=self._browse_output).grid(row=3, column=2, padx=(8, 0), pady=(5, 10))

        options = ttk.Frame(card, style="Card.TFrame")
        options.grid(row=4, column=0, columnspan=3, sticky="ew")
        options.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(options, text="Accuracy", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        model_box = ttk.Combobox(
            options,
            textvariable=self.model_var,
            values=list(MODEL_HELP),
            state="readonly",
            width=18,
        )
        model_box.grid(row=1, column=0, sticky="ew", pady=(7, 3), padx=(0, 12))
        model_box.bind("<<ComboboxSelected>>", self._model_changed)
        self.model_help = ttk.Label(
            options,
            text=MODEL_HELP[self.model_var.get()],
            style="Card.TLabel",
            foreground="#64748b",
        )
        self.model_help.grid(row=2, column=0, sticky="w")

        ttk.Label(options, text="Processing", style="Section.TLabel").grid(row=0, column=1, sticky="w")
        processing_box = ttk.Combobox(
            options,
            textvariable=self.processing_var,
            values=list(PROCESSING),
            state="readonly",
            width=22,
        )
        processing_box.grid(row=1, column=1, sticky="ew", pady=(7, 3), padx=(0, 12))
        ttk.Label(
            options,
            text="Auto falls back safely to CPU",
            style="Card.TLabel",
            foreground="#64748b",
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(options, text="Spoken language", style="Section.TLabel").grid(row=0, column=2, sticky="w")
        language_box = ttk.Combobox(
            options,
            textvariable=self.language_var,
            values=list(LANGUAGES),
            state="readonly",
            width=18,
        )
        language_box.grid(row=1, column=2, sticky="ew", pady=(7, 3))
        ttk.Label(options, text="Auto-detect works well for most videos", style="Card.TLabel", foreground="#64748b").grid(
            row=2, column=2, sticky="w"
        )

        ttk.Checkbutton(
            card,
            text="Keep the downloaded video (turn off to save only the audio)",
            variable=self.keep_video_var,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 2))

        queue_card = ttk.Frame(shell, style="Card.TFrame", padding=10)
        queue_card.pack(fill="x", pady=(10, 0))
        queue_header = ttk.Frame(queue_card, style="Card.TFrame")
        queue_header.pack(fill="x", pady=(0, 8))
        ttk.Label(queue_header, text="Batch queue", style="Section.TLabel").pack(side="left")
        self.clear_button = ttk.Button(queue_header, text="Clear completed", command=self._clear_completed)
        self.clear_button.pack(side="right")
        self.remove_button = ttk.Button(queue_header, text="Remove selected", command=self._remove_selected)
        self.remove_button.pack(side="right", padx=(0, 8))

        self.queue_view = ttk.Treeview(queue_card, columns=("status", "url"), show="headings", height=3, selectmode="browse")
        self.queue_view.heading("status", text="Status")
        self.queue_view.heading("url", text="Video URL / title")
        self.queue_view.column("status", width=125, minwidth=100, stretch=False)
        self.queue_view.column("url", width=690, minwidth=350, stretch=True)
        queue_scroll = ttk.Scrollbar(queue_card, orient="vertical", command=self.queue_view.yview)
        self.queue_view.configure(yscrollcommand=queue_scroll.set)
        self.queue_view.pack(side="left", fill="x", expand=True)
        queue_scroll.pack(side="right", fill="y")
        self.queue_view.bind("<<TreeviewSelect>>", self._on_queue_select)

        api_card = ttk.Frame(shell, style="Card.TFrame", padding=(14, 10))
        api_card.pack(fill="x", pady=(10, 0))
        ttk.Label(api_card, text="Agent API", style="Section.TLabel").pack(side="left")
        self.api_toggle = ttk.Checkbutton(
            api_card,
            text="Enable localhost API",
            variable=self.api_enabled_var,
            command=self._toggle_api,
        )
        self.api_toggle.pack(side="left", padx=(14, 10))
        ttk.Label(api_card, textvariable=self.api_status_var, style="Card.TLabel", foreground="#64748b").pack(
            side="left", fill="x", expand=True
        )
        self.api_docs_button = ttk.Button(api_card, text="API docs", command=self._open_api_docs, state="disabled")
        self.api_docs_button.pack(side="right")
        self.api_instructions_button = ttk.Button(
            api_card,
            text="Agent instructions",
            command=self._show_agent_instructions,
            state="disabled",
        )
        self.api_instructions_button.pack(side="right", padx=(0, 8))

        controls = ttk.Frame(shell, padding=(0, 10))
        controls.pack(fill="x")
        self.start_button = ttk.Button(controls, text="Run queued videos", style="Primary.TButton", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(controls, text="Stop", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(controls, text="Open output folder", command=self._open_output)
        self.open_button.pack(side="right")
        self.bundle_button = ttk.Button(controls, text="Export completed ZIP", command=self._export_bundle, state="disabled")
        self.bundle_button.pack(side="right", padx=(0, 8))

        progress_card = ttk.Frame(shell, style="Card.TFrame", padding=12)
        progress_card.pack(fill="x")
        ttk.Label(progress_card, textvariable=self.status_var, style="Section.TLabel").pack(anchor="w")
        self.progress = ttk.Progressbar(progress_card, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(7, 5))
        ttk.Label(progress_card, textvariable=self.detail_var, style="Card.TLabel", foreground="#64748b").pack(anchor="w")

        result_header = ttk.Frame(shell, padding=(0, 10, 0, 5))
        result_header.pack(fill="x")
        ttk.Label(result_header, text="Transcript preview", font=("Segoe UI Semibold", 11)).pack(side="left")
        self.copy_button = ttk.Button(result_header, text="Copy transcript", command=self._copy, state="disabled")
        self.copy_button.pack(side="right")
        self.save_button = ttk.Button(result_header, text="Save transcript as…", command=self._save_transcript, state="disabled")
        self.save_button.pack(side="right", padx=(0, 8))

        text_frame = ttk.Frame(shell)
        text_frame.pack(fill="both", expand=True)
        self.preview = tk.Text(
            text_frame,
            wrap="word",
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=1,
            padx=14,
            pady=12,
            bg="#ffffff",
            fg="#1f2937",
            insertbackground="#1f2937",
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=scrollbar.set)
        self.preview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _model_changed(self, _event: object = None) -> None:
        self.model_help.configure(text=MODEL_HELP[self.model_var.get()])

    def _api_defaults(self) -> dict[str, object]:
        return {
            "output_dir": self.output_var.get().strip(),
            "model_name": self.model_var.get(),
            "language": LANGUAGES[self.language_var.get()],
            "keep_video": False,
            "device_preference": PROCESSING[self.processing_var.get()],
        }

    def _toggle_api(self) -> None:
        self.api_toggle.configure(state="disabled")
        if self.api_enabled_var.get():
            if not self.output_var.get().strip():
                self.api_enabled_var.set(False)
                self.api_toggle.configure(state="normal")
                messagebox.showerror(APP_NAME, "Choose an output folder before enabling the API.")
                return
            if self.api_server is None:
                self.api_server = ApiServer(
                    on_enqueue=lambda jobs: self.events.put(("api_enqueue", {"jobs": jobs})),
                    default_settings=self._api_defaults(),
                )
            else:
                self.api_server.update_defaults(self._api_defaults())
            self.api_status_var.set("Starting secure localhost API…")
            self.api_instructions_button.configure(state="disabled")
            self.api_docs_button.configure(state="disabled")

            def start_server() -> None:
                try:
                    assert self.api_server is not None
                    self.api_server.start()
                    if not self.api_server.wait_until_started():
                        raise RuntimeError("The local API did not start within five seconds")
                    self.events.put(("api_started", {}))
                except Exception as exc:
                    logger.exception("Could not start local API")
                    self.events.put(("api_error", {"message": str(exc)}))

            threading.Thread(target=start_server, name="api-starter", daemon=True).start()
        else:
            self.api_status_var.set("Stopping local API…")

            def stop_server() -> None:
                if self.api_server:
                    self.api_server.stop()
                self.events.put(("api_stopped", {}))

            threading.Thread(target=stop_server, name="api-stopper", daemon=True).start()

    def _show_agent_instructions(self) -> None:
        if not self.api_server or not self.api_server.running:
            messagebox.showinfo(APP_NAME, "Enable the local API first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("LLM Agent API Instructions")
        dialog.geometry("820x680")
        dialog.minsize(640, 480)
        dialog.transient(self)

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Copy these instructions into your local LLM agent", font=("Segoe UI Semibold", 13)).pack(
            anchor="w", pady=(0, 8)
        )
        ttk.Label(
            frame,
            text="The live bearer token is hidden here. Copying includes it, and it changes when the app restarts.",
            foreground="#64748b",
        ).pack(anchor="w", pady=(0, 10))
        text_widget = tk.Text(frame, wrap="word", font=("Consolas", 9), padx=12, pady=12)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        safe_instructions = self.api_server.agent_instructions().replace(
            self.api_server.token,
            "<hidden — use Copy all instructions>",
        )
        text_widget.insert("1.0", safe_instructions)
        text_widget.configure(state="disabled")
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        buttons = ttk.Frame(dialog, padding=(16, 0, 16, 16))
        buttons.pack(fill="x")

        def copy_all() -> None:
            assert self.api_server is not None
            self.clipboard_clear()
            self.clipboard_append(self.api_server.agent_instructions())
            self.update()
            copy_button.configure(text="Copied!")
            dialog.after(1600, lambda: copy_button.configure(text="Copy all instructions"))

        copy_button = ttk.Button(buttons, text="Copy all instructions", command=copy_all)
        copy_button.pack(side="left")
        ttk.Button(buttons, text="Open API docs", command=self._open_api_docs).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right")

    def _open_api_docs(self) -> None:
        if not self.api_server or not self.api_server.running:
            return
        try:
            if sys.platform == "win32":
                os.startfile(f"{self.api_server.base_url}/docs")  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", f"{self.api_server.base_url}/docs"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open API documentation: {exc}")

    def _on_close(self) -> None:
        if self.api_server:
            self.api_server.stop()
        self.destroy()

    def _browse_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.home()))
        if selected:
            self.output_var.set(selected)

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _add_to_queue(self) -> bool:
        raw = self.url_entry.get("1.0", "end").strip()
        if not raw:
            return False
        candidates = [value.strip() for value in re.split(r"\s+", raw) if value.strip()]
        valid = [url for url in candidates if is_youtube_url(url)]
        invalid = [url for url in candidates if not is_youtube_url(url)]
        existing_urls = {str(job["url"]) for job in self.jobs.values()}
        added = 0
        for url in valid:
            if url in existing_urls:
                continue
            job_id = f"job-{self.next_job_number}"
            self.next_job_number += 1
            self.jobs[job_id] = {"url": url, "status": "Queued", "error": "", "source": "desktop"}
            self.queue_view.insert("", "end", iid=job_id, values=("Queued", url))
            existing_urls.add(url)
            added += 1
        self.url_entry.delete("1.0", "end")
        if invalid:
            messagebox.showwarning(APP_NAME, f"Skipped {len(invalid)} item(s) that were not valid YouTube URLs.")
        if added:
            self.status_var.set(f"{added} video{'s' if added != 1 else ''} added to the queue.")
        return bool(added)

    def _enqueue_api_jobs(self, queued: list[dict[str, object]]) -> None:
        for item in queued:
            job_id = str(item["job_id"])
            url = str(item["url"])
            if job_id in self.jobs:
                continue
            self.jobs[job_id] = {
                "url": url,
                "status": "Queued",
                "error": "",
                "source": "api",
                "settings": dict(item["settings"]),
            }
            self.queue_view.insert("", "end", iid=job_id, values=("Queued (API)", url))
        if queued:
            self.status_var.set(f"API added {len(queued)} video{'s' if len(queued) != 1 else ''} to the queue.")
        if not (self.worker and self.worker.is_alive()):
            pending = [
                job_id
                for job_id, job in self.jobs.items()
                if job.get("status") == "Queued" and job.get("source") == "api"
            ]
            if pending:
                self._launch_batch(pending)

    def _selected_job_id(self) -> str | None:
        selected = self.queue_view.selection()
        return selected[0] if selected else None

    def _set_job_status(self, job_id: str, status: str, display: str | None = None, error: str = "") -> None:
        if job_id not in self.jobs:
            return
        self.jobs[job_id]["status"] = status
        self.jobs[job_id]["error"] = error
        label = display or str(self.jobs[job_id]["url"])
        self.queue_view.item(job_id, values=(status, label))

    def _remove_selected(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        job_id = self._selected_job_id()
        if not job_id:
            return
        self.queue_view.delete(job_id)
        if self.jobs.get(job_id, {}).get("source") == "api" and self.api_server:
            self.api_server.store.cancel(job_id)
        self.jobs.pop(job_id, None)
        self.results.pop(job_id, None)
        self.last_result = None
        self._set_preview("")
        self._refresh_export_buttons()

    def _clear_completed(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        removable = [
            job_id for job_id, job in self.jobs.items() if str(job.get("status")) in {"Done", "Failed", "Cancelled"}
        ]
        for job_id in removable:
            self.queue_view.delete(job_id)
            self.jobs.pop(job_id, None)
            self.results.pop(job_id, None)
        self.last_result = None
        self._set_preview("")
        self._refresh_export_buttons()

    def _on_queue_select(self, _event: object = None) -> None:
        job_id = self._selected_job_id()
        if job_id and job_id in self.results:
            self.last_result = self.results[job_id]
            self._set_preview(self.last_result.text)
        elif job_id and self.jobs.get(job_id, {}).get("error"):
            self.last_result = None
            self._set_preview(f"This video failed:\n\n{self.jobs[job_id]['error']}")
        else:
            self.last_result = None
            self._set_preview("")
        self._refresh_export_buttons()

    def _refresh_export_buttons(self) -> None:
        selected_ready = self.last_result is not None
        state = "normal" if selected_ready else "disabled"
        self.copy_button.configure(state=state)
        self.save_button.configure(state=state)
        self.bundle_button.configure(state="normal" if self.results else "disabled")

    def _start(self) -> None:
        if self.url_entry.get("1.0", "end").strip():
            self._add_to_queue()
        if not self.output_var.get().strip():
            messagebox.showerror(APP_NAME, "Choose a folder for the downloaded files.")
            return

        pending = [job_id for job_id, job in self.jobs.items() if job.get("status") == "Queued"]
        if not pending:
            messagebox.showinfo(APP_NAME, "Add one or more YouTube URLs to the queue first.")
            self.url_entry.focus_set()
            return

        desktop_settings = {
            "output_dir": self.output_var.get().strip(),
            "model_name": self.model_var.get(),
            "language": LANGUAGES[self.language_var.get()],
            "keep_video": self.keep_video_var.get(),
            "device_preference": PROCESSING[self.processing_var.get()],
        }
        for job_id in pending:
            if "settings" not in self.jobs[job_id]:
                self.jobs[job_id]["settings"] = dict(desktop_settings)
        self._launch_batch(pending)

    def _launch_batch(self, pending: list[str]) -> None:
        if not pending or (self.worker and self.worker.is_alive()):
            return
        self.cancel_event.clear()
        self.progress.configure(value=0, mode="determinate")
        self.status_var.set(f"Starting batch of {len(pending)} video{'s' if len(pending) != 1 else ''}…")
        self.detail_var.set("Videos run one at a time to make reliable use of the GPU.")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.add_button.configure(state="disabled")
        self.remove_button.configure(state="disabled")
        self.clear_button.configure(state="disabled")
        self.worker = threading.Thread(target=self._run_batch, args=(pending,), daemon=True)
        self.worker.start()

    def _run_batch(self, pending: list[str]) -> None:
        completed = 0
        failed = 0
        total = len(pending)
        for index, job_id in enumerate(pending, start=1):
            if self.cancel_event.is_set():
                break
            url = str(self.jobs[job_id]["url"])
            settings = dict(self.jobs[job_id]["settings"])
            self.events.put(("batch_job_started", {"job_id": job_id, "index": index, "total": total, "url": url}))
            try:
                def report(event: str, payload: dict, current_id: str = job_id) -> None:
                    if self.api_server and self.jobs.get(current_id, {}).get("source") == "api":
                        self.api_server.store.update_event(current_id, event, payload)
                    self.events.put((event, {**payload, "job_id": current_id}))

                result = process_video(
                    url=url,
                    **settings,
                    callback=report,
                    cancel_event=self.cancel_event,
                )
                completed += 1
                self.events.put(
                    ("job_done", {"job_id": job_id, "result": result, "index": index, "total": total})
                )
            except JobCancelled:
                self.events.put(("job_cancelled", {"job_id": job_id}))
                break
            except Exception as exc:
                failed += 1
                logger.exception("Queue item failed: %s", url)
                self.events.put(
                    ("job_error", {"job_id": job_id, "message": str(exc), "index": index, "total": total})
                )
        self.events.put(
            (
                "batch_done",
                {
                    "completed": completed,
                    "failed": failed,
                    "stopped": self.cancel_event.is_set(),
                    "total": total,
                    "api_only": all(self.jobs[job_id].get("source") == "api" for job_id in pending),
                },
            )
        )

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Stopping…")
        self.detail_var.set("The current operation is being stopped safely.")
        self.cancel_button.configure(state="disabled")

    def _drain_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                self._handle_event(event, payload)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _handle_event(self, event: str, payload: dict) -> None:
        if event == "api_started":
            assert self.api_server is not None
            self.api_enabled_var.set(True)
            self.api_toggle.configure(state="normal")
            self.api_status_var.set(f"API on • {self.api_server.base_url} • bearer token required")
            self.api_instructions_button.configure(state="normal")
            self.api_docs_button.configure(state="normal")
        elif event == "api_stopped":
            self.api_enabled_var.set(False)
            self.api_toggle.configure(state="normal")
            self.api_status_var.set("API off — localhost access disabled")
            self.api_instructions_button.configure(state="disabled")
            self.api_docs_button.configure(state="disabled")
        elif event == "api_error":
            self.api_enabled_var.set(False)
            self.api_toggle.configure(state="normal")
            self.api_status_var.set("API failed to start")
            self.api_instructions_button.configure(state="disabled")
            self.api_docs_button.configure(state="disabled")
            messagebox.showerror(APP_NAME, str(payload.get("message", "Could not start the local API")))
        elif event == "api_enqueue":
            self._enqueue_api_jobs(list(payload.get("jobs") or []))
        elif event == "batch_job_started":
            job_id = str(payload["job_id"])
            self.active_job_id = job_id
            self._set_job_status(job_id, "Processing")
            if self.api_server and self.jobs.get(job_id, {}).get("source") == "api":
                self.api_server.store.set_processing(job_id)
            self.queue_view.selection_set(job_id)
            self.queue_view.see(job_id)
            self.status_var.set(f"Video {payload['index']} of {payload['total']}: starting…")
            self.detail_var.set(str(payload["url"]))
        elif event == "stage":
            self.status_var.set(str(payload.get("message", "Working…")))
            if "model" in self.status_var.get().lower():
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
        elif event == "download":
            self.progress.stop()
            self.progress.configure(mode="determinate")
            percent = payload.get("percent")
            if percent is not None:
                self.progress["value"] = float(percent)
                self.status_var.set(f"Downloading… {float(percent):.0f}%")
            speed = float(payload.get("speed") or 0)
            eta = payload.get("eta")
            details = []
            if speed:
                details.append(f"{speed / 1_048_576:.1f} MB/s")
            if eta is not None:
                details.append(f"about {int(eta)} seconds remaining")
            self.detail_var.set(" • ".join(details) or "Downloading media from YouTube.")
        elif event == "transcribe":
            self.progress.stop()
            self.progress.configure(mode="determinate")
            percent = payload.get("percent")
            current = float(payload.get("current") or 0)
            duration = float(payload.get("duration") or 0)
            if percent is not None:
                self.progress["value"] = min(100, float(percent))
                self.status_var.set(f"Transcribing locally… {float(percent):.0f}%")
            self.detail_var.set(f"Processed {self._short_time(current)} of {self._short_time(duration)}")
        elif event == "job_done":
            self._finish_success(
                str(payload["job_id"]), payload["result"], int(payload["index"]), int(payload["total"])
            )
        elif event == "job_cancelled":
            self.progress.stop()
            job_id = str(payload["job_id"])
            self._set_job_status(job_id, "Cancelled")
            if self.api_server and self.jobs.get(job_id, {}).get("source") == "api":
                self.api_server.store.cancel(job_id)
        elif event == "job_error":
            self.progress.stop()
            message = str(payload.get("message", "Unknown error"))
            job_id = str(payload["job_id"])
            self._set_job_status(job_id, "Failed", error=message)
            if self.api_server and self.jobs.get(job_id, {}).get("source") == "api":
                self.api_server.store.fail(job_id, message)
            self.status_var.set(f"Video {payload['index']} of {payload['total']} failed; continuing…")
            self.detail_var.set(message)
        elif event == "batch_done":
            self.progress.stop()
            self.progress.configure(mode="determinate", value=100 if payload["completed"] else 0)
            self._reset_controls()
            completed = int(payload["completed"])
            failed = int(payload["failed"])
            stopped = bool(payload["stopped"])
            if stopped:
                self.status_var.set("Batch stopped")
                self.detail_var.set(f"{completed} completed, {failed} failed. Queued videos can be run later.")
            else:
                self.status_var.set("Batch complete")
                self.detail_var.set(f"{completed} completed, {failed} failed. Transcript files are ready to export.")
                if not payload.get("api_only"):
                    messagebox.showinfo(
                        APP_NAME,
                        f"Batch complete: {completed} transcript{'s' if completed != 1 else ''} ready"
                        + (f", {failed} failed." if failed else "."),
                    )
            self.active_job_id = None
            self._refresh_export_buttons()
            pending_api = [
                job_id
                for job_id, job in self.jobs.items()
                if job.get("status") == "Queued" and job.get("source") == "api"
            ]
            if pending_api and not stopped:
                self.after(100, lambda: self._launch_batch(pending_api))
        elif event == "cancelled":
            # Backward-compatible event for a single job interrupted by a dependency.
            self.progress.stop()
            self.status_var.set("Stopped")
            self._reset_controls()

    @staticmethod
    def _short_time(seconds: float) -> str:
        minutes, secs = divmod(max(0, int(seconds)), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"

    def _finish_success(self, job_id: str, result: JobResult, index: int, total: int) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self.results[job_id] = result
        if self.api_server and self.jobs.get(job_id, {}).get("source") == "api":
            self.api_server.store.complete(job_id, result)
        self.last_result = result
        probability = f" ({result.language_probability:.0%} confidence)" if result.language_probability else ""
        self._set_job_status(job_id, "Done", display=result.title)
        self.status_var.set(f"Video {index} of {total} complete")
        processor = "NVIDIA GPU" if result.device == "cuda" else "CPU"
        self.detail_var.set(f"{result.title} • {processor} • Language: {result.language}{probability}")
        self._set_preview(result.text)
        self._refresh_export_buttons()

    def _reset_controls(self) -> None:
        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.add_button.configure(state="normal")
        self.remove_button.configure(state="normal")
        self.clear_button.configure(state="normal")

    def _copy(self) -> None:
        if not self.last_result:
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_result.text)
        self.update()
        self.copy_button.configure(text="Copied!")
        self.after(1600, lambda: self.copy_button.configure(text="Copy transcript"))

    def _save_transcript(self) -> None:
        if not self.last_result:
            return
        source = Path(self.last_result.ai_ready_path)
        destination = filedialog.asksaveasfilename(
            title="Save AI-ready transcript",
            initialdir=self.output_var.get(),
            initialfile=source.name,
            defaultextension=".md",
            filetypes=[("AI-ready Markdown", "*.md"), ("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not destination:
            return
        try:
            if Path(destination).suffix.lower() == ".txt":
                shutil.copy2(self.last_result.transcript_path, destination)
            else:
                shutil.copy2(source, destination)
            self.status_var.set("Transcript exported")
            self.detail_var.set(str(Path(destination).resolve()))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save the transcript: {exc}")

    def _export_bundle(self) -> None:
        if not self.results:
            return
        destination = filedialog.asksaveasfilename(
            title="Export completed transcripts",
            initialdir=self.output_var.get(),
            initialfile=f"YT-Transcripts-{datetime.now():%Y%m%d-%H%M}.zip",
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not destination:
            return
        try:
            create_transcript_zip(self.results.values(), destination)
            self.status_var.set("Transcript ZIP exported")
            self.detail_var.set(str(Path(destination).resolve()))
            messagebox.showinfo(APP_NAME, "The completed transcripts are bundled and ready to upload to an LLM.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not create the ZIP archive: {exc}")

    def _open_output(self) -> None:
        path = Path(self.output_var.get()).resolve()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open the folder: {exc}")


def main() -> None:
    app = TranscriberApp()
    app.mainloop()
