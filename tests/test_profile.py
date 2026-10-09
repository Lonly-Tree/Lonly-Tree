"""Regression tests for real counts, malformed HTML, escaping, and safe updates."""

import asyncio
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import UTC, date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts import build_profile as app

TODAY = date(2026, 10, 9)


def calendar(count: int = 1, level: int = 1) -> str:
    """Produce a complete fixture in reverse order with nested tooltip text."""
    return "".join(
        f'<td data-date="{TODAY-timedelta(days=i)}" id="d{i}" data-level="{level}"></td>'
        f'<tool-tip for="d{i}"><span>{count:,} contribution</span>s on a day.</tool-tip>'
        for i in range(365)
    )


def test_calendar_counts_and_sorting() -> None:
    days = app.parse_calendar(calendar(1234, 4), TODAY)
    assert len(days) == 365
    assert days[0].date < days[-1].date
    assert sum(day.count for day in days) == 365 * 1234
    assert days[-1].date == TODAY.isoformat()


def test_no_contributions_and_future_cells() -> None:
    html = calendar(0, 0).replace("0 contribution", "No contribution")
    html += '<td data-date="2099-01-01" data-level="0"></td>'
    assert sum(day.count for day in app.parse_calendar(html, TODAY)) == 0


def test_direct_counts() -> None:
    assert (
        app.parse_calendar(
            calendar().replace('data-level="1"', 'data-level="1" data-count="3"'), TODAY
        )[0].count
        == 3
    )


@pytest.mark.parametrize(
    "html",
    [
        "<html>GitHub is temporarily unavailable</html>",
        calendar().replace("1 contribution", "changed tooltip"),
        calendar() + '<td data-date="2026-10-09" data-level="1" data-count="1"></td>',
        calendar().replace('data-level="1"', 'data-level="5"'),
        calendar().replace('data-level="1"', 'data-level="0"'),
        calendar().replace('data-date="2026-10-08"', 'data-date="2025-01-01"'),
    ],
    ids=["unavailable", "changed-tooltip", "duplicate", "bad-level", "mismatch", "gap"],
)
def test_invalid_calendar_rejected(html: str) -> None:
    with pytest.raises(ValueError):
        app.parse_calendar(html, TODAY)


def test_stale_calendar() -> None:
    with pytest.raises(ValueError, match="stale"):
        app.parse_calendar(calendar(), TODAY + timedelta(days=10))


def test_download(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"public calendar"
    open_url = MagicMock(return_value=response)
    monkeypatch.setattr(app, "urlopen", open_url)
    assert (
        app.download("https://github.com/users/Lonly-Tree/contributions")
        == "public calendar"
    )
    assert open_url.call_args.kwargs["timeout"] == 30


def profile_folder(tmp_path: Path) -> Path:
    """Create isolated editable profile content and cached data."""
    profile = app.Profile(
        "Lonly-Tree",
        "A < B & C",
        "RAG / security",
        [["DATA", "<MongoDB>"]],
        "Keep growing.",
    )
    (tmp_path / "profile.json").write_text(
        json.dumps(asdict(profile)), encoding="utf-8"
    )
    (tmp_path / "data").mkdir()
    days = [asdict(day) for day in app.parse_calendar(calendar(), TODAY)]
    (tmp_path / "data/contributions.json").write_text(
        json.dumps({"username": "Lonly-Tree", "days": days}), encoding="utf-8"
    )
    return tmp_path


def test_offline_build_svg_and_xml_escaping(tmp_path: Path) -> None:
    root = profile_folder(tmp_path)
    asyncio.run(app.build(root, offline=True))
    assets = list((root / "assets").glob("*.svg"))
    assert len(assets) == 5
    for asset in assets:
        ET.fromstring(asset.read_text(encoding="utf-8"))
    hero = (root / "assets/profile.svg").read_text(encoding="utf-8")
    assert "A &lt; B &amp; C" in hero
    assert "prefers-reduced-motion" in hero
    graph = ET.parse(root / "assets/contributions.svg")
    cells = [item for item in graph.iter() if item.get("class") == "reveal"]
    assert len(cells) == 365
    assert max(float(item.attrib["x"]) for item in cells) < 890
    before = {asset.name: asset.read_bytes() for asset in assets}
    asyncio.run(app.build(root, offline=True))
    assert before == {asset.name: asset.read_bytes() for asset in assets}


def test_live_build_and_failure_preserves_artwork(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    root = profile_folder(tmp_path)
    monkeypatch.setattr(app, "download", lambda url: calendar())
    # Shift fixture dates to the current UTC day for the live-build path.
    shift = (datetime.now(UTC).date() - TODAY).days
    fixture = calendar()
    import re

    fixture = re.sub(
        r"\d{4}-\d{2}-\d{2}",
        lambda m: (date.fromisoformat(m[0]) + timedelta(days=shift)).isoformat(),
        fixture,
    )
    monkeypatch.setattr(app, "download", lambda url: fixture)
    asyncio.run(app.build(root))
    files = list((root / "assets").glob("*.svg")) + [root / "data/contributions.json"]
    before = [file.read_bytes() for file in files]
    monkeypatch.setattr(app, "download", lambda url: "broken response")
    with pytest.raises(ValueError):
        asyncio.run(app.build(root))
    assert before == [file.read_bytes() for file in files]


def test_username_validation(tmp_path: Path) -> None:
    root = profile_folder(tmp_path)
    config = root / "profile.json"
    config.write_text(config.read_text().replace("Lonly-Tree", "../invalid"))
    with pytest.raises(ValueError, match="username"):
        asyncio.run(app.build(root))


def test_cached_user_mismatch(tmp_path: Path) -> None:
    root = profile_folder(tmp_path)
    config = root / "profile.json"
    config.write_text(config.read_text().replace("Lonly-Tree", "another-user"))
    with pytest.raises(ValueError, match="different username"):
        asyncio.run(app.build(root, offline=True))
