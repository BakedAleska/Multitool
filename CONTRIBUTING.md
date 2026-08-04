## Testing the Catalogue

The Catalogue only renders on the Canary channel. Running from source
isn't enough by itself - set `TOOLBLOX_ENABLE_CANARY` to
`i-understand-this-is-unvetted` (see `.env.example`) in a local `.env`
file to opt in deliberately.

## Commits and Pull Requests

- Follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `chore:`, `docs:`). Use a plain title, and add a body
  only when necessary.
- Keep pull requests focused on a single change, and explain the
  rationale in the description rather than restating the diff.

## Before Opening a Pull Request

Run lint, type-check, and a real launch:

```
ruff check toolblox/ main.py
pyright
python main.py
```

Confirm the app starts with no traceback, and check
`<data dir>/logs/toolblox.log` for anything unexpected.
