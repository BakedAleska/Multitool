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

API docs are generated from docstrings with Sphinx. Install the dev
dependencies, then regenerate the module stubs and build the HTML:

```
pip install -r requirements-dev.txt
sphinx-apidoc --implicit-namespaces -f -e -o docs/source/api multitool
sphinx-build -b html docs/source docs/build
```

Open `docs/build/index.html` to view it. Re-run `sphinx-apidoc` whenever
modules are added, removed, or renamed.
