#!/usr/bin/env bash
set -euo pipefail

SESSION_ID="${1:-}"
DB="${OPENCODE_DB:-$HOME/.local/share/opencode/opencode.db}"

if [ -z "$SESSION_ID" ]; then
  echo "Error: No session ID provided" >&2
  echo "Usage: $0 <session-id>" >&2
  exit 1
fi

if [ ! -f "$DB" ]; then
  echo "Error: Database not found at $DB" >&2
  exit 1
fi

EXISTS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM session WHERE id = '$SESSION_ID';")
if [ "$EXISTS" -eq 0 ]; then
  echo "Error: Session $SESSION_ID not found" >&2
  exit 1
fi

TITLE=$(sqlite3 "$DB" "SELECT title FROM session WHERE id = '$SESSION_ID';")
CHILD_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM session WHERE parent_id = '$SESSION_ID';")

echo "=== Session Info ==="
echo "ID:     $SESSION_ID"
echo "Title:  $TITLE"
if [ "$CHILD_COUNT" -gt 0 ]; then
  echo "Subagents: $CHILD_COUNT child sessions"
fi

SESSION_IDS=$(sqlite3 "$DB" "
WITH RECURSIVE children(id) AS (
  SELECT id FROM session WHERE id = '$SESSION_ID'
  UNION ALL
  SELECT s.id FROM session s JOIN children c ON s.parent_id = c.id
)
SELECT '\"' || id || '\"' FROM children;
" | paste -sd, -)

echo "=== Session Summary ==="
sqlite3 -header -column "$DB" "
SELECT
  (SELECT COUNT(*) FROM message WHERE session_id IN ($SESSION_IDS)) AS 'Messages',
  SUM(tokens_input) AS 'Input',
  SUM(tokens_output) AS 'Output',
  SUM(tokens_reasoning) AS 'Reasoning',
  SUM(tokens_cache_read) AS 'Cache Read',
  SUM(tokens_cache_write) AS 'Cache Write',
  CASE WHEN (SUM(tokens_cache_read) + SUM(tokens_input)) > 0
    THEN printf('%.1f%%', CAST(SUM(tokens_cache_read) AS REAL) / (SUM(tokens_cache_read) + SUM(tokens_input)) * 100)
    ELSE '0.0%'
  END AS 'Cache Hit %',
  printf('%.6f', SUM(cost)) AS 'Cost'
FROM session WHERE id IN ($SESSION_IDS);
"

echo ""
echo "=== Agent Breakdown ==="
sqlite3 -header -column "$DB" "
WITH agent_models AS (
  SELECT
    json_extract(m.data, '$.agent') AS agent,
    json_extract(m.data, '$.modelID') AS model
  FROM message m
  WHERE m.session_id IN ($SESSION_IDS)
    AND json_extract(m.data, '$.role') = 'assistant'
  GROUP BY agent, model
),
agent_model_counts AS (
  SELECT agent, COUNT(*) AS model_count
  FROM agent_models
  GROUP BY agent
)
SELECT
  COALESCE(json_extract(m.data, '$.agent'), 'unknown') AS 'Agent',
  CASE
    WHEN mc.model_count = 1
    THEN (SELECT model FROM agent_models WHERE agent = json_extract(m.data, '$.agent') LIMIT 1)
    ELSE mc.model_count || ' models'
  END AS 'Model',
  COUNT(*) AS 'Msgs',
  SUM(json_extract(m.data, '$.tokens.input')) AS 'Input',
  SUM(json_extract(m.data, '$.tokens.output')) AS 'Output',
  SUM(json_extract(m.data, '$.tokens.reasoning')) AS 'Reasoning',
  SUM(json_extract(m.data, '$.tokens.cache.read')) AS 'Cache Read',
  CASE WHEN (SUM(json_extract(m.data, '$.tokens.cache.read')) + SUM(json_extract(m.data, '$.tokens.input'))) > 0
    THEN printf('%.1f%%', CAST(SUM(json_extract(m.data, '$.tokens.cache.read')) AS REAL) / (SUM(json_extract(m.data, '$.tokens.cache.read')) + SUM(json_extract(m.data, '$.tokens.input'))) * 100)
    ELSE '0.0%'
  END AS 'Cache Hit %'
FROM message m
JOIN agent_model_counts mc ON mc.agent = json_extract(m.data, '$.agent')
WHERE m.session_id IN ($SESSION_IDS)
  AND json_extract(m.data, '$.role') = 'assistant'
GROUP BY json_extract(m.data, '$.agent')
ORDER BY SUM(json_extract(m.data, '$.tokens.input')) DESC;
"

MULTI_MODEL_COUNT=$(sqlite3 "$DB" "
SELECT COUNT(DISTINCT json_extract(data, '$.agent'))
FROM message
WHERE session_id IN ($SESSION_IDS)
  AND json_extract(data, '$.role') = 'assistant'
  AND json_extract(data, '$.agent') IN (
    SELECT json_extract(data, '$.agent')
    FROM message
    WHERE session_id IN ($SESSION_IDS)
      AND json_extract(data, '$.role') = 'assistant'
    GROUP BY json_extract(data, '$.agent')
    HAVING COUNT(DISTINCT json_extract(data, '$.modelID')) > 1
  );
")

if [ "$MULTI_MODEL_COUNT" -gt 0 ]; then
  echo ""
  echo "=== Model Breakdown (multi-model agents only) ==="
  sqlite3 -header -column "$DB" "
  SELECT
    COALESCE(json_extract(m.data, '$.agent'), 'unknown') AS 'Agent',
    COALESCE(json_extract(m.data, '$.modelID'), 'unknown') AS 'Model',
    COALESCE(json_extract(m.data, '$.providerID'), 'unknown') AS 'Provider',
    COUNT(*) AS 'Msgs',
    SUM(json_extract(m.data, '$.tokens.input')) AS 'Input',
    SUM(json_extract(m.data, '$.tokens.output')) AS 'Output',
    SUM(json_extract(m.data, '$.tokens.reasoning')) AS 'Reasoning',
    SUM(json_extract(m.data, '$.tokens.cache.read')) AS 'Cache Read',
    CASE WHEN (SUM(json_extract(m.data, '$.tokens.cache.read')) + SUM(json_extract(m.data, '$.tokens.input'))) > 0
      THEN printf('%.1f%%', CAST(SUM(json_extract(m.data, '$.tokens.cache.read')) AS REAL) / (SUM(json_extract(m.data, '$.tokens.cache.read')) + SUM(json_extract(m.data, '$.tokens.input'))) * 100)
      ELSE '0.0%'
    END AS 'Cache Hit %'
  FROM message m
  WHERE m.session_id IN ($SESSION_IDS)
    AND json_extract(m.data, '$.role') = 'assistant'
    AND json_extract(m.data, '$.agent') IN (
      SELECT json_extract(data, '$.agent')
      FROM message
      WHERE session_id IN ($SESSION_IDS)
        AND json_extract(data, '$.role') = 'assistant'
      GROUP BY json_extract(data, '$.agent')
      HAVING COUNT(DISTINCT json_extract(data, '$.modelID')) > 1
    )
  GROUP BY json_extract(m.data, '$.agent'), json_extract(m.data, '$.modelID'), json_extract(m.data, '$.providerID')
  ORDER BY json_extract(m.data, '$.agent'), SUM(json_extract(m.data, '$.tokens.input')) DESC;
  "
fi
