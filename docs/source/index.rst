Multitool
=========

Documentation generated from the docstrings in the `multitool` package.

Guide
-----

The sections below group modules by what they do. Start here. The full,
alphabetical module tree is further down for reference.

Settings and app state
~~~~~~~~~~~~~~~~~~~~~~

Where user preferences and per-page state live.

* :doc:`api/multitool.state`: read and write app settings for the current page.
* :doc:`api/multitool.data.settings`: persistence for app settings, as a plain JSON dict.

Accounts
~~~~~~~~

Storing and managing the tracked Roblox account list.

* :doc:`api/multitool.data.accounts`: persistence for the tracked Roblox account list.
* :doc:`api/multitool.data.crypto`: per-platform protection for sensitive values stored in accounts.json.
* :doc:`api/multitool.ui.accounts`: the Accounts screen. List, add, remove, join, and reorder tracked accounts.

Roblox login and join
~~~~~~~~~~~~~~~~~~~~~~

Logging into Roblox and launching into a place.

* :doc:`api/multitool.roblox.login`: standalone Roblox login window, run as a subprocess.
* :doc:`api/multitool.roblox.join`: build a launch URL for joining a Roblox place with a saved account.
* :doc:`api/multitool.roblox.multi_instance`: Windows-only bypass for Roblox's singleton-instance check.
* :doc:`api/multitool.ui.join_action`: shared join flow, used by both the Accounts screen and the Dashboard.

Widget plugin system
~~~~~~~~~~~~~~~~~~~~~

How third-party widgets are discovered, installed, and run.

* :doc:`api/multitool.widgets.api`: the contract a widget must implement, and shared helpers for it.
* :doc:`api/multitool.widgets.loader`: discover and import installed widgets from WIDGETS_DIR.
* :doc:`api/multitool.widgets.catalog`: fetch and cache the Catalogue, the list of widgets available to install.
* :doc:`api/multitool.widgets.installer`: download, verify, and install a widget from the Catalogue.
* :doc:`api/multitool.widgets.process`: helper for widgets whose actual logic runs as an external process.
* :doc:`api/multitool.ui.widgets`: the Widgets screen. The Catalogue banner and the grid of installed widgets.

App shell and other screens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The rest of the UI and shared app infrastructure.

* :doc:`api/multitool.app`: Multitool's entrypoint. Window setup and the top-level view router.
* :doc:`api/multitool.ui.layout`: the shared page shell. Nav rail plus content area, used by every view.
* :doc:`api/multitool.ui.dashboard`: the Dashboard. A Roblox-style continue card, an account row, and stats.
* :doc:`api/multitool.ui.settings`: the Settings screen.
* :doc:`api/multitool.ui.style`: shared visual constants and theme-aware helpers.
* :doc:`api/multitool.ui.toast`: snackbar-based toast notifications, shared across all views.
* :doc:`api/multitool.theme`: parse and apply a user-supplied theme.
* :doc:`api/multitool.config`: per-OS data directory and shared URLs.
* :doc:`api/multitool.logs`: file-based logging shared by every part of the app.

Full API reference
-------------------

Every module, alphabetically, if you already know what you're looking for.

.. toctree::
   :maxdepth: 2

   api/modules
