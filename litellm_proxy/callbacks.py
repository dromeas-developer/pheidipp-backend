import json
import re
from litellm.integrations.custom_logger import CustomLogger

# Models that fail or produce garbage when reasoning/thinking content
# is left in the message history. All others are left untouched so that
# provider-side prefix caching stays stable.
_REASONING_SENSITIVE_MODELS = (
    "mistral-medium",
    "kimi-k2",
    "deepseek-r",
    "o1",
    "o3",
    "qwq",
    "glm-4.7",
)

_EMPTY_CONTENT_SENSITIVE_MODELS = (
    "cohere/",
    "command-",
)

def _is_empty_content_sensitive(model: str) -> bool:
    lower = model.lower()
    return any(pattern in lower for pattern in _EMPTY_CONTENT_SENSITIVE_MODELS)

def _is_reasoning_sensitive(model: str) -> bool:
    lower = model.lower()
    return any(pattern in lower for pattern in _REASONING_SENSITIVE_MODELS)


class MessageHistoryCleaner(CustomLogger):

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        try:
            model = data.get("model", "")
            messages = data.get("messages", [])
            strip_thinking = _is_reasoning_sensitive(model)
            fix_empty_content = _is_empty_content_sensitive(model)

            cleaned_messages = []
            for msg in messages:
                if not isinstance(msg, dict) or msg.get("role") != "assistant":
                    cleaned_messages.append(msg)
                    continue

                # Shallow copy the message to avoid corrupting data referenced elsewhere
                msg_copy = dict(msg)

                if strip_thinking:
                    # 1. Remove top-level reasoning keys injected by native providers
                    msg_copy.pop("reasoning_content", None)
                    msg_copy.pop("thinking", None)

                    # 2. Handle both String and List formats for msg["content"]
                    content = msg_copy.get("content")
                    if isinstance(content, str):
                        msg_copy["content"] = self._strip_reasoning(content)
                    elif isinstance(content, list):
                        # Filter out explicit Anthropic-style or OpenAI-style thinking blocks
                        msg_copy["content"] = [
                            block for block in content
                            if not (
                                isinstance(block, dict) and
                                block.get("type") in ("thinking", "redacted_thinking", "reasoning")
                            )
                        ]
                        # Process text blocks wrapped within content arrays
                        for block in msg_copy["content"]:
                            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                                block["text"] = self._strip_reasoning(block["text"])

                        # If content array is empty, fall back to None or empty string gracefully
                        if not msg_copy["content"]:
                            msg_copy["content"] = None

                # 3. Always normalize tool-call serialization for byte-stable cache hits
                if "tool_calls" in msg_copy and msg_copy["tool_calls"]:
                    # Create a deep copy of tool calls to isolate changes safely
                    normalized_tool_calls = []
                    for tc in msg_copy["tool_calls"]:
                        tc_copy = dict(tc) if isinstance(tc, dict) else tc
                        self._fix_tool_call(tc_copy)
                        normalized_tool_calls.append(tc_copy)
                    msg_copy["tool_calls"] = normalized_tool_calls

                # Fix empty content for sensitive models (e.g. Cohere)
                if fix_empty_content:
                    content = msg_copy.get("content")
                    has_tool_calls = bool(msg_copy.get("tool_calls"))
                    content_empty = content is None or (isinstance(content, str) and not content.strip()) or content == []

                    if content_empty and not has_tool_calls:
                        # Drop the message entirely — provider will reject it
                        continue
                    if content_empty and has_tool_calls:
                        # Provider accepts null but not "" for tool-call turns
                        msg_copy["content"] = None

                cleaned_messages.append(msg_copy)

            data["messages"] = cleaned_messages
        except Exception as e:
            print(f"[PHEIDIPP] Error pre-cleaning message history: {e}", flush=True)
            
        return data

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._log_usage(kwargs, response_obj)

    async def async_log_stream_event(self, kwargs, response_obj, start_time, end_time):
        usage = getattr(response_obj, "usage", None)
        if usage and getattr(usage, "total_tokens", 0) > 0:
            self._log_usage(kwargs, response_obj)

    def _log_usage(self, kwargs, response_obj):
        try:
            usage = getattr(response_obj, "usage", None)
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
        Remove system <think> tags and heuristic thinking signatures,
        returning only the final clean execution text.
        """
        if not text:
            return text

        # Step A: Explicitly excise standard xml/markdown thinking blocks (e.g., DeepSeek R1 style)
        if "<think>" in text:
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        lower = text.lower()
        patterns = [
            r"(final answer\s*:)",
            r"(answer\s*:)",
            r"(conclusion\s*:)",
        ]

        # Step B: Scan regex boundaries for textual pivots
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                idx = match.start()
                return text[idx:].split(":", 1)[-1].strip()

        # Step C: Catch sequential thinking patterns
        if "let's think step by step" in lower:
            parts = text.split("\n")
            # Pull only the concluding non-empty string line
            for part in reversed(parts):
                if part.strip():
                    return part.strip()

        return text

    def _fix_tool_call(self, tc):
        """
        Unwrap double-encoded JSON arguments and enforce compact serialization.
        Ensures perfect downstream byte-matching stability.
        """
        try:
            is_dict = isinstance(tc, dict)
            func = tc.get("function") if is_dict else getattr(tc, "function", None)
            if not func:
                return

            is_func_dict = isinstance(func, dict)
            arguments = func.get("arguments") if is_func_dict else getattr(func, "arguments", None)
            if not arguments:
                return

            # Parse input string
            if isinstance(arguments, str):
                args = json.loads(arguments)
            else:
                args = arguments

            changed = False
            if isinstance(args, dict):
                for key, val in args.items():
                    if isinstance(val, str):
                        try:
                            parsed = json.loads(val)
                            if isinstance(parsed, (list, dict)):
                                args[key] = parsed
                                changed = True
                        except Exception:
                            pass

            # Enforce deterministic spacing via separators
            new_args = json.dumps(args, separators=(",", ":"), sort_keys=True)
            if new_args != arguments or changed:
                if is_func_dict:
                    func["arguments"] = new_args
                else:
                    func.arguments = new_args

        except Exception:
            pass


proxy_handler_instance = MessageHistoryCleaner()