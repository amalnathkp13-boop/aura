# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | yes |

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository
(*Security → Report a vulnerability*). Do not open a public issue for
security problems. You will get an acknowledgement within a few days.

## Deployment notes

- The dashboard (`aura-face`) listens on `0.0.0.0:8080` **without
  authentication** — it is designed for a trusted home LAN. Do not expose it
  to the internet; put it behind a VPN or reverse proxy with auth if you need
  remote access.
- The Telegram bot token and chat id live in `~/.aura/config.json` on the
  board. Keep that file private; rotate the token with `@BotFather` if it is
  ever exposed.
- Aura never records audio or images. The only stored radio data is RSSI
  (signal strength) with access-point identifiers salted and hashed per
  install.
