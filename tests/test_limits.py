from src.limits import official_max_output


def test_deepseek_v4_official_384k() -> None:
    assert official_max_output("deepseek-v4-flash") == 384000
    assert official_max_output("deepseek-v4-pro") == 384000
    assert official_max_output("deepseek-v4-flash-vision-exp") == 384000


def test_unknown_model_has_no_guess() -> None:
    assert official_max_output("demo-model") is None
    assert official_max_output("grok-4.5") is None


def test_glm_official_max_from_docs() -> None:
    assert official_max_output("glm-4.5-flash") == 98304
    assert official_max_output("glm-4.6") == 131072
    assert official_max_output("glm-4.6v-flash") == 32768
    assert official_max_output("glm-5.1") == 131072


def test_claude_current_line_from_docs() -> None:
    assert official_max_output("claude-sonnet-5") == 128000
    assert official_max_output("claude-haiku-4-5") == 64000
    assert official_max_output("claude-sonnet-4-5") == 64000
