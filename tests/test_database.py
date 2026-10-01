"""Integração CSV → AnimalRecord → Splay Tree.

Cobertura:
  1. Leitura dos CSVs e construção da árvore.
  2. Transformação correta em objetos AnimalRecord.
  3. Inserção na Splay Tree com ID como chave.
  4. Obtenção de ID válido existente.
  5. Busca por ID com operação de splay (nó vai à raiz).
"""

from __future__ import annotations

import unittest

import database as db
from database import (
    VERNACULAR_CSV,
    TAXA_CSV,
    build_tree_from_csv,
    find_animal_by_id,
    get_valid_id,
    all_taxonomic_classes,
)
from animal import AnimalRecord


def _skip_if_no_csv(test_case: unittest.TestCase) -> None:
    if not VERNACULAR_CSV.is_file() or not TAXA_CSV.is_file():
        test_case.skipTest("CSVs ausentes — execute com os arquivos em data/")


# ---------------------------------------------------------------------------
# Req 1 — Leitura dos CSVs e construção da árvore
# ---------------------------------------------------------------------------

class DatabaseBuildTests(unittest.TestCase):
    """Req 1 — Os CSVs são lidos e a árvore é construída corretamente."""

    @classmethod
    def setUpClass(cls) -> None:
        if not VERNACULAR_CSV.is_file():
            raise unittest.SkipTest(f"CSV ausente: {VERNACULAR_CSV}")
        cls._prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 500  # rápido, evita varrer 394 MB inteiro

    @classmethod
    def tearDownClass(cls) -> None:
        db.MAX_VERNACULAR_ROWS = cls._prev_limit

    def test_tree_is_not_empty(self) -> None:
        """Após leitura dos CSVs a árvore deve conter pelo menos 1 animal."""
        tree = build_tree_from_csv()
        self.assertGreater(len(tree), 0,
                           "Nenhum animal foi carregado dos CSVs.")

    def test_all_classes_are_non_empty_strings(self) -> None:
        """Toda classe taxonômica carregada deve ser string não-vazia."""
        tree = build_tree_from_csv()
        classes = all_taxonomic_classes(tree)
        self.assertGreater(len(classes), 0)
        for cls_name in classes:
            self.assertIsInstance(cls_name, str)
            self.assertTrue(cls_name.strip(),
                            f"Classe vazia encontrada: {cls_name!r}")

    def test_inorder_is_sorted_by_id(self) -> None:
        """As chaves em in-order devem estar em ordem crescente (propriedade ABB)."""
        tree = build_tree_from_csv()
        keys = tree.keys_inorder()
        self.assertEqual(keys, sorted(keys),
                         "In-order da Splay Tree não está em ordem crescente.")


# ---------------------------------------------------------------------------
# Req 2 — Transformação correta em objetos AnimalRecord
# ---------------------------------------------------------------------------

