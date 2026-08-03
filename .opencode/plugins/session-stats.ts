import type { Plugin } from "@opencode-ai/plugin"
import path from "path"

const SessionStatsPlugin: Plugin = async ({ client, $, worktree }) => {
  const scriptPath = path.join(worktree, ".opencode/scripts/session-stats.sh")
  let lastShownId: string | null = null
  let lastShownAt: number = 0

  await client.app.log({
    body: {
      service: "session-stats",
      level: "info",
      message: "Plugin loaded",
    },
  })

  const runStats = async (sessionID: string) => {
    const now = Date.now()
    if (sessionID === lastShownId && now - lastShownAt < 10_000) return
    lastShownId = sessionID
    lastShownAt = now

    try {
      const result = await $`bash ${scriptPath} ${sessionID}`.text()
      const stats = result.trim()
      if (!stats) return

      await client.session.prompt({
        path: { id: sessionID },
        body: {
          noReply: true,
          parts: [{ type: "text", text: `\n## Session Token Stats\n${stats}` }],
        },
      })

      await client.app.log({
        body: {
          service: "session-stats",
          level: "info",
          message: `Injected stats for session ${sessionID}`,
        },
      })
    } catch (err) {
      await client.app.log({
        body: {
          service: "session-stats",
          level: "error",
          message: `Failed: ${err}`,
        },
      })
    }
  }

  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        const data = event.properties as { sessionID?: string }
        if (data.sessionID) await runStats(data.sessionID)
      }
    },
  }
}

export default SessionStatsPlugin
