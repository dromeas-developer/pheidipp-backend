---
description: Show token consumption breakdown for the current session
---
Run the session stats script to display token consumption. Execute:

```
bash .opencode/scripts/session-stats.sh $OPENCODE_SESSION_ID
```

If the session ID environment variable is not set, get it from the opencode.db by running:

```
sqlite3 ~/.local/share/opencode/opencode.db "SELECT id FROM session ORDER BY time_updated DESC LIMIT 1;"
```

Then use that ID with the script.
