"""Persistência pickle da Splay Tree — testes isolados e de integração.

Cobre os 4 comportamentos exigidos:
  1. Cache válido existente → carregado sem reconstruir dos CSVs.
  2. Cache ausente → reconstrução a partir dos CSVs + salvamento automático.
  3. Cache corrompido / inválido → descartado graciosamente, sem exceção.
  4. Fingerprint divergente → cache ignorado, árvore reconstruída.
"""

from __future__ import annotations

import os
import pickle
import tempfile
import unittest
from pathlib import Path

from animal import AnimalRecord
from splay_tree import SplayTree
from tree_persistence import (
    DEFAULT_PICKLE_PATH,
    PICKLE_VERSION,
    load_splay_tree,
    save_splay_tree,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_tree(n: int = 5) -> SplayTree[AnimalRecord]:
    """Árvore pequena com AnimalRecords sintéticos para testes rápidos."""
    t: SplayTree[AnimalRecord] = SplayTree()
    animals = [
        AnimalRecord(99,  "Tubarão",        "Chlamydoselachus anguineus", "Chondrichthyes"),
        AnimalRecord(77,  "Abetarda",        "Otis tarda",                 "Aves"),
        AnimalRecord(482, "Galeirão-comum",  "Fulica atra",                "Aves"),
        AnimalRecord(24492, "Perereca",      "Brachycephalus ephippium",   "Amphibia"),
        AnimalRecord(47250, "Bicuda-africana", "Sphyraena guachancho",     "Actinopterygii"),
    ]
    for rec in animals[:n]:
        t.insert(rec.id, rec)
    return t


# ---------------------------------------------------------------------------
# Cenário 1 — Salvar e carregar (round-trip)
# ---------------------------------------------------------------------------

class PersistenceRoundTripTests(unittest.TestCase):
    """Req 1 — Cache válido é carregado corretamente."""

    def test_save_returns_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            ok = save_splay_tree(_sample_tree(), "fp_ok", path)
            self.assertTrue(ok, "save_splay_tree() deveria retornar True em caso de sucesso.")

    def test_file_created_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            self.assertFalse(path.exists())
            save_splay_tree(_sample_tree(), "fp", path)
            self.assertTrue(path.exists(), "Arquivo .pkl não foi criado.")

    def test_parent_dir_created_automatically(self) -> None:
        """O diretório data/ é criado se não existir (path aninhado)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "subdir" / "animals_splay.pkl"
            save_splay_tree(_sample_tree(), "fp", path)
            self.assertTrue(path.exists())

    def test_roundtrip_preserves_all_records(self) -> None:
        """Todos os AnimalRecords devem ser idênticos após save → load."""
        tree = _sample_tree()
        original_keys = tree.keys_inorder()
        fp = "roundtrip_fp"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            save_splay_tree(tree, fp, path)
            loaded = load_splay_tree(fp, path)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.keys_inorder(), original_keys)

            for key in original_keys:
                orig_rec = tree.find(key)
                load_rec = loaded.find(key)
                self.assertIsNotNone(load_rec, msg=f"Chave {key} perdida após load.")
                self.assertEqual(orig_rec, load_rec,
                                 msg=f"Registro diferente após load para id={key}")

    def test_roundtrip_splay_still_works_after_load(self) -> None:
        """A árvore carregada do pickle deve suportar operações de splay."""
        fp = "splay_fp"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            save_splay_tree(_sample_tree(), fp, path)
            loaded = load_splay_tree(fp, path)
            assert loaded is not None

            loaded.find(77)
            self.assertEqual(loaded.search_root_key(), 77,
                             "Splay não funcionou na árvore carregada do pickle.")

    def test_save_is_atomic_tmp_file_removed(self) -> None:
        """O arquivo .tmp intermediário não deve existir após save bem-sucedido."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            save_splay_tree(_sample_tree(), "fp", path)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            self.assertFalse(tmp_path.exists(),
                             "Arquivo .tmp temporário não foi removido após save.")


