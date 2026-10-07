"""Register the live 20261008 questions. Nothing else is installed."""

from __future__ import annotations

from .bank_registry import ITEMS, ItemPlugin


def _install_coding(active: set[str], profiles: dict[str, dict[str, str]]) -> None:
    from .bank_manifest import ITEM_CODE_LANG
    from .next_coding import coding_items, prompt, score_saved

    for item in coding_items():
        if item.id not in active:
            continue
        assigned = ITEM_CODE_LANG[item.id]
        ITEMS.register(ItemPlugin(
            item.id, "coding", item.title,
            lambda language=None, item_id=item.id, assigned=assigned: prompt(item_id, language or assigned),
            lambda text, language=None, item_id=item.id, assigned=assigned: score_saved(item_id, text, language or assigned),
            runtime_profiles=profiles.get(item.id, {}),
        ), replace=True)


def _install_engineering(active: set[str]) -> None:
    from .engineering import ENGINEERING_SCENARIOS, score_engineering
    from .engineering_next import score_next
    from .next_questions import DOCS, _sections

    for item_id, scenario in ENGINEERING_SCENARIOS.items():
        if item_id in active:
            ITEMS.register(ItemPlugin(
                item_id, "engineering", scenario["title"],
                lambda language=None, prompt=scenario["prompt"]: prompt,
                lambda text, language=None, item_id=item_id: score_engineering(text, item_id),
            ), replace=True)
    for item_id, (title, body) in _sections(DOCS["engineering"], "E").items():
        if item_id in active and item_id not in ENGINEERING_SCENARIOS:
            ITEMS.register(ItemPlugin(
                item_id, "engineering", title,
                lambda language=None, body=body: body,
                lambda text, language=None, item_id=item_id: score_next(item_id, text),
            ), replace=True)


def _install_reasoning(active: set[str]) -> None:
    from .next_reasoning import BY_ID, render_reasoning_prompt, score_reasoning

    for item_id, item in BY_ID.items():
        if item_id in active:
            ITEMS.register(ItemPlugin(
                item_id, "reasoning", item.title,
                lambda language=None, item_id=item_id: render_reasoning_prompt(item_id),
                lambda text, language=None, item_id=item_id: score_reasoning(item_id, text),
            ), replace=True)


def install() -> None:
    from .bank_manifest import ACTIVE_ITEMS, ITEM_RUNTIME_PROFILES

    active = set(ACTIVE_ITEMS)
    _install_coding(active, ITEM_RUNTIME_PROFILES)
    _install_engineering(active)
    _install_reasoning(active)
    from .next_questions import install_design_descriptors
    install_design_descriptors()


install()
