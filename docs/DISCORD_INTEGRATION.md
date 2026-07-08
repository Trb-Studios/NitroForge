# Discord Integration (crash / bug / feedback reports)

Nitro Forge delivers reports through **Discord webhooks** - no bot to host, no
account access required by the app, nothing to install. You create a webhook
in your own server and paste one URL into the app. That's the whole setup.

> Privacy: nothing is ever sent unless a webhook/endpoint is configured AND
> sending is enabled (auto-send toggle, the crash screen's send button, or the
> feedback form). Reports contain the app version, OS/hardware summary, stack
> trace, optional user message and (optionally) recent app log lines.

## 1. Create a reports channel + webhook in your server

In your Discord server (e.g. **Nitro Forge LLC.**):

1. Create a private channel for reports, e.g. `#nitro-forge-reports`
   (Server Settings → Roles to keep it admin-only, if you like). You can also
   make separate channels + webhooks per type, e.g. `#crashes`, `#feedback`.
2. **Server Settings → Integrations → Webhooks → New Webhook**
3. Name it (e.g. `Nitro Forge Reporter`), pick the channel, **Copy Webhook URL**.

The URL looks like:
`https://discord.com/api/webhooks/1234567890/AbCdEfG...`

Treat it like a password - anyone with the URL can post to that channel.

## 2. Paste it into the app

**Settings → Crash & bug reporting → Discord webhook URL** → Save endpoints →
**Send test report**. A baby-blue embed should appear in your channel within a
second; the badges in the app show which sinks succeeded.

## 3. What arrives

Each report is a rich embed:

* **Color-coded by type** - red = crash / UI crash, amber = bug report,
  baby blue = feedback / test
* **Fields** - app version, OS, hardware summary (thread count + RAM),
  user feedback, optional contact
* **Body** - stack trace / detail in a code block, truncated to Discord limits
* **Timestamp + footer**

Delivery is rate-limited in the app (min 30 s between automatic sends) so a
crash loop can't flood your channel.

## 4. Optional: website endpoint

The same reports can also POST as JSON to your own API - set
**Website API endpoint** in Settings. Payload shape:

```json
{
  "kind": "crash | frontend-crash | bug | feedback",
  "title": "...",
  "detail": "stack trace / description",
  "feedback": "user-typed message",
  "contact": "optional",
  "ts": 1780000000.0,
  "system": { "app": "Nitro Forge", "version": "2.0.0", "os": "...", "cpu_count": 16, "ram_gb": 32.0 },
  "log_tail": ["12:00:01 INFO  ...", "..."]
}
```

Any endpoint returning HTTP 2xx counts as delivered. A tiny serverless
function (Cloudflare Workers / Vercel) that stores these in a DB - or simply
re-forwards to Discord - is plenty.

## 5. Config reference (Settings → also in %LOCALAPPDATA%\NitroForge\settings.json)

| Key | Default | Meaning |
|---|---|---|
| `report_enabled` | `true` | write local diagnostic JSON files |
| `report_auto_send` | `false` | send crashes without asking |
| `report_discord_webhook` | `""` | webhook URL (empty = disabled) |
| `report_site_url` | `""` | website endpoint (empty = disabled) |
| `report_include_logs` | `true` | attach recent log lines |
