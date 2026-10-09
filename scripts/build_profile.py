"""Generate self-contained profile SVGs with Python's standard library."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BG = "#0c1512"
TEXT = "#e3ece4"
MUTED = "#90a99a"
GREEN = "#b1ec91"
PALETTE = ["#1b2c23", "#31573a", "#4a8050", "#7cb764", GREEN]
TREE = r"""                    .
                   /|\
                 .::|::.
               .::**|**::.
              .:**/ | \**:.
            .:**/  /|\  \**:.
          .::**   / | \   **::.
             / .:* /|\ *:. \
           .::*  /  |  \  *::.
         .::**  /  /|\  \  **::.
       .::**   /  / | \  \   **::.
          / .:*  /  |  \  *:. \
        .::*   /   /|\   \   *::.
      .::**   /   / | \   \   **::.
    .::**    /   /  |  \   \    **::.
   '--------'---'---|---'---'--------'
                  |||
                  |||
                  |||
                __|||__
             __/  /|\  \__
          __/____/ | \____\__""".splitlines()


@dataclass(frozen=True)
class Day:
    """A public GitHub contribution calendar cell."""

    date: str
    count: int
    level: int


@dataclass(frozen=True)
class Profile:
    """Editable profile content loaded from profile.json."""

    username: str
    name: str
    headline: str
    rows: list[list[str]]
    tagline: str


class CalendarParser(HTMLParser):
    """Collect cells and their accessible tooltip text, regardless of order."""

    def __init__(self) -> None:
        super().__init__()
        self.cells: list[dict[str, str]] = []
        self.tips: dict[str, str] = {}
        self.target: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Collect day attributes and begin tooltip capture."""
        values = {key: value for key, value in attrs if value is not None}
        if "data-date" in values and "data-level" in values:
            self.cells.append(values)
        if tag == "tool-tip":
            self.target = values.get("for")
            if self.target:
                self.tips[self.target] = ""

    def handle_data(self, data: str) -> None:
        """Accumulate tooltip text including nested spans."""
        if self.target:
            self.tips[self.target] += data

    def handle_endtag(self, tag: str) -> None:
        """Stop capture at the end of a tooltip."""
        if tag == "tool-tip":
            self.target = None


def parse_calendar(html: str, today: date) -> list[Day]:
    """Parse and validate a complete calendar; reject changed or partial HTML."""
    parser = CalendarParser()
    parser.feed(html)
    days: dict[str, Day] = {}
    for cell in parser.cells:
        stamp = cell["data-date"]
        if date.fromisoformat(stamp) > today:
            continue
        level = int(cell["data-level"])
        tip = parser.tips.get(cell.get("id", ""), "").strip()
        if "data-count" in cell:
            count = int(cell["data-count"])
        elif re.match(r"No contributions?\b", tip, re.I):
            count = 0
        else:
            match = re.match(r"([\d,]+) contributions?\b", tip, re.I)
            if not match:
                raise ValueError(f"Missing contribution count for {stamp}")
            count = int(match[1].replace(",", ""))
        if stamp in days or not 0 <= level <= 4 or count < 0:
            raise ValueError(f"Invalid or duplicate contribution day: {stamp}")
        if (count == 0) != (level == 0):
            raise ValueError(f"Contribution level/count mismatch for {stamp}")
        days[stamp] = Day(stamp, count, level)
    result = sorted(days.values(), key=lambda day: day.date)
    if not 300 <= len(result) <= 380:
        raise ValueError("Incomplete contribution calendar; keeping existing artwork")
    first, last = date.fromisoformat(result[0].date), date.fromisoformat(
        result[-1].date
    )
    if (last - first).days + 1 != len(result) or not 0 <= (today - last).days <= 2:
        raise ValueError("Calendar is stale or contains missing days")
    return result


def download(url: str) -> str:
    """Read GitHub's public calendar with a bounded timeout."""
    request = Request(
        url, headers={"User-Agent": "Lonly-Tree-profile", "Accept-Language": "en-US"}
    )
    with urlopen(request, timeout=30) as response:
        return str(response.read().decode("utf-8"))


def text(x: float, y: float, value: str, size: int = 14, color: str = TEXT) -> str:
    """Create escaped SVG text so profile strings cannot break XML."""
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(value)}</text>'


def svg(width: int, height: int, title: str, content: str) -> str:
    """Wrap SVG content with an accessible title, background, and reduced motion."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
<title id="title">{escape(title)}</title>
<style>
text {{ font-family: 'Cascadia Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
@keyframes enter {{ from {{ opacity:0; transform:translateY(5px) }} to {{ opacity:1; transform:translateY(0) }} }}
@keyframes type {{ from {{ clip-path:inset(0 100% 0 0) }} to {{ clip-path:inset(0 0 0 0) }} }}
.reveal {{ animation:enter .45s ease-out both; }}
.tree-row {{ animation:type .25s linear both; }}
@media (prefers-reduced-motion: reduce) {{ .reveal,.tree-row {{ animation:none!important; }} }}
</style>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="18" fill="{BG}" stroke="#2b4032"/>
{content}
</svg>\n"""


def tree_group() -> str:
    """Render original ASCII tree art with one left-to-right wipe per row."""
    rows = []
    for i, row in enumerate(TREE):
        rows.append(
            f'<g class="tree-row" style="animation-delay:{i*.065:.3f}s">'
            f'<text x="20" y="{25+i*12}" xml:space="preserve" font-size="12" fill="{GREEN}">{escape(row)}</text></g>'
        )
    return "\n".join(rows)