class AnimalRecordTransformTests(unittest.TestCase):
    """Req 2 — Registros CSV são transformados corretamente em AnimalRecord."""

    @classmethod
    def setUpClass(cls) -> None:
        if not VERNACULAR_CSV.is_file():
            raise unittest.SkipTest(f"CSV ausente: {VERNACULAR_CSV}")
        cls._prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 500
        cls.tree = build_tree_from_csv()

    @classmethod
    def tearDownClass(cls) -> None:
        db.MAX_VERNACULAR_ROWS = cls._prev_limit

    def test_all_values_are_animal_records(self) -> None:
        """Todos os valores na árvore devem ser instâncias de AnimalRecord."""
        for record in self.tree.values_inorder():
            self.assertIsInstance(record, AnimalRecord,
                                  f"Valor inesperado: {record!r}")

    def test_record_ids_match_tree_keys(self) -> None:
        """O campo AnimalRecord.id deve coincidir com a chave do nó na árvore."""
        keys = self.tree.keys_inorder()
        values = self.tree.values_inorder()
        for key, record in zip(keys, values):
            self.assertEqual(
                record.id, key,
                msg=f"Chave da árvore {key} != AnimalRecord.id {record.id}"
            )

    def test_all_ids_are_positive_integers(self) -> None:
        """IDs de taxon devem ser inteiros positivos (>0)."""
        for record in self.tree.values_inorder():
            self.assertIsInstance(record.id, int)
            self.assertGreater(record.id, 0,
                               f"ID inválido: {record.id}")

    def test_all_common_names_are_non_empty(self) -> None:
        """Nomes populares carregados devem ser strings não-vazias."""
        for record in self.tree.values_inorder():
            self.assertTrue(
                record.common_name.strip(),
                msg=f"Nome popular vazio para id={record.id}"
            )

    def test_all_taxonomic_classes_are_non_empty(self) -> None:
        """Classe taxonômica de cada registro deve ser string não-vazia."""
        for record in self.tree.values_inorder():
            self.assertTrue(
                record.taxonomic_class.strip(),
                msg=f"Classe taxonômica vazia para id={record.id}"
            )

    def test_known_vernacular_records(self) -> None:
        """IDs conhecidos devem ter dados coerentes com os CSVs reais."""
        # Pares (taxon_id, nome_pt, classe) confirmados na inspeção dos CSVs
        expected = [
            (47250, "Actinopterygii"),  # Bicuda-africana / Sphyraena guachancho
            (47302, "Chondrichthyes"),  # Tubarão-cobra / Chlamydoselachus anguineus
        ]
        for taxon_id, expected_class in expected:
            rec = find_animal_by_id(self.tree, taxon_id)
            if rec is None:
                continue  # fora do subconjunto limitado — OK
            self.assertEqual(rec.id, taxon_id)
            self.assertEqual(
                rec.taxonomic_class, expected_class,
                msg=f"Classe incorreta para id={taxon_id}: "
                    f"esperado={expected_class!r}, obtido={rec.taxonomic_class!r}"
            )
            self.assertTrue(rec.common_name.strip())
            self.assertTrue(rec.scientific_name.strip())


# ---------------------------------------------------------------------------
# Req 3 — Inserção na Splay Tree com ID como chave
# ---------------------------------------------------------------------------

class DatabaseInsertionTests(unittest.TestCase):
    """Req 3 — Animais são inseridos na Splay Tree usando o ID como chave."""

    @classmethod
    def setUpClass(cls) -> None:
        if not VERNACULAR_CSV.is_file():
            raise unittest.SkipTest(f"CSV ausente: {VERNACULAR_CSV}")
        cls._prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 500
        cls.tree = build_tree_from_csv()

    @classmethod
    def tearDownClass(cls) -> None:
        db.MAX_VERNACULAR_ROWS = cls._prev_limit

    def test_no_duplicate_keys(self) -> None:
        """Não deve haver chaves duplicadas na árvore."""
        keys = self.tree.keys_inorder()
        self.assertEqual(len(keys), len(set(keys)),
                         "Chaves duplicadas encontradas na Splay Tree.")

    def test_every_key_is_findable(self) -> None:
        """Cada chave do in-order deve ser recuperável via find()."""
        keys = self.tree.keys_inorder()
        # Verifica todos (subconjunto é pequeno ≤ 500)
        for k in keys:
            rec = find_animal_by_id(self.tree, k)
            self.assertIsNotNone(rec, msg=f"Chave {k} inserida mas não encontrada.")

    def test_build_twice_same_count(self) -> None:
        """Construir a árvore duas vezes com o mesmo limite deve dar o mesmo tamanho."""
        t1 = build_tree_from_csv()
        t2 = build_tree_from_csv()
        self.assertEqual(len(t1), len(t2))


# ---------------------------------------------------------------------------
# Req 4 — Obtenção de ID válido existente na árvore
# ---------------------------------------------------------------------------

