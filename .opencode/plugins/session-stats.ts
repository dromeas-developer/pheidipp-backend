import type { Plugin } from "@opencode-ai/plugin"
import path from "path"

// Session Token Stats — display-only plugin.
//
// v2 fixes (2026-08-08, session ses_01c51a9b6ffeo3hDCod5KwP1Dz):
//   1. No more `client.session.prompt` injection. That call ADDED a message
//      to the session history, so the stats text was sent to the agent on
//      the next prompt — and could be picked up by the model-fallback
//      plugin's `getReplayParts` as the "last user message" to replay.
//      Stats are now displayed via `client.tui.showToast` (display-only,
//      never part of the agent's context).
//   2. No more firing on every `session.idle`. `session.idle` fires after
//      every completed turn AND right after a fallback abort. Stats now
//      require a sustained idle grace period, and are suppressed in the
//      window after a retry/error (fallback in progress).

const IDLE_GRACE_MS = 60_000 // session must stay idle this long before showing
const FALLBACK_SUPPRESS_MS = 60_000 // suppress stats after a retry/error
const MIN_REPEAT_MS = 10_000 // minimum time between shows for the same session

const SessionStatsPlugin: Plugin = async ({ client, $, worktree }) => {
  const scriptPath = path.join(worktree, ".opencode/scripts/session-stats.sh")
  const lastShownAt = new Map<string, number>()
  const suppressUntil = new Map<string, number>()
  const idleTimers = new Map<string, ReturnType<typeof setTimeout>>()

  await client.app.log({
    body: {
      service: "session-stats",
      level: "info",
      message: "Plugin loaded",
    },
  })

  const clearIdleTimer = (sessionID: string) => {
    const timer = idleTimers.get(sessionID)
    if (timer) {
      clearTimeout(timer)
      idleTimers.delete(sessionID)
    }
  }

  const showStats = async (sessionID: string) => {
    idleTimers.delete(sessionID)
    const now = Date.now()
    if (now < (suppressUntil.get(sessionID) ?? 0)) return
    const last = lastShownAt.get(sessionID) ?? 0
    if (now - last < MIN_REPEAT_MS) return
    lastShownAt.set(sessionID, now)

    try {
      const result = await $`bash ${scriptPath} ${sessionID} --summary`.text()
      const summary = result.trim()
      if (!summary) return

      // Display-only: toast. Never inject into the session conversation —
      // an injected message becomes part of the agent's context and can be
      // replayed by the model-fallback plugin.
      await client.tui
        .showToast({
          body: {
            title: "Session Token Stats",
            message: summary,
            variant: "info",
            duration: 8000,
          },
        })
        .catch(() => {})

      await client.app.log({
        body: {
          service: "session-stats",
          level: "info",
          message: `Showed stats for session ${sessionID}`,
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
      const props = event.properties as Record<string, any>
      // session.status/idle/error carry sessionID directly; session.deleted
      // carries info.id (Session object).
      const sessionID = props?.sessionID ?? props?.info?.id ?? props?.info?.sessionID
      if (!sessionID) return

      switch (event.type) {
        case "session.idle": {
          // A turn (or an abort) finished. Arm the grace timer — stats only
          // show if the session stays idle (user stopped interacting). Any
          // new activity cancels it, so mid-session turns never trigger.
          clearIdleTimer(sessionID)
          idleTimers.set(
            sessionID,
            setTimeout(() => {
              void showStats(sessionID)
            }, IDLE_GRACE_MS),
          )
          break
        }
        case "session.status": {
          const statusType = String(props?.status?.type ?? "")
          if (statusType === "busy") {
            // New turn started — cancel any pending stats display.
            clearIdleTimer(sessionID)
          } else if (statusType === "retry") {
            // Fallback in progress — cancel pending stats and suppress for
            // the fallback window.
            clearIdleTimer(sessionID)
            suppressUntil.set(sessionID, Date.now() + FALLBACK_SUPPRESS_MS)
          }
          break
        }
        case "session.error": {
          clearIdleTimer(sessionID)
          suppressUntil.set(sessionID, Date.now() + FALLBACK_SUPPRESS_MS)
          break
        }
        case "session.deleted": {
          clearIdleTimer(sessionID)
          suppressUntil.delete(sessionID)
          break
        }
      }
    },
  }
}

export default SessionStatsPlugin
