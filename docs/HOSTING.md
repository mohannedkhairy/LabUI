# Hosting LabUI

LabUI runs locally or as user services on a Linux host. The default backend is
LM Studio; `./start-ollama.sh` provides the optional Ollama launcher.

## Configure the host

Run `./setup.sh` from the repository root. Copy the portable settings example:

```bash
mkdir -p ~/.config/labui
cp deploy/labui.env.example ~/.config/labui/labui.env
chmod 600 ~/.config/labui/labui.env
```

Set `LM_STUDIO_URL` to your local or private-network server, and optionally set
`LM_STUDIO_MODEL`. Set `LABUI_DATA_DIR` explicitly when attaching an existing
library. Keep that directory and its PDFs, attachments, SQLite databases,
writing projects and vector indexes together in backups. New installations use
`.data/labui`; an existing `.data/lm-studio-test` directory is retained for
compatibility and may contain real user data. Do not delete it as a test cache.

Secrets belong in private configuration or the optional
`~/.config/local-model/token`, never in the checkout. See
[model configuration](LM_STUDIO_TESTING.md) and the example environment file.

## Install user services

```bash
submission_strategy/.venv/bin/python tools/install_user_services.py
systemctl --user start labui.service
```

The installer creates app, model-adapter, and private-access timer units. The
app and adapter restart independently. Stopping the model server leaves the
library available. The app holds a sleep inhibitor while serving; display
locking remains available. For startup before login and survival after logout,
a system administrator must enable user lingering on the host.

The default local address is http://127.0.0.1:8770. Keep the listeners bound to
loopback when using the private-access proxy.

## Connect a phone or tablet

Install and sign in to Tailscale on the host and the client device using the
host owner's account. Enable the private-access timer when ready:

```bash
systemctl --user start labui-private-access.timer
journalctl --user -u labui-private-access.service -n 20
tailscale serve status
```

Complete any HTTPS/Serve authorization requested by Tailscale, then open the
private address displayed by `tailscale serve status` or stored in
`~/.config/labui/access.json`. The publisher retries after sign-in. The owner
policy checks the verified proxy identity and rejects other network members.
Do not expose the app listener directly or use a public Funnel for this setup.

## Service controls

```bash
systemctl --user status labui labui-model
systemctl --user restart labui
journalctl --user -u labui -n 40
journalctl --user -u labui-model -n 20
```

To pause hosting, stop `labui-private-access.timer`, `labui.service`, and
`labui-model.service`. Restart `labui.service` and the timer to resume. The host
and any remote model server need power and connectivity for AI answers.

Embedding model changes require a validated migration, not only a dimension
setting change. See [retrieval and migration](GPU_RETRIEVAL.md). Installation
and service commands in this document are instructions; cloning the branch does
not install services or change a running library.