class GetValidIdTests(unittest.TestCase):
    """Req 4 — get_valid_id() retorna IDs efetivamente presentes na árvore."""

    @classmethod
    def setUpClass(cls) -> None:
        if not VERNACULAR_CSV.is_file():
            raise unittest.SkipTest(f"CSV ausente: {VERNACULAR_CSV}")
        cls._prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 500
        cls.tree = build_tree_from_csv()

    @classmethod
    def tearDownClass(cls) -> None:
        db.MAX_VERNACULAR_ROWS = cls._prev_limit

    def test_first_id_is_present(self) -> None:
        first = get_valid_id(self.tree, index=0)
        self.assertIsNotNone(find_animal_by_id(self.tree, first))

    def test_last_id_is_present(self) -> None:
        last_idx = len(self.tree) - 1
        last = get_valid_id(self.tree, index=last_idx)
        self.assertIsNotNone(find_animal_by_id(self.tree, last))

    def test_middle_id_is_present(self) -> None:
        mid = get_valid_id(self.tree, index=len(self.tree) // 2)
        self.assertIsNotNone(find_animal_by_id(self.tree, mid))

    def test_out_of_range_raises(self) -> None:
        from database import DatabaseError
        with self.assertRaises(DatabaseError):
            get_valid_id(self.tree, index=-1)
        with self.assertRaises(DatabaseError):
            get_valid_id(self.tree, index=len(self.tree))


# ---------------------------------------------------------------------------
# Req 5 — Busca por ID com splay (nó vai à raiz)
# ---------------------------------------------------------------------------

class DatabaseSplaySearchTests(unittest.TestCase):
    """Req 5 — find_animal_by_id() realiza splay; nó encontrado vai à raiz."""

    @classmethod
    def setUpClass(cls) -> None:
        if not VERNACULAR_CSV.is_file():
            raise unittest.SkipTest(f"CSV ausente: {VERNACULAR_CSV}")
        cls._prev_limit = db.MAX_VERNACULAR_ROWS
        db.MAX_VERNACULAR_ROWS = 500
        cls.tree = build_tree_from_csv()

    @classmethod
    def tearDownClass(cls) -> None:
        db.MAX_VERNACULAR_ROWS = cls._prev_limit

    def test_found_id_becomes_root(self) -> None:
        """Após find_animal_by_id(tree, k), tree.search_root_key() deve ser k."""
        keys = self.tree.keys_inorder()
        # Testa primeiro, meio e último
        for idx in (0, len(keys) // 4, len(keys) // 2, len(keys) - 1):
            k = keys[idx]
            find_animal_by_id(self.tree, k)
            self.assertEqual(
                self.tree.search_root_key(), k,
                msg=f"Após busca de id={k}, raiz deveria ser {k} "
                    f"mas é {self.tree.search_root_key()}"
            )

    def test_absent_id_does_not_crash(self) -> None:
        """Busca de ID inexistente deve retornar None sem lançar exceção."""
        result = find_animal_by_id(self.tree, 999_999_999)
        self.assertIsNone(result)

    def test_repeated_search_same_root(self) -> None:
        """Buscar o mesmo ID duas vezes consecutivas mantém o nó na raiz."""
        k = get_valid_id(self.tree, index=len(self.tree) // 3)
        find_animal_by_id(self.tree, k)
        self.assertEqual(self.tree.search_root_key(), k)
        find_animal_by_id(self.tree, k)
        self.assertEqual(self.tree.search_root_key(), k)

    def test_sequential_searches_each_goes_to_root(self) -> None:
        """Buscar IDs diferentes em sequência: cada um deve subir à raiz na sua vez."""
        keys = self.tree.keys_inorder()
        sample = keys[:10]  # primeiros 10 IDs em ordem
        for k in sample:
            find_animal_by_id(self.tree, k)
            self.assertEqual(
                self.tree.search_root_key(), k,
                msg=f"Após find_animal_by_id(tree, {k}), raiz = {self.tree.search_root_key()}"
            )


if __name__ == "__main__":
    unittest.main()
