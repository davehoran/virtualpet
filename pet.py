#!/usr/bin/env python3
"""
Terminal Virtual Pet — powered by your development activity.

  git commit       → feeds the pet
  browser running  → plays with the pet
  idle 15 min      → pet falls asleep (restoring energy)
  active 45 min    → pet reminds you to take a break

Run:  python pet.py [/path/to/git/repo]
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


# ──────────────────────────────────────────────────────────────────────────────
# Pet states & visuals
# ──────────────────────────────────────────────────────────────────────────────

class State(Enum):
    HAPPY    = "happy"
    SLEEPING = "sleeping"
    EATING   = "eating"
    PLAYING  = "playing"
    TIRED    = "tired"
    HUNGRY   = "hungry"
    SICK     = "sick"


# ASCII art per state (each line same width so the panel stays stable)
ART: dict[State, list[str]] = {
    State.HAPPY:    [r" /\_/\  ", r"( ^.^ ) ", r" > ω <  "],
    State.SLEEPING: [r" /\_/\  ", r"( -.- )z", r" > ^ <  "],
    State.EATING:   [r" /\_/\  ", r"( *o* ) ", r" > ^ <  "],
    State.PLAYING:  [r" /\_/\~ ", r"( ^w^ ) ", r" > ^ <  "],
    State.TIRED:    [r" /\_/\  ", r"( x.x ) ", r" > ^ <  "],
    State.HUNGRY:   [r" /\_/\  ", r"( o.o ) ", r" >   <  "],
    State.SICK:     [r" /\_/\  ", r"( @.@ ) ", r" > ^ <  "],
}

COLORS: dict[State, str] = {
    State.HAPPY:    "bright_yellow",
    State.SLEEPING: "bright_blue",
    State.EATING:   "bright_green",
    State.PLAYING:  "bright_magenta",
    State.TIRED:    "bright_red",
    State.HUNGRY:   "orange3",
    State.SICK:     "red",
}

EMOJI: dict[State, str] = {
    State.HAPPY:    "😊",
    State.SLEEPING: "😴",
    State.EATING:   "🍖",
    State.PLAYING:  "🎮",
    State.TIRED:    "😩",
    State.HUNGRY:   "😋",
    State.SICK:     "🤒",
}

# Browser process names to look for (lower-case)
BROWSERS = [
    "chrome", "chromium", "firefox", "safari", "brave-browser",
    "brave", "opera", "msedge", "vivaldi", "waterfox", "librewolf",
    "epiphany", "falkon", "midori",
]


# ──────────────────────────────────────────────────────────────────────────────
# Virtual Pet
# ──────────────────────────────────────────────────────────────────────────────

class VirtualPet:
    SAVE_FILE = Path.home() / ".virtualpet_save.json"

    # Poll intervals (seconds)
    GIT_POLL         = 10
    BROWSER_POLL     = 20
    DECAY_INTERVAL   = 60   # stats decay once per minute
    ACTIVITY_CHECK   = 30

    # Behaviour thresholds (minutes)
    BREAK_AFTER_MIN  = 45
    SLEEP_AFTER_MIN  = 15

    def __init__(self, name: str, repo: str) -> None:
        self.name        = name
        self.repo        = Path(repo).resolve()
        self.running     = True
        self._lock       = threading.Lock()

        # Stats 0–100
        self.hunger      = 30   # 0 = full, 100 = starving
        self.happiness   = 70
        self.energy      = 80
        self.health      = 90

        # Activity
        self._last_commit: Optional[str] = self._latest_commit()
        self._last_activity               = datetime.now()
        self._session_start: Optional[datetime] = None
        self._eating_ticks                = 0
        self._playing_ticks               = 0
        self.is_sleeping                  = False
        self.break_needed                 = False
        self.browser_active               = False
        self.commits_today                = 0

        # Notifications: (time_str, rich_markup)
        self._notes: List[Tuple[str, str]] = []

        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save(self) -> None:
        data = {
            "name":         self.name,
            "hunger":       self.hunger,
            "happiness":    self.happiness,
            "energy":       self.energy,
            "health":       self.health,
            "commits_today": self.commits_today,
            "saved_at":     datetime.now().isoformat(),
        }
        try:
            self.SAVE_FILE.write_text(json.dumps(data))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if self.SAVE_FILE.exists():
                data = json.loads(self.SAVE_FILE.read_text())
                saved = datetime.fromisoformat(data.get("saved_at", "2000-01-01"))
                if saved.date() == datetime.now().date():
                    self.hunger        = int(data.get("hunger",       self.hunger))
                    self.happiness     = int(data.get("happiness",    self.happiness))
                    self.energy        = int(data.get("energy",       self.energy))
                    self.health        = int(data.get("health",       self.health))
                    self.commits_today = int(data.get("commits_today", 0))
        except Exception:
            pass

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _latest_commit(self) -> Optional[str]:
        try:
            r = subprocess.run(
                ["git", "log", "--format=%H", "-1"],
                cwd=self.repo, capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return r.stdout.strip() or None
        except Exception:
            pass
        return None

    def _browser_running(self) -> bool:
        try:
            r = subprocess.run(
                ["ps", "-axo", "comm"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                procs = r.stdout.lower()
                return any(b in procs for b in BROWSERS)
        except Exception:
            pass
        return False

    def _notify(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        with self._lock:
            self._notes.insert(0, (ts, msg))
            del self._notes[7:]

    # ── Pet actions ──────────────────────────────────────────────────────────

    def _feed(self) -> None:
        with self._lock:
            self.hunger         = max(0,   self.hunger    - 25)
            self.happiness      = min(100, self.happiness + 10)
            self._eating_ticks  = 4
            self.commits_today += 1
        self._notify(f"[green]Nom nom![/] {self.name} ate — thanks for that commit! 🍖")

    def _play(self) -> None:
        with self._lock:
            if not self.is_sleeping:
                self.happiness      = min(100, self.happiness + 2)
                self.energy         = max(0,   self.energy    - 1)
                self._playing_ticks = max(self._playing_ticks, 2)

    def _sleep(self) -> None:
        with self._lock:
            self.is_sleeping = True
        self._notify(f"[blue]zzz…[/] {self.name} fell asleep. Let them rest! 😴")

    def _wake(self) -> None:
        with self._lock:
            self.is_sleeping = False
            self.energy = min(100, self.energy + 20)
        self._notify(f"[yellow]Rise and shine![/] {self.name} woke up! ☀️")

    # ── State ────────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        if self.is_sleeping:        return State.SLEEPING
        if self._eating_ticks  > 0: return State.EATING
        if self._playing_ticks > 0: return State.PLAYING
        if self.health    < 30:     return State.SICK
        if self.energy    < 20:     return State.TIRED
        if self.hunger    > 70:     return State.HUNGRY
        return State.HAPPY

    # ── Background threads ───────────────────────────────────────────────────

    def _watch_git(self) -> None:
        while self.running:
            try:
                latest = self._latest_commit()
                if latest and latest != self._last_commit:
                    self._last_commit    = latest
                    self._last_activity  = datetime.now()
                    if self._session_start is None:
                        self._session_start = datetime.now()
                    if self.is_sleeping:
                        self._wake()
                    self._feed()
            except Exception:
                pass
            time.sleep(self.GIT_POLL)

    def _watch_browser(self) -> None:
        while self.running:
            try:
                active = self._browser_running()
                with self._lock:
                    was                 = self.browser_active
                    self.browser_active = active

                if active:
                    self._last_activity = datetime.now()
                    if self._session_start is None:
                        self._session_start = datetime.now()
                    if not was:
                        self._notify(
                            f"[magenta]Browser open![/] {self.name} wants to play! 🌐"
                        )
                    if not self.is_sleeping:
                        self._play()
                elif was and not active:
                    self._notify(
                        f"[cyan]Browser closed.[/] {self.name} misses you! 💤"
                    )
            except Exception:
                pass
            time.sleep(self.BROWSER_POLL)

    def _watch_activity(self) -> None:
        """Trigger sleep when idle; trigger break reminder when too long active."""
        while self.running:
            try:
                now      = datetime.now()
                idle_min = (now - self._last_activity).total_seconds() / 60

                # Sleep after inactivity
                if idle_min >= self.SLEEP_AFTER_MIN and not self.is_sleeping:
                    self._sleep()
                    with self._lock:
                        self._session_start = None
                        self.break_needed   = False

                # Break reminder after sustained activity
                if self._session_start and not self.is_sleeping:
                    active_min = (now - self._session_start).total_seconds() / 60
                    if active_min >= self.BREAK_AFTER_MIN:
                        with self._lock:
                            self.break_needed = True
                        self._notify(
                            f"[bold red]⚠ BREAK TIME![/] {int(active_min)} min non-stop. "
                            f"{self.name} needs you to rest! 🛑"
                        )
                    else:
                        with self._lock:
                            self.break_needed = False
            except Exception:
                pass
            time.sleep(self.ACTIVITY_CHECK)

    def _decay_stats(self) -> None:
        """Slowly degrade (or restore) stats over time."""
        while self.running:
            time.sleep(self.DECAY_INTERVAL)
            try:
                with self._lock:
                    if self.is_sleeping:
                        self.energy    = min(100, self.energy    + 8)
                        self.happiness = min(100, self.happiness + 3)
                    else:
                        self.hunger    = min(100, self.hunger    + 4)
                        self.happiness = max(0,   self.happiness - 2)
                        self.energy    = max(0,   self.energy    - 2)

                    # Health driven by hunger & happiness
                    if self.hunger > 80:
                        self.health = max(0, self.health - 4)
                    elif self.hunger < 30 and self.happiness > 50:
                        self.health = min(100, self.health + 1)

                    # Tick down animation counters
                    if self._eating_ticks  > 0: self._eating_ticks  -= 1
                    if self._playing_ticks > 0: self._playing_ticks -= 1

                self._save()
            except Exception:
                pass

    def start(self) -> None:
        for target in (
            self._watch_git,
            self._watch_browser,
            self._watch_activity,
            self._decay_stats,
        ):
            threading.Thread(target=target, daemon=True).start()

    def stop(self) -> None:
        self.running = False
        self._save()

    # ── Rendering ────────────────────────────────────────────────────────────

    @staticmethod
    def _bar(value: int, width: int = 18) -> Text:
        value  = max(0, min(100, value))
        filled = int(value / 100 * width)
        color  = "green" if value > 60 else "yellow" if value > 30 else "red"
        t = Text()
        t.append("█" * filled,          style=color)
        t.append("░" * (width - filled), style="dim")
        return t

    def render(self) -> Layout:
        st     = self.state
        color  = COLORS[st]
        now    = datetime.now()

        # ── Pet ASCII art panel ──────────────────────────────────────────
        art = Text(justify="center")
        for line in ART[st]:
            art.append(line + "\n", style=f"bold {color}")
        art.append(f"\n{EMOJI[st]}  {st.value.upper()}", style=f"bold {color}")

        border = "bold red" if self.break_needed else color
        pet_panel = Panel(
            Align.center(art, vertical="middle"),
            title=f"[bold]{self.name}[/bold]",
            border_style=border,
            padding=(1, 2),
        )

        # ── Stats panel ─────────────────────────────────────────────────
        fullness = 100 - self.hunger
        stats = Text()
        for label, val in (
            ("Fullness ", fullness),
            ("Happiness", self.happiness),
            ("Energy   ", self.energy),
            ("Health   ", self.health),
        ):
            stats.append(f" {label} ", style="bold")
            stats.append_text(self._bar(val))
            stats.append(f" {val:3d}%\n")

        stats_panel = Panel(
            stats,
            title="[bold cyan]Stats[/bold cyan]",
            border_style="cyan",
        )

        # ── Activity panel ───────────────────────────────────────────────
        idle_min    = int((now - self._last_activity).total_seconds() / 60)
        session_min = (
            int((now - self._session_start).total_seconds() / 60)
            if self._session_start else 0
        )

        act = Text()
        act.append(" Commits today  ", style="bold")
        act.append(f"{self.commits_today} 🔥\n", style="green")

        act.append(" Browser active ", style="bold")
        if self.browser_active:
            act.append("YES 🌐\n", style="bright_magenta")
        else:
            act.append("No\n", style="dim")

        act.append(" Session time   ", style="bold")
        sess_color = "red" if session_min >= self.BREAK_AFTER_MIN else "yellow"
        act.append(f"{session_min} min\n", style=sess_color)

        act.append(" Idle time      ", style="bold")
        act.append(
            f"{idle_min} min\n",
            style="bright_blue" if idle_min >= 5 else "white",
        )

        if self.break_needed:
            act.append("\n ⚠  TAKE A BREAK NOW!", style="bold red")

        act_panel = Panel(
            act,
            title="[bold magenta]Activity[/bold magenta]",
            border_style="magenta",
        )

        # ── Notifications panel ──────────────────────────────────────────
        notif = Text()
        if self._notes:
            for ts, msg in self._notes:
                notif.append(f" {ts}  ", style="dim")
                notif.append_text(Text.from_markup(msg + "\n"))
        else:
            notif.append(" Waiting for activity…", style="dim italic")

        notif_panel = Panel(
            notif,
            title="[bold yellow]Notifications[/bold yellow]",
            border_style="yellow",
        )

        # ── How-it-works panel ───────────────────────────────────────────
        help_t = Text()
        help_t.append(" git commit     → ", style="dim")
        help_t.append("feeds the pet 🍖\n", style="green")
        help_t.append(" browser open   → ", style="dim")
        help_t.append("plays with pet 🎮\n", style="magenta")
        help_t.append(f" idle {self.SLEEP_AFTER_MIN} min      → ", style="dim")
        help_t.append("pet sleeps 😴\n", style="blue")
        help_t.append(f" active {self.BREAK_AFTER_MIN} min   → ", style="dim")
        help_t.append("break reminder ⚠\n", style="red")
        help_t.append("\n Ctrl+C to exit  ", style="dim italic")

        help_panel = Panel(
            help_t,
            title="[bold]How It Works[/bold]",
            border_style="dim white",
        )

        # ── Layout assembly ──────────────────────────────────────────────
        layout = Layout()
        layout.split_row(
            Layout(pet_panel,  name="pet",   ratio=2),
            Layout(name="right", ratio=5),
        )
        layout["right"].split_column(
            Layout(name="top",           ratio=3),
            Layout(notif_panel, name="notifications", ratio=3),
            Layout(help_panel,  name="help",          ratio=2),
        )
        layout["right"]["top"].split_row(
            Layout(stats_panel, name="stats"),
            Layout(act_panel,   name="activity"),
        )
        return layout


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_name(console: Console) -> str:
    """Return saved name or ask the user."""
    save = VirtualPet.SAVE_FILE
    if save.exists():
        try:
            data = json.loads(save.read_text())
            name = data.get("name", "").strip()
            if name:
                return name
        except Exception:
            pass
    console.print("\n[bold cyan]╔══ Terminal Virtual Pet ══╗[/bold cyan]")
    name = console.input("[bold]  Name your pet: [/bold]").strip()
    return name or "Pixel"


def main() -> None:
    console = Console()
    repo    = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    if not (Path(repo) / ".git").exists():
        console.print(
            f"[yellow]⚠  No .git found at '{repo}'. "
            "Git-commit feeding is disabled.[/yellow]"
        )

    name = _resolve_name(console)
    pet  = VirtualPet(name=name, repo=repo)
    pet.start()

    console.print(
        f"\n[bold green]✓ {name} is ready![/bold green]  "
        "[dim]Commit code to feed · open a browser to play · "
        "go idle to sleep · Ctrl-C to quit[/dim]\n"
    )
    time.sleep(0.8)

    try:
        with Live(pet.render(), refresh_per_second=2, screen=True) as live:
            while True:
                time.sleep(0.5)
                live.update(pet.render())
    except KeyboardInterrupt:
        pass
    finally:
        pet.stop()
        console.print(f"\n[bold yellow]Goodbye! {name} will miss you! 👋[/bold yellow]\n")


if __name__ == "__main__":
    main()
