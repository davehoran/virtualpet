# Terminal Virtual Pet 🐱

A terminal-based virtual pet that lives inside your developer workflow, powered by the [Rich](https://github.com/Textualize/rich) library.

```
 /\_/\
( ^.^ )   <-- your pet
 > ω <
```

## Features

| Trigger | Effect |
|---|---|
| **git commit** | Feeds the pet (reduces hunger, boosts happiness) |
| **Browser open** | Plays with the pet (boosts happiness, drains energy) |
| **Idle ≥ 15 min** | Pet falls asleep and restores energy |
| **Active ≥ 45 min** | Break reminder — pet border turns red |

### Pet Stats
- **Fullness** — drops over time; git commits restore it
- **Happiness** — drops over time; commits + browser play restore it
- **Energy** — drains while awake/playing; restored during sleep
- **Health** — affected by hunger and happiness levels

### Pet States
`happy` · `sleeping` · `eating` · `playing` · `tired` · `hungry` · `sick`

State transitions happen automatically based on your activity and stats.

## Requirements

- Python 3.10+
- `rich` library

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Monitor the current directory's git repo
python pet.py

# Monitor a specific git repo
python pet.py /path/to/your/project
```

On first run you'll be asked to name your pet. Stats are saved daily to `~/.virtualpet_save.json` and restored if you restart on the same day.

## How the monitoring works

- **Git** — polls `git log` every 10 s; any new commit triggers a feeding event
- **Browser** — polls the process list (`ps -axo comm`) every 20 s for common browser names (Chrome, Firefox, Brave, Safari, Edge, etc.)
- **Activity** — checks every 30 s; 15 min of no git/browser activity triggers sleep, 45 min of sustained activity triggers a break reminder
- **Stats decay** — runs every 60 s while the app is open

Press **Ctrl-C** to exit gracefully. The pet's current stats are saved on exit.
