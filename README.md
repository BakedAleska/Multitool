## Requirements

- Python 3.13
- Windows (primary target) or macOS
- On Windows, the WebView2 runtime (preinstalled on most Windows 10/11 systems)

## Setup

Clone the repo and create a virtual environment:

```
git clone https://github.com/BakedAleska/Multitool.git
cd Multitool
python -m venv .venv
```

Activate the virtual environment:

```
# Windows
.venv\Scripts\activate

# macOS
source .venv/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

## Running

```
python main.py
```

## Linting and type checking

```
ruff check multitool/ main.py
pyright
```

## Documentation

The Sphinx API documentation lives on the `docs` branch, not `main`.

## Widget development

An installed widget (under `WIDGETS_DIR`, see Settings -> Widgets for the
path on your machine) is a separate copy from its source in this repo's
`widgets/` folder. Editing a widget's source here does not update an
already-installed copy. For now, changes have to be copied over manually
(or reinstalled through the Catalogue) to be picked up. Automatically
syncing an installed widget with its repo source during development is
not implemented yet.
