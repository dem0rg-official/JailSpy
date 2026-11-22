# JailSpy

**Server Tracker for Your Grind**

JailSpy is a terminal (TUI) tracker for active Roblox Jailbreak robberies. It reads a live feed from [Jailbreak Changelogs](https://jailbreakchangelogs.com/robberies) or [MuffinHook](https://www.muffinhook.site), shows the servers in a table, and can join them through Sober or `xdg-open`. An optional auto-join loop keeps relaunching the client on fresh servers.

Current version: **0.2.3** (`./run.sh --version`). Interface languages: English and Russian, changed in the settings menu (`S`).

## Requirements

- Linux with Python 3.10+
- Flatpak `org.vinegarhq.Sober` for auto-join (manual join can fall back to `xdg-open`)
- An account on the source you choose: jailbreakchangelogs.com, or muffinhook.site (Discord sign-in)

## Quick start

```bash
git clone https://github.com/dem0rg-official/JailSpy.git
cd JailSpy
chmod +x run.sh
./run.sh
```

On first run `run.sh` creates `.venv`, installs Playwright and Chromium, and starts the app. A full-screen setup wizard (arrows or digits to pick, `Enter` to confirm, `Esc` to go back) then asks for:

1. interface language (EN / RU);
2. data source: Jailbreak Changelogs or MuffinHook;
3. your token (see below);
4. the dashboard starts.

Re-run the wizard with `./run.sh --setup`; your pity settings are kept. 

## How it works

With **Jailbreak Changelogs**:

1. JailSpy opens the robberies page in headless Chromium (Playwright) using your session and listens to the page's WebSocket. It reads the `recent_robberies` messages.
2. Each message is normalised into a table row: status, opening time (`hh:mm:ss`), full server ID, total / criminal / cop counts, and a "full" flag.
3. If no frame arrives for a while, the page is reloaded automatically.
4. Joining builds the deep link `roblox://experiences/start?placeId=606849621&gameInstanceId=<job-id>`. Auto-join starts it with `flatpak run org.vinegarhq.Sober <uri>`.

The MuffinHook source works differently, see [Data sources](#data-sources). In both cases a server counts as full when `criminals >= min(18, 4 * (cops + 1))`. If the feed has no team counts, the flag is shown as unknown/No.

## Data sources

- **Jailbreak Changelogs**: WebSocket feed read through headless Chromium.
- **MuffinHook** (muffinhook.site): polls `https://api.muffinhook.site/export/servers` every 5 seconds over plain HTTPS, with no browser. Each open or in-progress robbery on a server becomes one table row, with the same columns and auto-join logic as the first source. This feed has no opening time, so the Time column shows when the server last reported. The real Roblox job ID is requested only when you join.

Choose the source in the setup wizard (`./run.sh --setup`) or later in the settings menu (`S`).

## Authentication (token)

JailSpy never reads your browser profile. You paste the token yourself:

1. Log in at jailbreakchangelogs.com in your browser.
2. Open DevTools (F12) → Application / Storage → Cookies → `jailbreakchangelogs.com`.
3. Copy the value of the `jbcl_token` cookie.
4. Paste it into JailSpy when asked. Input is hidden.

For **MuffinHook**: sign in with Discord at muffinhook.site, open DevTools → Application/Storage → Local Storage → `https://www.muffinhook.site`, and copy the value of `muffin_auth_token`. It is stored in `~/.local/share/jailspy/muffinhook-token` (mode `600`). The token is sent only to `api.muffinhook.site`.

For Jailbreak Changelogs, the token is stored as a cookie in `~/.local/share/jailspy/storage-state.json` (file mode `600`). Settings are stored in `~/.config/jailspy/config.json`. Both live outside the project folder. Never publish or share them; anyone with the token can act as your account. To replace the token, use `S` → Change token, or run `./run.sh --setup`.

## Auto-join

```text
pick a robbery → refresh the list → choose the newest matching server
→ close a running Roblox client → launch via Sober
→ wait for the process to exit → wait → repeat
```

- The server list is refreshed right before every launch.
- **The server from the previous launch is skipped**, so you are not sent to the same server twice in a row. This applies whether the client closed early or late. Selecting a different robbery with `A` resets it. If no other server is available, the loop waits and retries every 5 seconds.
- Default wait between launches: 5 seconds. With Pity cooldown on: the configured delay (default 210 s), which avoids resetting pity when the same store is robbed again within five minutes.
- If the client exits less than 60 seconds after launch (crash or failed join), it is relaunched after 5 seconds without the pity delay. This is built in and not configurable.
- The AUTO line shows a countdown to the next launch.
- Filters work independently: skip full servers, open only, max players.

## Hotkeys

Hotkeys are shown in `[ ]` in the UI and also work on the Russian keyboard layout.

| Key | Action |
| --- | --- |
| `↑` / `↓`, `J` / `K` | Select a robbery |
| `Enter` | Join the selected server once |
| `A` | Toggle auto-join for the selected robbery |
| `/` | Text filter by robbery name/type |
| `C` | Clear the text filter |
| `F` | Auto-join: skip full servers |
| `O` | Auto-join: only open robberies |
| `N` | Auto-join: max player count (asks for the limit; press again to turn off) |
| `P` | Toggle Pity cooldown |
| `S` | Open the settings menu: language, data source, pity delay, change token |
| `R` | Reconnect the data source |
| `Q` / `Esc` | Quit |

Enabled toggles are highlighted in green.

## Settings menu

`S` opens a full-screen menu in the same style as the dashboard (arrows or digits to pick, `Enter` to confirm, `Esc` to go back). It changes the language, the data source, the pity delay (seconds), and the token. Language and delay apply immediately. Changing the source or token restarts the data connection automatically. There are no separate hotkeys for language and delay.

## Status panel

Shows whether the Roblox client is running, launches this session, time of the last launch, Pity cooldown state, and the current auto-join phase. Counters live in memory and reset when you quit.

## Logs

`~/.local/share/jailspy/jailspy.log`. Check the end of this file if the app exits unexpectedly.

## Changelog

**0.2.3**
- Second data source: MuffinHook.
- Full-screen TUI setup wizard (`--setup`) and settings menu (`S`) for language, source, pity delay, and token. The `L` and `D` hotkeys are removed.
- Table: Region column removed, full server ID always visible.
- English mode no longer shows Russian text.

**0.2.2**
- First release. Auto-join skips the server from the previous launch.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Notes

- JailSpy uses only your own session and does not bypass authorization. The site may rate-limit WebSocket connections.
- Closing the running Roblox client is required to switch servers. Don't run unrelated Roblox sessions while auto-join is on.
- The feed schema is normalised from several possible field names and may need updates if the site changes its API.
