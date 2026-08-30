"""本地词表 catalog：tiktoken 内置 + 磁盘上的 HF / Kimi / 混元 / Grok-2 词表。"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import tiktoken
import yaml
from tiktoken.load import load_tiktoken_bpe
from tokenizers import Tokenizer

from src.match import exact_or_longest_prefix
from src.types import Vocab

# tokenization_kimi.py pretok，必须字节级一致。
KIMI_PAT = (
    r"[\p{Han}]+|"
    r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*"
    r"[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?|"
    r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+"
    r"[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?|"
    r"\p{N}{1,3}|"
    r" ?[^\s\p{L}\p{N}]+[\r\n]*|"
    r"\s*[\r\n]+|"
    r"\s+(?!\S)|"
    r"\s+"
)

# tokenization_hy.py PAT_STR（Hunyuan-A13B / 7B 同源）。
HUNYUAN_PAT = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}|"
    r" ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
)

# vLLM grok2.py：word_split == V1。官方 tokenizer.tok.json 不带 pat_str。
GROK2_PAT = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}|"
    r" ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


class TiktokenVocab:
    """tiktoken Encoding 封装。escaped 把 special 当字面量切。"""

    def __init__(self, id: str, enc: tiktoken.Encoding) -> None:
        self.id = id
        self._enc = enc

    def encode_len(self, text: str, *, escaped: bool = False) -> int:
        if escaped:
            return len(self._enc.encode(text, allowed_special=set(), disallowed_special=()))
        return len(self._enc.encode(text, allowed_special="all"))

    def n_hat(self, base: str, probe: str, *, escaped: bool = False) -> int:
        return self.encode_len(base + probe, escaped=escaped) - self.encode_len(
            base, escaped=escaped
        )


class HFTokenizerVocab:
    """HuggingFace tokenizers.Tokenizer。escaped 走普通 BPE，跳过 added tokens。"""

    def __init__(self, id: str, tokenizer: Tokenizer) -> None:
        self.id = id
        self._tok = tokenizer

    def encode_len(self, text: str, *, escaped: bool = False) -> int:
        if escaped:
            return self._encode_escaped_len(text)
        return len(self._tok.encode(text, add_special_tokens=False).ids)

    def _encode_escaped_len(self, text: str) -> int:
        tok = self._tok
        if tok.normalizer is not None:
            text = tok.normalizer.normalize_str(text)
        if tok.pre_tokenizer is not None:
            pieces = [piece for piece, _off in tok.pre_tokenizer.pre_tokenize_str(text)]
        else:
            pieces = [text]
        n = 0
        for piece in pieces:
            n += len(tok.model.tokenize(piece))
        return n

    def n_hat(self, base: str, probe: str, *, escaped: bool = False) -> int:
        return self.encode_len(base + probe, escaped=escaped) - self.encode_len(
            base, escaped=escaped
        )


def _manifest_path(root: Path) -> Path:
    return root / "catalog" / "manifest.json"


def _load_manifest(root: Path) -> list[dict]:
    data = json.loads(_manifest_path(root).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data["vocabs"])
    return list(data)


def _resolve_local(root: Path, local_path: str | None) -> Path | None:
    if not local_path:
        return None
    p = Path(local_path)
    if not p.is_absolute():
        p = root / p
    return p


def _load_tiktoken_builtin(entry: dict) -> TiktokenVocab:
    name = str(entry["id"])
    return TiktokenVocab(name, tiktoken.get_encoding(name))


def _load_kimi(entry: dict, path: Path) -> TiktokenVocab:
    ranks = load_tiktoken_bpe(str(path))
    enc = tiktoken.Encoding(
        name="kimi",
        pat_str=KIMI_PAT,
        mergeable_ranks=ranks,
        special_tokens={},
    )
    return TiktokenVocab(str(entry["id"]), enc)


def _load_hunyuan(entry: dict, path: Path) -> TiktokenVocab:
    ranks = load_tiktoken_bpe(str(path))
    enc = tiktoken.Encoding(
        name="hunyuan",
        pat_str=HUNYUAN_PAT,
        mergeable_ranks=ranks,
        special_tokens={},
    )
    return TiktokenVocab(str(entry["id"]), enc)


def _load_grok_tok(entry: dict, path: Path) -> TiktokenVocab:
    data = json.loads(path.read_text(encoding="utf-8"))
    ranks = {bytes(item["bytes"]): int(item["token"]) for item in data.get("regular_tokens") or []}
    special: dict[str, int] = {}
    for item in data.get("special_tokens") or []:
        surface = bytes(item["bytes"]).decode("utf-8", errors="replace")
        special[surface] = int(item["token"])
    enc = tiktoken.Encoding(
        name=str(entry["id"]),
        pat_str=data.get("pat_str") or GROK2_PAT,
        mergeable_ranks=ranks,
        special_tokens=special,
        explicit_n_vocab=data.get("vocab_size"),
    )
    return TiktokenVocab(str(entry["id"]), enc)


def _load_hf(entry: dict, path: Path) -> HFTokenizerVocab:
    return HFTokenizerVocab(str(entry["id"]), Tokenizer.from_file(str(path)))


_BACKEND_LOADERS = {
    "tiktoken.model": _load_kimi,
    "tiktoken.hunyuan": _load_hunyuan,
    "tiktoken.tok.json": _load_grok_tok,
    "tokenizers": _load_hf,
}


def _entry_backend(entry: dict) -> str:
    return str(entry.get("backend") or "")


def _load_entry(entry: dict, local: Path) -> Vocab | None:
    vid = str(entry["id"])
    backend = _entry_backend(entry)
    try:
        if backend == "tiktoken":
            return _load_tiktoken_builtin(entry)
        loader = _BACKEND_LOADERS.get(backend)
        if loader is None:
            warnings.warn(
                f"catalog vocab {vid!r} unknown backend {backend!r}; skipped",
                UserWarning,
                stacklevel=2,
            )
            return None
        return loader(entry, local)
    except Exception as exc:
        warnings.warn(
            f"catalog vocab {vid!r} failed to load ({exc}); skipped",
            UserWarning,
            stacklevel=2,
        )
        return None


def load_catalog(root: Path | None = None) -> dict[str, Vocab]:
    """加载可本地编码的词表。内置 tiktoken 始终可加载；缺文件的 HF / Kimi 跳过并 warning。"""
    root = root or repo_root()
    out: dict[str, Vocab] = {}
    for entry in _load_manifest(root):
        vid = str(entry["id"])
        local = _resolve_local(root, entry.get("local_path"))
        if _entry_backend(entry) == "tiktoken" and local is None:
            out[vid] = _load_tiktoken_builtin(entry)
            continue
        if local is None or not local.is_file():
            warnings.warn(
                f"catalog vocab {vid!r} missing local file; skipped",
                UserWarning,
                stacklevel=2,
            )
            continue
        loaded = _load_entry(entry, local)
        if loaded is not None:
            out[vid] = loaded
    return out


def load_model_family_map(root: Path | None = None) -> dict[str, str]:
    root = root or repo_root()
    path = root / "catalog" / "model_family.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model_family.yaml must be a mapping of claimed model → catalog id")
    return {str(k): str(v) for k, v in data.items()}


def lookup_claimed_family(claimed: str, mapping: dict[str, str] | None = None) -> str | None:
    """精确命中，否则最长前缀（大小写不敏感）。qwen3.8* 优先于 qwen3。"""
    mapping = mapping if mapping is not None else load_model_family_map()
    return exact_or_longest_prefix(claimed, mapping)
