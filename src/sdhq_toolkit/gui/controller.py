"""Headless selection and single-worker job controller."""
from __future__ import annotations

import json
import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path

from ..core.operations import CancellationToken, OperationCancelled


def filter_rows(rows, query="", extension="", format_name="", state="", scope=None):
    words = query.casefold().split()
    return [row for row in rows
            if all(word in f"{row['archive']}/{row['path']}".casefold() for word in words)
            and (not extension or row["extension"].casefold() == extension.casefold())
            and (not format_name or row["format"] == format_name)
            and (not state or row["state"] == state)
            and (scope is None or any(row["archive"] == archive and
                 (not folder or row["path"].startswith(folder.rstrip("/") + "/"))
                 for archive, folder in scope))]


def resolve_selection(rows, files=(), folders=(), all_files=False):
    selected = set(files)
    result = {}
    for row in rows:
        if all_files or (row["archive"], row["path"]) in selected or any(
            row["archive"] == name and (not folder or row["path"].startswith(folder.rstrip("/") + "/"))
            for name, folder in folders
        ):
            result.setdefault(row["archive"], []).append(row["path"])
    return result


class JobController:
    """Workers emit messages only; Tk is accessed exclusively by the main thread."""
    def __init__(self):
        self.events = queue.Queue()
        self.progress = None
        self.token = None
        self.thread = None

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, name, operation, reports: Path | None = None):
        if self.busy:
            raise RuntimeError("Outra operação está em andamento")
        self.token = CancellationToken()
        self.progress = None

        def progress(current, total, detail, *_):
            self.progress = (current, total, str(detail))

        def run():
            status, result, trace = "PASS", None, None
            try:
                result = operation(cancel=self.token, progress=progress)
                if isinstance(result, dict) and result.get("status") in ("FAIL", "WARN"):
                    status = result["status"]
                elif isinstance(result, list) and any(isinstance(item, dict) and item.get("status") == "WARN" for item in result):
                    status = "WARN"
            except OperationCancelled as exc:
                status, result = "CANCELLED", str(exc)
            except Exception as exc:
                status, result, trace = "FAIL", getattr(exc, "report", str(exc)), traceback.format_exc()
            report_path = None
            if reports is not None:
                try:
                    reports.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    report_path = reports / f"gui-{stamp}.json"
                    report_path.write_text(json.dumps(dict(operation=name, status=status, result=result,
                                                          traceback=trace), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                    with (reports / "desktop.log").open("a", encoding="utf-8") as log:
                        log.write(f"{stamp} {name}: {status} | {report_path}\n")
                        if trace:
                            log.write(trace + "\n")
                except OSError as exc:
                    self.events.put(("log_error", str(exc)))
            self.events.put(("done", name, status, result, report_path))

        self.thread = threading.Thread(target=run, name="sdhq-operation", daemon=False)
        self.thread.start()

    def cancel(self):
        if self.token:
            self.token.cancel()
