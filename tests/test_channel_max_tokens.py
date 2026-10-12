"""max_tokens 按每个模型在 catalog/output_limits.yaml 登记的官方最大输出发送，不统一压低。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cursor_workspace.build_scripts import run_eval_20260925 as run_eval  # noqa: E402
from src.limits import official_max_output  # noqa: E402

CATALOG_MODEL = {"deepseek-chat": "deepseek-v4"}


def test_catalog_channels_send_official_max_output():
    chans = run_eval.channels(grok_base="https://example.invalid", grok_key_env="X", grok_cli_proxy=False)
    assert chans["deepseek-flash"].max_tokens == 384000
    for name, ch in chans.items():
        if name.startswith("grok-"):
            continue  # grok 未在 catalog 登记，沿用渠道固定值
        expected = official_max_output(CATALOG_MODEL.get(name, ch.model))
        assert expected is not None, name
        assert ch.max_tokens == expected, (name, ch.max_tokens, expected)