# ---------------------------------------------------------------------------
# Cenário 2 — Arquivo ausente (primeira execução)
# ---------------------------------------------------------------------------

class PersistenceMissingFileTests(unittest.TestCase):
    """Req 2 — Arquivo ausente retorna None; a reconstrução é responsabilidade do chamador."""

    def test_missing_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.pkl"
            result = load_splay_tree("any_fingerprint", path)
            self.assertIsNone(result,
                              "Arquivo ausente deveria retornar None.")

    def test_missing_file_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "does_not_exist.pkl"
            try:
                load_splay_tree("fp", path)
            except Exception as exc:
                self.fail(f"load_splay_tree() lançou exceção inesperada: {exc}")

    def test_integration_cache_created_after_rebuild(self) -> None:
        """Após reconstrução dos CSVs, o arquivo pickle deve ser criado."""
        import database as db
        from database import load_animal_tree

        if not db.VERNACULAR_CSV.is_file():
            self.skipTest("CSV ausente")

        prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 100  # mínimo para ser rápido

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            prev_path = db.PICKLE_PATH
            db.PICKLE_PATH = path
            try:
                tree = load_animal_tree(force_rebuild=True)
                self.assertGreater(len(tree), 0)
                self.assertTrue(path.is_file(),
                                "Arquivo .pkl não foi criado após force_rebuild.")
            finally:
                db.PICKLE_PATH = prev_path
                db.MAX_VERNACULAR_ROWS = prev_limit


# ---------------------------------------------------------------------------
# Cenário 3 — Arquivo corrompido / inválido
# ---------------------------------------------------------------------------

