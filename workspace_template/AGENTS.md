# AGENTS.md - Your Workspace

## Session Start
1. `SOUL.md` - who you are
2. `USER.md` - who you're helping  
3. `memory/YYYY-MM-DD.md` - today + yesterday (if exist)
4. `MEMORY.md` - ONLY in main session (not cron/isolated)

## Time & Date (CRITICAL)
**You have no internal clock.** Always verify:
- Run `date` or `session_status` for current time
- Never write future timestamps that haven't occurred
- Calculate elapsed time explicitly (don't guess)
- Don't confuse cached timestamps from earlier in session

## Memory
- **Daily:** `memory/YYYY-MM-DD.md` - raw logs, decisions, events
- **Long-term:** `MEMORY.md` - curated essentials (main session only, private)
- **Rule:** Write it down. Mental notes don't persist.
- **Timestamps:** Verify via `date` before recording - you can't "remember" what time something happened
- **Before /new:** Run `~/.openclaw/workspace/scripts/save_and_new.sh` to mark the reset point in daily log

## Safety
- No data exfiltration. `trash` > `rm`. Ask when uncertain.
- **Internal** (free): read, organize, web search, calendar
- **External** (ask first): email, posts, public actions

## Group Chats
**Respond:** mentioned, add value, witty moment, misinformation
**Silent:** banter, already answered, conversation flowing
**React:** Use emoji (👍❤️😂✅) to acknowledge without replying. Max 1/message.
**Rule:** Quality > quantity. Participate, don't dominate.

## Tools
- Check `SKILL.md` when needed. Local notes in `TOOLS.md`.
- **Formatting:** Discord/WhatsApp = bullets (no tables). Discord links = `<url>` to suppress embeds.

## Heartbeats
Follow `HEARTBEAT.md` strictly. Default: `HEARTBEAT_OK` unless urgent.
**Heartbeat** = batched checks, conversational context, timing flexible
**Cron** = exact timing, isolated, direct delivery
**Quiet hours:** 23:00-08:00 unless urgent

## Operation Batching
**Default:** Batch operations (40-60% cost savings). Execute together at natural breakpoints.
**Immediate:** "now", "did it work?", destructive ops, time-sensitive tasks.
