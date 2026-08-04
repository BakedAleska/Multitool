<p align="center">
  <img src="assets/splash.svg" alt="Toolblox">
</p>

## Widgets

Widgets add game-specific functionality to Toolblox. It's open source, so build one to suit your own needs and share it.

## Is my account safe?

Yes. Login opens Roblox's own page in a separate window (`toolblox/roblox/login.py`), so Toolblox never sees your password. Only your session is kept, encrypted via Windows Credential storage or macOS Keychain, and it never leaves your computer. See `toolblox/data/crypto.py` and `toolblox/data/accounts.py`.

## A note on AI

This project is built with substantial help from Claude Code (Anthropic). Every change is reviewed before merging, and the codebase is small enough to audit yourself.

## Downloading

Get the [latest release](https://github.com/BakedAleska/Toolblox/releases/latest).

## Building from source

For development only. Requires Python 3.13, Windows or macOS, and (Windows only) the WebView2 runtime, usually preinstalled.

```
git clone https://github.com/BakedAleska/Toolblox.git
cd Toolblox
python -m venv .venv
.venv\Scripts\activate # Windows
source .venv/bin/activate # macOS
pip install -r requirements.txt
python main.py
```

Lint and type-check with `ruff check toolblox/ main.py` and `pyright`.

## More info

- API docs live on the `docs` branch, not `main`.
- See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.
- Found a bug or have a question? Open an [issue](https://github.com/BakedAleska/Toolblox/issues).
- MIT license - see [LICENSE](LICENSE).