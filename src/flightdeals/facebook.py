"""Veröffentlichung auf der Facebook-Seite über die offizielle Meta Graph API.

STANDARD: AUS. Es wird nur veröffentlicht, wenn ALLE Bedingungen erfüllt sind:
  1. config.toml  [facebook] autopublish = true
  2. Umgebungsvariable FACEBOOK_AUTOPUBLISH = "true"   (GitHub: Repository-Variable)
  3. GitHub Secrets FACEBOOK_PAGE_ID und FACEBOOK_PAGE_ACCESS_TOKEN sind gesetzt
  4. Der Beitrag enthält KEINE Testdaten
Zugangsdaten werden nur aus Umgebungsvariablen gelesen und niemals gespeichert oder ausgegeben.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)


def publishing_enabled(cfg: Config) -> tuple[bool, str]:
    if not cfg["facebook"]["autopublish"]:
        return False, "In config.toml deaktiviert (autopublish = false)"
    if os.environ.get("FACEBOOK_AUTOPUBLISH", "").lower() != "true":
        return False, "Variable FACEBOOK_AUTOPUBLISH ist nicht 'true'"
    if not os.environ.get("FACEBOOK_PAGE_ID") or not os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN"):
        return False, "FACEBOOK_PAGE_ID / FACEBOOK_PAGE_ACCESS_TOKEN fehlen"
    return True, "aktiv"


def _post_multipart(url: str, fields: dict, file_field: str, file_path: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
             f"filename=\"{file_path.name}\"\r\nContent-Type: image/png\r\n\r\n").encode()
    body += file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=bytes(body), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _post_form(url: str, fields: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def publish(post_dir: Path, cfg: Config) -> dict:
    """Lädt alle Bilder unveröffentlicht hoch und erstellt dann EINEN Beitrag mit Text und Bildern."""
    meta_path = post_dir / "beitrag.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ok, reason = publishing_enabled(cfg)
    if not ok:
        return {"veroeffentlicht": False, "grund": reason}
    if meta.get("testdaten"):
        return {"veroeffentlicht": False, "grund": "Beitrag enthält Testdaten"}
    if meta.get("veroeffentlicht"):
        return {"veroeffentlicht": True, "grund": "bereits veröffentlicht"}

    page, token = os.environ["FACEBOOK_PAGE_ID"], os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
    base = f"https://graph.facebook.com/{cfg['facebook']['graph_api_version']}/{page}"
    media = []
    for img in meta["bilder"]:
        r = _post_multipart(f"{base}/photos", {"published": "false", "access_token": token}, "source", post_dir / img)
        media.append(r["id"])
    fields = {"message": (post_dir / "beitrag.txt").read_text(encoding="utf-8"), "access_token": token}
    for i, mid in enumerate(media):
        fields[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
    r = _post_form(f"{base}/feed", fields)
    meta.update({"veroeffentlicht": True, "facebook_post_id": r.get("id"), "status": "veröffentlicht"})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Facebook-Beitrag veröffentlicht: %s", r.get("id"))
    return {"veroeffentlicht": True, "id": r.get("id")}
