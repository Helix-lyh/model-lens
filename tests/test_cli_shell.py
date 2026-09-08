"""shell 附录命令：解析对照 id，不打网。"""

from src.cli import build_parser, resolve_shell_peers
from src.types import Endpoint, Targets


def _targets(model: str = "omen-alpha", claimed: str = "glm-5.3-flash") -> Targets:
    return Targets(
        claimed_model=claimed,
        target=Endpoint(
            base_url="https://example.test/v1",
            api_key_env="TARGET_KEY",
            model=model,
        ),
    )


def test_parser_has_shell():
    args = build_parser().parse_args(
        ["shell", "--target", "examples/targets.yaml", "--peers", "glm-5.3-flash"]
    )
    assert args.cmd == "shell"
    assert args.peers == "glm-5.3-flash"
    assert args.func.__name__ == "_cmd_shell"


def test_peers_flag_wins():
    assert resolve_shell_peers(_targets(), "a, b ,omen-alpha") == ["a", "b"]


def test_claimed_used_when_peers_omitted():
    assert resolve_shell_peers(_targets(), None) == ["glm-5.3-flash"]


def test_no_peer_when_claimed_is_target():
    assert resolve_shell_peers(_targets(model="glm-5.3-flash"), None) == []
