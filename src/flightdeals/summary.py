"""Zusammenfassung jedes Laufs (Markdown) – für den Ausgabeordner und die GitHub-Actions-Übersicht."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import Alert, Snapshot
from .posts import alert_line
from .texts import fmt_datetime


def write_summary(cfg: Config, now: datetime, snap: Snapshot | None, alerts: list[Alert],
                  posts: list[Path], notes: list[str]) -> str:
    lines = [f"# Lauf vom {fmt_datetime(now)}", ""]
    if snap:
        ok = sum(m.ok for m in snap.months.values())
        lines.append(f"**Preisabfrage:** {ok} von {len(snap.months)} Monaten erfolgreich.")
        for m in snap.errors:
            lines.append(f"- ❓ {m.route} {m.month.strftime('%m/%Y')}: {m.error}")
        lines.append("")
    lines.append(f"## Neue Angebote ({len(alerts)})")
    lines += [f"\n{alert_line(cfg, a)}" for a in alerts] or ["Keine neuen Angebote."]
    lines += ["", f"## Vorbereitete Beiträge ({len(posts)})"]
    lines += [f"- `{p.relative_to(cfg.output_dir)}`" for p in posts] or ["Keine."]
    if notes:
        lines += ["", "## Hinweise"] + [f"- {n}" for n in notes]
    text = "\n".join(lines) + "\n"

    out = cfg.output_dir / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"zusammenfassung_{now.strftime('%H%M')}.md").write_text(text, encoding="utf-8")
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(text)
    return text
