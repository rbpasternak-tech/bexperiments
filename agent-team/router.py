"""Decides which persona should answer a message.

Direct address wins ("Ron, remind me..." / "@april what's left today").
Otherwise a small, cheap Claude call picks the best-fit teammate, falling
back to the default persona on any error.
"""

import re


def build_alias_map(personas_cfg):
    """Map every lowercase alias and persona key to its persona key."""
    alias_map = {}
    for key, persona in personas_cfg["personas"].items():
        alias_map[key.lower()] = key
        for alias in persona.get("aliases", []):
            alias_map[alias.lower()] = key
    return alias_map


def match_direct_address(text, alias_map):
    """Return (persona_key, remaining_text) if the message names a persona first."""
    match = re.match(r"^[@/]?(\w+)[\s,:.!-]*(.*)$", text.strip(), re.DOTALL)
    if not match:
        return None, text
    candidate, rest = match.group(1).lower(), match.group(2).strip()
    if candidate in alias_map:
        return alias_map[candidate], rest or text
    return None, text


def route_with_model(anthropic_client, router_model, personas_cfg, text, history):
    """Ask a small model which persona fits the message; fall back to default."""
    default = personas_cfg["default"]
    roster = "\n".join(
        f"- {key}: {p['role'].strip()}" for key, p in personas_cfg["personas"].items()
    )
    recent = "\n".join(f"[{e['speaker']}] {e['text']}" for e in history[-6:])
    try:
        response = anthropic_client.messages.create(
            model=router_model,
            max_tokens=10,
            system=(
                "You route messages to one member of a persona team. Reply with "
                f"exactly one key and nothing else.\nTeam:\n{roster}\n"
                f"Recent conversation:\n{recent or '(none)'}\n"
                "If the message continues a thread with the last persona who "
                f"spoke, keep them. If unsure, reply '{default}'."
            ),
            messages=[{"role": "user", "content": text}],
        )
        choice = response.content[0].text.strip().lower()
        if choice in personas_cfg["personas"]:
            return choice
    except Exception:
        pass
    return default


def pick_persona(anthropic_client, router_model, personas_cfg, alias_map, text,
                 history):
    """Return (persona_key, text_for_persona) for an incoming message."""
    direct, rest = match_direct_address(text, alias_map)
    if direct:
        return direct, rest
    return (
        route_with_model(anthropic_client, router_model, personas_cfg, text, history),
        text,
    )
