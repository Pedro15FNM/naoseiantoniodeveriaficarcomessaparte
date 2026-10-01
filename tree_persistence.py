"""Persistência da Splay Tree em pickle (módulo isolado; sem regras de gameplay)."""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path
from typing import Any

from animal import AnimalRecord
from splay_tree import SplayTree

PICKLE_VERSION = 1
DEFAULT_PICKLE_PATH = Path(__file__).resolve().parent / "data" / "animals_splay.pkl"


def save_splay_tree(
    tree: SplayTree[AnimalRecord],
    fingerprint: str,
    path: Path = DEFAULT_PICKLE_PATH,
) -> bool:
    """Grava árvore em path (escrita atômica via .tmp). Retorna False se falhar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PICKLE_VERSION,
        "fingerprint": fingerprint,
        "tree": tree,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
        return True
    except OSError as exc:
        _warn(f"não foi possível salvar cache {path}: {exc}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _validate_payload(payload: Any, expected_fingerprint: str) -> SplayTree[AnimalRecord] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != PICKLE_VERSION:
        return None
    if payload.get("fingerprint") != expected_fingerprint:
        return None
    tree = payload.get("tree")
    if not isinstance(tree, SplayTree):
        return None
    try:
        if len(tree) == 0:
            return None
    except (RecursionError, RuntimeError):
        return None
    return tree


def load_splay_tree(
    expected_fingerprint: str,
    path: Path = DEFAULT_PICKLE_PATH,
) -> SplayTree[AnimalRecord] | None:
    """
    Carrega árvore persistida se existir e for válida.
    Arquivo ausente, corrompido ou incompatível → None (sem exceção).
    """
    if not path.is_file():
        return None
    try:
        with path.open("rb") as f:
            payload = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, OSError, AttributeError, TypeError, ValueError) as exc:
        _warn(f"cache ignorado ({path} corrompido ou ilegível): {exc}")
        return None
    tree = _validate_payload(payload, expected_fingerprint)
    if tree is None:
        _warn(f"cache ignorado ({path} inválido ou desatualizado)")
    return tree


def _warn(message: str) -> None:
    print(f"[tree_persistence] {message}", file=sys.stderr)
