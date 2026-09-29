"""Synchronize local Markdown summaries and Notion status properties.

Only pages created by this worker are updated. Notion status is mirrored to a
local sidecar; the worker never overwrites user-authored Markdown.
"""

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LOG = logging.getLogger("jaios-sync")
API = "https://api.notion.com/v1"


class SyncEngine:
    def __init__(self, root: Path, token: str, database_id: str, interval: int = 30):
        if not token or not database_id:
            raise ValueError("NOTION_TOKEN and NOTION_DATABASE_ID are required")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / ".jaios-sync-state.json"
        self.status_path = self.root / ".notion-status.json"
        self.database_id = database_id
        self.interval = interval
        self.lock = threading.RLock()
        self.client = httpx.Client(base_url=API, headers={
            "Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }, timeout=15)
        self.state = self._load(self.state_path)

    @staticmethod
    def _load(path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}

    @staticmethod
    def _save(path, data):
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _request(self, method, path, **kwargs):
        for attempt in range(4):
            response = self.client.request(method, path, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(min(float(response.headers.get("Retry-After", 2 ** attempt)), 30))
                continue
            response.raise_for_status()
            return response.json()

    def _key(self, path):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() != ".md" or not path.is_file():
            return None
        return path.relative_to(self.root).as_posix()

    def sync_file(self, path):
        key = self._key(path)
        if key is None:
            return
        with self.lock:
            try:
                content = (self.root / key).read_text(encoding="utf-8")
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                record = self.state.get(key, {})
                if record.get("sha256") == digest:
                    return
                # One worker-owned summary block. Large files are intentionally
                # excerpted; the full Markdown remains authoritative on disk.
                excerpt = content[:1900] or "(empty Markdown file)"
                rich_text = [{"type": "text", "text": {"content": excerpt}}]
                if record.get("page_id"):
                    self._request("PATCH", f"/blocks/{record['block_id']}", json={
                        "paragraph": {"rich_text": rich_text}})
                    self._request("PATCH", f"/pages/{record['page_id']}", json={
                        "properties": {"Name": {"title": [{"text": {"content": key[:2000]}}]}}})
                else:
                    page = self._request("POST", "/pages", json={
                        "parent": {"database_id": self.database_id},
                        "properties": {"Name": {"title": [{"text": {"content": key[:2000]}}]}},
                        "children": [{"object": "block", "type": "paragraph",
                                      "paragraph": {"rich_text": rich_text}}],
                    })
                    blocks = self._request("GET", f"/blocks/{page['id']}/children")
                    record = {"page_id": page["id"], "block_id": blocks["results"][0]["id"]}
                record["sha256"] = digest
                self.state[key] = record
                self._save(self.state_path, self.state)
                LOG.info("Synced %s", key)
            except (OSError, httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                LOG.error("Sync failed for %s: %s", key, exc)

    def poll_statuses(self):
        with self.lock:
            statuses = {}
            for key, record in list(self.state.items()):
                try:
                    page = self._request("GET", f"/pages/{quote(record['page_id'])}")
                    prop = page.get("properties", {}).get("Status", {})
                    selected = prop.get("status") or prop.get("select") or {}
                    statuses[key] = {"status": selected.get("name"),
                                     "notion_page_id": record["page_id"],
                                     "last_edited_time": page.get("last_edited_time")}
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    LOG.error("Status poll failed for %s: %s", key, exc)
            if statuses:
                self._save(self.status_path, statuses)

    def run(self):
        for path in self.root.rglob("*.md"):
            self.sync_file(path)
        handler = MarkdownHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.root), recursive=True)
        observer.start()
        try:
            while True:
                self.poll_statuses()
                time.sleep(self.interval)
        finally:
            observer.stop()
            observer.join()
            self.client.close()


class MarkdownHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_modified(self, event):
        if not event.is_directory:
            self.engine.sync_file(event.src_path)

    def on_created(self, event):
        self.on_modified(event)

    def on_moved(self, event):
        if not event.is_directory:
            self.engine.sync_file(event.dest_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SyncEngine(Path(os.getenv("WATCH_DIR", "/app/fsad_storage")),
               os.getenv("NOTION_TOKEN", ""), os.getenv("NOTION_DATABASE_ID", ""),
               int(os.getenv("POLL_INTERVAL_SECONDS", "30"))).run()