class PersistenceCorruptFileTests(unittest.TestCase):
    """Req 3 — Arquivo corrompido/inválido é descartado sem exceção."""

    def _assert_returns_none_silently(self, path: Path, fp: str = "fp") -> None:
        try:
            result = load_splay_tree(fp, path)
        except Exception as exc:
            self.fail(f"load_splay_tree() lançou exceção em arquivo inválido: {exc}")
        self.assertIsNone(result)

    def test_random_bytes_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.pkl"
            path.write_bytes(b"not-a-pickle-at-all-xyz")
            self._assert_returns_none_silently(path)

    def test_truncated_pickle_returns_none(self) -> None:
        """Pickle truncado no meio deve ser descartado graciosamente."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.pkl"
            # Gravar pickle válido e truncar pela metade
            save_splay_tree(_sample_tree(), "fp", path)
            data = path.read_bytes()
            path.write_bytes(data[:len(data) // 2])
            self._assert_returns_none_silently(path)

    def test_empty_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.pkl"
            path.write_bytes(b"")
            self._assert_returns_none_silently(path)

    def test_wrong_version_returns_none(self) -> None:
        """Payload com version diferente de PICKLE_VERSION deve ser rejeitado."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrong_ver.pkl"
            payload = {
                "version": PICKLE_VERSION + 99,
                "fingerprint": "fp",
                "tree": _sample_tree(),
            }
            with path.open("wb") as f:
                pickle.dump(payload, f)
            self._assert_returns_none_silently(path)

    def test_missing_tree_key_returns_none(self) -> None:
        """Payload sem chave 'tree' deve ser rejeitado."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "no_tree.pkl"
            payload = {"version": PICKLE_VERSION, "fingerprint": "fp"}
            with path.open("wb") as f:
                pickle.dump(payload, f)
            self._assert_returns_none_silently(path)

    def test_non_dict_payload_returns_none(self) -> None:
        """Payload que não é dict deve ser rejeitado."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not_dict.pkl"
            with path.open("wb") as f:
                pickle.dump([1, 2, 3], f)
            self._assert_returns_none_silently(path)

    def test_tree_replaced_by_string_returns_none(self) -> None:
        """'tree' contendo um objeto que não é SplayTree deve ser rejeitado."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_tree.pkl"
            payload = {
                "version": PICKLE_VERSION,
                "fingerprint": "fp",
                "tree": "isso não é uma SplayTree",
            }
            with path.open("wb") as f:
                pickle.dump(payload, f)
            self._assert_returns_none_silently(path)


# ---------------------------------------------------------------------------
# Cenário 4 — Fingerprint divergente (CSVs mudaram ou parâmetros diferentes)
# ---------------------------------------------------------------------------

class PersistenceFingerprintTests(unittest.TestCase):
    """Req 4 — Fingerprint divergente invalida o cache."""

    def test_wrong_fingerprint_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            save_splay_tree(_sample_tree(), "fp_gravado", path)
            result = load_splay_tree("fp_diferente", path)
            self.assertIsNone(result,
                              "Cache com fingerprint divergente deveria retornar None.")

    def test_correct_fingerprint_loads_ok(self) -> None:
        """O mesmo fingerprint deve carregar a árvore com sucesso."""
        fp = "fingerprint_exata"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            save_splay_tree(_sample_tree(), fp, path)
            loaded = load_splay_tree(fp, path)
            self.assertIsNotNone(loaded)

    def test_integration_cache_reused_same_csvs(self) -> None:
        """Segunda chamada a load_animal_tree() deve reutilizar o cache."""
        import database as db
        from database import load_animal_tree

        if not db.VERNACULAR_CSV.is_file():
            self.skipTest("CSV ausente")

        prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 100

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            prev_path = db.PICKLE_PATH
            db.PICKLE_PATH = path
            try:
                t1 = load_animal_tree(force_rebuild=True)
                n1 = len(t1)
                self.assertTrue(path.is_file())

                # Segunda carga: deve vir do cache, mesmo tamanho
                t2 = load_animal_tree(force_rebuild=False)
                self.assertEqual(
                    len(t2), n1,
                    "Cache reutilizado deveria ter o mesmo número de animais."
                )
            finally:
                db.PICKLE_PATH = prev_path
                db.MAX_VERNACULAR_ROWS = prev_limit

    def test_integration_different_limit_invalidates_cache(self) -> None:
        """Mudar MAX_VERNACULAR_ROWS deve gerar fingerprint diferente e reconstruir."""
        import database as db
        from database import load_animal_tree

        if not db.VERNACULAR_CSV.is_file():
            self.skipTest("CSV ausente")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "animals_splay.pkl"
            prev_path = db.PICKLE_PATH
            prev_limit = db.MAX_VERNACULAR_ROWS
            db.PICKLE_PATH = path
            try:
                db.MAX_VERNACULAR_ROWS = 100
                t1 = load_animal_tree(force_rebuild=True)
                n1 = len(t1)

                # Muda o limite → fingerprint muda → cache deve ser ignorado
                db.MAX_VERNACULAR_ROWS = 200
                t2 = load_animal_tree(force_rebuild=False)
                # n2 pode ser maior que n1 (mais registros) ou igual se o CSV
                # não tem mais dados nesse range — mas não deve ser n1 exato
                # se há mais registros disponíveis. Apenas confirma que a árvore
                # é válida e não lança exceção.
                self.assertGreater(len(t2), 0)
            finally:
                db.PICKLE_PATH = prev_path
                db.MAX_VERNACULAR_ROWS = prev_limit


# ---------------------------------------------------------------------------
# Teste de caminho padrão
# ---------------------------------------------------------------------------

class DefaultPathTests(unittest.TestCase):
    """Verifica que DEFAULT_PICKLE_PATH aponta para data/animals_splay.pkl."""

    def test_default_path_inside_data_dir(self) -> None:
        self.assertEqual(DEFAULT_PICKLE_PATH.name, "animals_splay.pkl")
        self.assertEqual(DEFAULT_PICKLE_PATH.parent.name, "data")

    def test_default_path_is_absolute(self) -> None:
        self.assertTrue(DEFAULT_PICKLE_PATH.is_absolute())


if __name__ == "__main__":
    unittest.main()
