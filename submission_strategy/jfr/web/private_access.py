"""Restrict private-network access to the account that owns this LabUI host.

Tailscale Serve sets identity headers and removes client-supplied copies. Keep
the app bound to loopback; direct local requests remain available for the owner
and health probes. Other tailnet members do not inherit access to the library.
"""
import ipaddress
import json
from pathlib import Path

from starlette.responses import JSONResponse


class PrivateAccessMiddleware:
    def __init__(self, app, policy_path):
        self.app = app
        self.policy_path = Path(policy_path)

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope.get('headers', [])}
        login = headers.get(b'tailscale-user-login', b'').decode('utf-8', errors='replace').casefold()
        allowed = False
        if login:
            try:
                owner = json.loads(self.policy_path.read_text()).get('owner_login', '').casefold()
                allowed = bool(owner) and login == owner
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        elif b'x-forwarded-for' not in headers:
            try:
                allowed = ipaddress.ip_address(scope['client'][0]).is_loopback
            except (ValueError, TypeError, KeyError):
                pass
        if allowed:
            return await self.app(scope, receive, send)
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        response = JSONResponse({'detail': 'Open LabUI through Tailscale using the account that owns this PC.'}, status_code=403)
        await response(scope, receive, send)
