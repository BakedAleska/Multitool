# Rogue Lineage

Tracks Rogue Lineage characters: username, class, race, freeform notes, and a
repeatable list of items, each with an optional quantity.

A character's username is always typed in by hand. If it's similar to one of
Multitool's own tracked accounts, press Tab while the field is focused to
autofill the full match. Once it's an exact match, the character starts
syncing with that account automatically: its username and avatar follow the
account from then on, and it falls back to standalone again if the account
is later removed from Multitool.

Class, race, and item choices come from `reference.json` in this folder, a
starting list assembled from the Rogue Lineage Fandom wiki, not a full
scrape. It's a plain, hand-editable JSON file - extend it any time by adding
entries to its `classes`, `races`, or `items` arrays. Every dropdown built
from that list also offers "Other...", so an incomplete list never blocks
entering real data.

## Installing

Running Multitool from source (`python main.py` in this repo) picks this
widget up automatically - no install step needed. To use it in a packaged
build, copy this `rogue_lineage` folder into the widgets folder shown in
Settings -> Widgets.

## Data

Characters are stored at `<DATA_DIR>/rogue_lineage.json`, independent of
`accounts.json` - deleting or editing this file only affects the Rogue
Lineage roster, not tracked accounts.