def info_group(profile: Profile) -> str:
    """Render the neofetch-style profile details."""
    result = text(0, 20, "~/ " + profile.username, 15, GREEN)
    result += text(0, 70, "Hi, I'm " + profile.name + ".", 36)
    result += text(0, 103, profile.headline, 16, MUTED)
    result += '<path d="M0 126H465" stroke="#2b4032"/>'
    for i, (label, value) in enumerate(profile.rows):
        result += f'<g class="reveal" style="animation-delay:{.3+i*.13:.2f}s">'
        result += text(0, 157 + i * 29, label, 11, GREEN)
        result += text(104, 157 + i * 29, value, 14) + "</g>"
    return result


def profile_svg(profile: Profile) -> str:
    """Compose the tree and info in a single borderless two-column terminal."""
    content = '<path d="M1 46H919" stroke="#2b4032"/>'
    for x, color in [(25, "#cf866f"), (43, "#c3b579"), (61, "#86b980")]:
        content += f'<circle cx="{x}" cy="24" r="4" fill="{color}"/>'
    content += text(91, 29, profile.username.lower() + "@github: ~ / whoami", 12, MUTED)
    content += text(784, 29, "PROFILE / 01", 11, MUTED)
    content += f'<g transform="translate(30 93)">{tree_group()}</g>'
    content += '<path d="M401 83V402" stroke="#2b4032"/>'
    content += f'<g transform="translate(431 78)">{info_group(profile)}</g>'
    content += '<path d="M26 422H894" stroke="#2b4032"/>'
    content += text(30, 452, profile.tagline, 12, MUTED)
    content += text(754, 452, "./keep-growing", 12, GREEN)
    return svg(920, 477, profile.username + " — " + profile.headline, content)


def mobile_profile_svg(profile: Profile) -> str:
    """Stack the artwork and readable details for narrow profile pages."""
    content = text(24, 30, profile.username.lower() + "@github ~ / whoami", 12, MUTED)
    content += '<path d="M1 46H509" stroke="#2b4032"/>'
    content += f'<g transform="translate(145 61) scale(.7)">{tree_group()}</g>'
    content += f'<g transform="translate(24 266)">{info_group(profile)}</g>'
    content += '<path d="M24 601H486" stroke="#2b4032"/>'
    content += text(24, 630, profile.tagline, 11, MUTED)
    return svg(510, 654, profile.username + " developer profile", content)


def heatmap_svg(days: list[Day], username: str) -> str:
    """Render dated cells with a diagonal reveal and real totals."""
    first = date.fromisoformat(days[0].date)
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    columns = (date.fromisoformat(days[-1].date) - start).days // 7 + 1
    step = min(15.3, 810 / columns)
    content = text(28, 34, "$ git log --grow", 14, GREEN)
    content += text(28, 66, "A year of small steps.", 23)
    content += text(660, 37, f"{sum(day.count for day in days):,} contributions", 16)
    content += text(660, 60, "PUBLIC GITHUB CALENDAR", 10, MUTED)
    for row, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        content += text(28, 115 + row * 16, label, 10, MUTED)
    previous_month = ""
    last_label = -100.0
    for day in days:
        stamp = date.fromisoformat(day.date)
        offset = (stamp - start).days
        col, row = divmod(offset, 7)
        x, y = 70 + col * step, 104 + row * 16
        if stamp.strftime("%Y-%m") != previous_month:
            if x - last_label > 34:
                content += text(x, 92, stamp.strftime("%b"), 10, MUTED)
                last_label = x
            previous_month = stamp.strftime("%Y-%m")
        content += f'<rect class="reveal" x="{x:.2f}" y="{y}" width="{step-3:.2f}" height="12" rx="2.5" fill="{PALETTE[day.level]}" style="animation-delay:{.01*col+.045*row:.3f}s"><title>{day.date}: {day.count} contributions</title></rect>'
    content += text(28, 242, f"{days[0].date} / {days[-1].date}", 11, MUTED)
    content += text(715, 242, "Less", 10, MUTED)
    for i, color in enumerate(PALETTE):
        content += f'<rect x="{750+i*17}" y="232" width="12" height="12" rx="2" fill="{color}"/>'
    content += text(844, 242, "More", 10, MUTED)
    return svg(920, 266, username + " contribution calendar", content)


def save(path: Path, content: str) -> None:
    """Replace a generated file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


async def build(root: Path, offline: bool = False) -> None:
    """Fetch verified data before changing any existing generated output."""
    profile = Profile(**json.loads((root / "profile.json").read_text(encoding="utf-8")))
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", profile.username):
        raise ValueError("Invalid GitHub username")
    data_path = root / "data/contributions.json"
    if offline:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        if data["username"] != profile.username:
            raise ValueError("Cached calendar belongs to a different username")
        days = [Day(**item) for item in data["days"]]
    else:
        html = await asyncio.to_thread(
            download, f"https://github.com/users/{profile.username}/contributions"
        )
        from datetime import datetime

        days = parse_calendar(html, datetime.now(UTC).date())
    assets = root / "assets"
    outputs = {
        "profile.svg": profile_svg(profile),
        "profile-mobile.svg": mobile_profile_svg(profile),
        "tree.svg": svg(360, 300, "Animated ASCII tree", tree_group()),
        "info-card.svg": svg(
            510,
            365,
            profile.headline,
            f'<g transform="translate(22 12)">{info_group(profile)}</g>',
        ),
        "contributions.svg": heatmap_svg(days, profile.username),
    }
    for name, content in outputs.items():
        save(assets / name, content)
    save(
        data_path,
        json.dumps(
            {"username": profile.username, "days": [asdict(day) for day in days]},
            indent=2,
        )
        + "\n",
    )
    print(
        f"Built profile for {profile.username}: {len(days)} days, {sum(d.count for d in days)} contributions"
    )


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Render previously fetched data without network access",
    )
    asyncio.run(build(ROOT, offline=parser.parse_args().offline))
