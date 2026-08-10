/** @jsxImportSource solid-js */
import type { TuiPlugin, TuiRouteDefinition } from "@opencode-ai/plugin/tui"
import { createResource, Show } from "solid-js"

// TUI plugin: on-demand, agent-free full session-token report.
//
// This runs entirely inside the opencode TUI process (client-side SolidJS
// rendering). It registers:
//   1. A command in the palette ("Session token stats") that navigates to
//      a full-screen route for the current session.
//   2. A route named "session-stats" whose render runs
//      `.opencode/scripts/session-stats.sh <sessionID>` as a local process
//      and displays the full report (Session Info / Summary / Agent
//      Breakdown / Model Breakdown).
//
// No LLM call, no agent, no model tokens, no server round-trip. The script
// reads the local opencode.db directly.
//
// Registered in `.opencode/tui.json` (TUI plugins are loaded from the TUI
// config, separate from the server plugin array in opencode.jsonc).

const id = "session-stats-tui"

const tui: TuiPlugin = async (api) => {
  const scriptPath = `${api.state.path.worktree}/.opencode/scripts/session-stats.sh`

  async function runStats(sessionID?: string): Promise<string> {
    if (!sessionID) return "No session selected. Open this from inside a session."
    try {
      const proc = Bun.spawn(["bash", scriptPath, sessionID])
      return await new Response(proc.stdout).text()
    } catch (err) {
      return `Failed to run ${scriptPath}: ${String(err)}`
    }
  }

  // The route replaces the whole screen; navigate back to the session that
  // opened it. Works from the route (current = plugin id + params) or from
  // the palette close command (current = session or plugin).
  function backToSession() {
    const current = api.route.current
    // Both the "session" route and any plugin route carry sessionID in
    // params (TuiRouteCurrent: { name, params?: { sessionID } }).
    const sessionID = current.name === "home" ? undefined : current.params?.sessionID
    if (typeof sessionID === "string") {
      api.route.navigate("session", { sessionID })
    }
  }

  const route: TuiRouteDefinition = {
    name: "session-stats",
    render: ({ params }) => {
      const sessionID = typeof params?.sessionID === "string" ? params.sessionID : undefined
      const [stats] = createResource(sessionID, (sid) => runStats(sid))
      return (
        <box padding={1} flexDirection="column">
          <box flexDirection="row" justifyContent="space-between" width="100%">
            <text bold>Session Token Stats{sessionID ? ` — ${sessionID}` : ""}</text>
            <text onMouseUp={backToSession} underline>
              [x] close
            </text>
          </box>
          <Show when={!stats.loading} fallback={<text>Loading…</text>}>
            <text wrapMode="word">{stats() ?? "No data"}</text>
          </Show>
          <text marginTop={1}>
            Close: click [x] above, or run palette command "Close session token stats"
          </text>
        </box>
      )
    },
  }

  api.route.register([route])

  api.command.register(() => [
    {
      title: "Session token stats",
      value: "session-stats.show",
      category: "Session",
      description: "Show full token consumption report for the current session (agent-free)",
      onSelect: () => {
        const current = api.route.current
        const sessionID = current.name === "session" ? current.params?.sessionID : undefined
        api.route.navigate("session-stats", { sessionID })
      },
    },
    {
      title: "Close session token stats",
      value: "session-stats.close",
      category: "Session",
      description: "Return to the session view",
      onSelect: () => backToSession(),
    },
  ])
}

export default { id, tui }
