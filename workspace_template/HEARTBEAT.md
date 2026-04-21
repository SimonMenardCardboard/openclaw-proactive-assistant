# HEARTBEAT.md

## System Health (once per day, rotate 4 AM / 4 PM)
- Check `openclaw status` only if >12h since last check
- If Telegram errored, restart gateway silently
- Only alert Simon if restart fails

## Weekly Check (Sundays only)
- **OpenClaw iOS TestFlight:** Check docs.openclaw.ai/platforms/ios for public release
- Alert if status changed from "internal preview"

## Notes
- Cron jobs handle: calendar (4 AM), email scan (9 AM/2 PM/7 PM), recovery (7 PM)
- Heartbeat = catch-all for edge cases, not routine monitoring
- Default: HEARTBEAT_OK unless something urgent
