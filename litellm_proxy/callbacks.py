import json
import re
from litellm.integrations.custom_logger import CustomLogger

# Models that fail or produce garbage when reasoning/thinking content
# is left in the message history. All others are left untouched so that
# provider-side prefix caching (e.g. Mistral) stays stable.
_REASONING_SENSITIVE_MODELS = (
    "mistral-medium",
    "kimi-k2",
    "deepseek-r",
    "o1",
    "o3",
    "qwq",
    "glm-4.7",
)

def _is_reasoning_sensitive(model: str) -> bool:
    lower = model.lower()
    return any(pattern in lower for pattern in _REASONING_SENSITIVE_MODELS)


class MessageHistoryCleaner(CustomLogger):

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        model = data.get("model", "")
        messages = data.get("messages", [])
        strip_thinking = _is_reasoning_sensitive(model)

        for msg in messages:
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue

            if strip_thinking:
                # Remove top-level reasoning fields injected by some providers
                msg.pop("reasoning_content", None)
                msg.pop("thinking", None)

                # Remove Anthropic-style thinking blocks from content arrays
                if isinstance(msg.get("content"), list):
                    msg["content"] = [
                        block for block in msg["content"]
                        if not (
                            isinstance(block, dict) and
                            block.get("type") in ("thinking", "redacted_thinking")
                        )
                    ]
                    if not msg["content"]:
                        msg["content"] = ""

            # Always normalise tool-call argument serialisation so the prefix
            # is byte-stable across turns (fixes Mistral cache misses).
            for tc in msg.get("tool_calls", []) or []:
                self._fix_tool_call(tc)

        data["messages"] = messages
        return data

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._log_usage(kwargs, response_obj)

    async def async_log_stream_event(self, kwargs, response_obj, start_time, end_time):
        usage = getattr(response_obj, "usage", None)
        if usage and getattr(usage, "total_tokens", 0) > 0:
            self._log_usage(kwargs, response_obj)

    def _log_usage(self, kwargs, response_obj):
        try:
            usage = response_obj.usage
            if not usage:
                return

            model = kwargs.get("model", "unknown")

            cached = getattr(usage, "prompt_tokens_details", None)
            cached_tokens = getattr(cached, "cached_tokens", 0) if cached else 0
            completion = getattr(usage, "completion_tokens_details", None)
            reasoning_tokens = getattr(completion, "reasoning_tokens", 0) if completion else 0

            print(
                f"[PHEIDIPP] ✓ {model} | "
                f"prompt: {usage.prompt_tokens} ({cached_tokens} cached) | "
                f"completion: {usage.completion_tokens} | "
                f"reasoning: {reasoning_tokens} | "
                f"total: {usage.total_tokens}",
                flush=True,
            )

            if cached_tokens > 0 and usage.prompt_tokens > 0:
                pct = round(cached_tokens / usage.prompt_tokens * 100)
                print(f"[PHEIDIPP] 💾 Cache hit: {pct}% reused", flush=True)

        except Exception as e:
            print(f"[PHEIDIPP] log error: {e}", flush=True)

    def _strip_reasoning(self, text: str) -> str:
        """
        Remove common reasoning patterns while preserving final answer.
        This is heuristic but highly effective.
        """
        if not text:
            return text

        patterns = [
            r"(final answer\s*:)",
            r"(answer\s*:)",
            r"(conclusion\s*:)",
        ]

        lower = text.lower()

        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                idx = match.start()
                return text[idx:].split(":", 1)[-1].strip()

        if "let's think step by step" in lower:
            parts = text.split("\n")
            return parts[-1].strip()

        return text

    def _fix_tool_call(self, tc):
        """
        Unwrap double-encoded JSON strings in tool arguments (Llama quirk) and
        re-serialise with compact separators so the byte representation is
        stable across turns. Stable bytes = stable prefix = cache hits.
        """
        try:
            func = (
                tc.get("function")
                if isinstance(tc, dict)
                else getattr(tc, "function", None)
            )
            if not func:
                return

            arguments = (
                func.get("arguments")
                if isinstance(func, dict)
                else getattr(func, "arguments", None)
            )
            if not arguments:
                return

            args = json.loads(arguments)
            changed = False

            for key, val in args.items():
                if isinstance(val, str):
                    try:
                        parsed = json.loads(val)
                        if isinstance(parsed, (list, dict)):
                            args[key] = parsed
                            changed = True
                    except Exception:
                        pass

            # Always re-serialise with compact, deterministic separators.
            # This prevents json.dumps default whitespace from producing
            # different bytes on different runs, which would break prefix cache.
            new_args = json.dumps(args, separators=(",", ":"))
            if new_args != arguments or changed:
                if isinstance(func, dict):
                    func["arguments"] = new_args
                else:
                    func.arguments = new_args

        except Exception:
            pass

proxy_handler_instance = MessageHistoryCleaner()