# NAS Deployment with Tailscale (Private Access)

Yes, this project can run on a NAS and be reachable only by you via Tailscale.

## Architecture

- Solver API runs in Docker on your NAS (`127.0.0.1:18000` on NAS host)
- Tailscale on NAS publishes that local port to your tailnet
- Extension points to your private tailnet URL

No public reverse proxy is required.

## 1) Deploy API on NAS

Copy this repository to your NAS, then:

```bash
cd /path/to/linkedin-puzzle-solvers/deploy/nas
cp .env.example .env
docker compose up -d --build
```

Check status:

```bash
docker compose ps
curl -s http://127.0.0.1:18000/health
```

Expected response:

```json
{"status":"ok"}
```

## 2) Publish privately with Tailscale

Install Tailscale on the NAS (package/app or CLI), then log in with your account.

Publish HTTPS service to tailnet:

```bash
tailscale serve --bg https / http://127.0.0.1:18000
tailscale serve status
```

Your extension API URL will be:

`https://<nas-name>.<your-tailnet>.ts.net`

If your Tailscale version uses legacy flags, use:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:18000
```

## 3) Restrict access to only you

If your tailnet has only your account, that is already private.

For shared tailnets, add ACL policy so only your user can access the NAS tag.

Example ACL snippet (Tailscale admin console policy):

```json
{
  "tagOwners": {
    "tag:solver-nas": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["user:you@example.com"],
      "dst": ["tag:solver-nas:443"]
    }
  ]
}
```

Then advertise tag on NAS (CLI install):

```bash
tailscale up --advertise-tags=tag:solver-nas
```

## 4) Configure extension

In extension popup:

- Set `API URL` to your Tailscale URL
- Keep the rest unchanged

You can now solve from any device that is signed into your tailnet.

## 5) Operations

Update API after pulling repo changes:

```bash
cd /path/to/linkedin-puzzle-solvers/deploy/nas
docker compose up -d --build
```

Stop/start:

```bash
docker compose stop
docker compose start
```

Logs:

```bash
docker compose logs -f solver-api
```

## Troubleshooting

- `captureVisibleTab` permission errors in extension: reload extension after manifest changes
- `connection refused`: check API health on NAS local port first
- Tailscale URL not reachable: verify `tailscale serve status` and NAS is connected in `tailscale status`
