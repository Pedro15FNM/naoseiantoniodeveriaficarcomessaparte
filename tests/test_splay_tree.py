"""Testes unitários da Splay Tree (sem Pygame, skip list ou database).

Cobertura dos 4 requisitos pedidos:
  1. Elementos são inseridos corretamente.
  2. A busca funciona.
  3. O elemento encontrado é levado para a raiz.
  4. A propriedade de ABB por ID é preservada.
"""

from __future__ import annotations

import random
import unittest

from splay_tree import SplayNode, SplayTree


# ---------------------------------------------------------------------------
# Helpers de verificação estrutural
# ---------------------------------------------------------------------------

def _is_bst(node: SplayNode[int] | None, lo: int | None = None, hi: int | None = None) -> bool:
    """Valida recursivamente que a subárvore responde à propriedade de ABB."""
    if node is None:
        return True
    if lo is not None and node.key <= lo:
        return False
    if hi is not None and node.key >= hi:
        return False
    return _is_bst(node.left, lo, node.key) and _is_bst(node.right, node.key, hi)


def _parent_links_ok(node: SplayNode[int] | None) -> bool:
    """Verifica que os ponteiros parent são consistentes com left/right."""
    if node is None:
        return True
    if node.left is not None and node.left.parent is not node:
        return False
    if node.right is not None and node.right.parent is not node:
        return False
    return _parent_links_ok(node.left) and _parent_links_ok(node.right)


# ---------------------------------------------------------------------------
# Requisito 1 — Inserção correta
# ---------------------------------------------------------------------------

class SplayTreeInsertTests(unittest.TestCase):
    """Req 1 — Elementos são inseridos corretamente."""

    def test_inorder_after_sequential_inserts(self) -> None:
        """In-order deve devolver chaves em ordem crescente após inserção fora de ordem."""
        t: SplayTree[str] = SplayTree()
        for key in (10, 5, 20, 3, 7, 15, 25):
            t.insert(key, f"v{key}")
        self.assertEqual(t.keys_inorder(), [3, 5, 7, 10, 15, 20, 25])
        self.assertEqual(len(t), 7)

    def test_inorder_after_reverse_inserts(self) -> None:
        """Inserção em ordem decrescente não deve gerar duplicatas nem perder nós."""
        t: SplayTree[int] = SplayTree()
        for k in range(20, 0, -1):
            t.insert(k, k)
        self.assertEqual(t.keys_inorder(), list(range(1, 21)))

    def test_single_insert(self) -> None:
        """Após uma única inserção a raiz deve ser o nó inserido."""
        t: SplayTree[str] = SplayTree()
        t.insert(42, "resposta")
        self.assertEqual(t.search_root_key(), 42)
        self.assertEqual(len(t), 1)

    def test_duplicate_key_updates_value(self) -> None:
        """Reinserção de chave existente deve atualizar o valor sem criar duplicata."""
        t: SplayTree[str] = SplayTree()
        t.insert(7, "sete")
        t.insert(7, "SETE_atualizado")
        self.assertEqual(len(t), 1)
        self.assertEqual(t.find(7), "SETE_atualizado")

    def test_invalid_key_raises(self) -> None:
        """Chave <= 0 deve disparar ValueError (contrato dos IDs de taxon)."""
        t: SplayTree[str] = SplayTree()
        with self.assertRaises(ValueError):
            t.insert(0, "zero")
        with self.assertRaises(ValueError):
            t.insert(-5, "negativo")

    def test_stress_500_random_taxon_ids(self) -> None:
        """500 IDs simulando IDs de taxon: in-order deve coincidir com sorted()."""
        rng = random.Random(2024)
        ids = rng.sample(range(1, 100_000), 500)
        t: SplayTree[int] = SplayTree()
        for taxon_id in ids:
            t.insert(taxon_id, taxon_id)
        self.assertEqual(len(t), 500)
        self.assertEqual(t.keys_inorder(), sorted(ids))


# ---------------------------------------------------------------------------
# Requisito 2 — Busca funciona
# ---------------------------------------------------------------------------

class SplayTreeFindTests(unittest.TestCase):
    """Req 2 — A busca funciona corretamente."""

    def test_find_existing_key_returns_value(self) -> None:
        t: SplayTree[str] = SplayTree()
        t.insert(100, "cem")
        t.insert(50, "cinquenta")
        t.insert(200, "duzentos")
        self.assertEqual(t.find(100), "cem")
        self.assertEqual(t.find(50), "cinquenta")
        self.assertEqual(t.find(200), "duzentos")

    def test_find_absent_key_returns_none(self) -> None:
        t: SplayTree[str] = SplayTree()
        t.insert(10, "dez")
        self.assertIsNone(t.find(999))
        self.assertIsNone(t.find(1))

    def test_find_on_empty_tree_returns_none(self) -> None:
        t: SplayTree[str] = SplayTree()
        self.assertIsNone(t.find(1))

    def test_find_all_inserted_keys(self) -> None:
        """Todos os IDs inseridos devem ser encontrados via find()."""
        unique = sorted({3, 1, 4, 5, 9, 2, 6})
        t: SplayTree[int] = SplayTree()
        for k in unique:
            t.insert(k, k * 10)
        for k in unique:
            self.assertEqual(t.find(k), k * 10, msg=f"Falha ao buscar chave {k}")

    def test_find_after_delete(self) -> None:
        """Chave removida não deve ser encontrada; as demais devem permanecer."""
        t: SplayTree[int] = SplayTree()
        for k in range(1, 8):
            t.insert(k, k)
        t.delete(4)
        self.assertIsNone(t.find(4))
        for k in (1, 2, 3, 5, 6, 7):
            self.assertEqual(t.find(k), k, msg=f"Chave {k} perdida apos delete(4)")


# ---------------------------------------------------------------------------
# Requisito 3 — Nó encontrado vai para a raiz (splay)
# ---------------------------------------------------------------------------

class SplayTreeSplayToRootTests(unittest.TestCase):
    """Req 3 — O elemento encontrado é levado para a raiz."""

    def test_found_node_becomes_root(self) -> None:
        """Após find(k) bem-sucedido, a raiz deve ter chave k."""
        t: SplayTree[int] = SplayTree()
        for i in range(1, 16):
            t.insert(i, i)

        for key in (7, 3, 14, 1, 12):
            result = t.find(key)
            self.assertEqual(result, key)
            self.assertEqual(
                t.search_root_key(), key,
                msg=f"Apos find({key}), raiz deveria ser {key}, mas e {t.search_root_key()}"
            )

    def test_repeated_find_keeps_node_at_root(self) -> None:
        """Buscar a mesma chave duas vezes deve mante-la na raiz."""
        t: SplayTree[int] = SplayTree()
        for i in range(1, 10):
            t.insert(i, i)
        t.find(5)
        self.assertEqual(t.search_root_key(), 5)
        t.find(5)
        self.assertEqual(t.search_root_key(), 5)

    def test_root_has_no_parent_after_splay(self) -> None:
        """A raiz nunca deve ter ponteiro parent nao-nulo."""
        t: SplayTree[int] = SplayTree()
        for i in (10, 20, 5, 15, 3, 7, 12, 18):
            t.insert(i, i)
        for k in (3, 12, 7, 18, 5):
            t.find(k)
            assert t.root is not None
            self.assertIsNone(
                t.root.parent,
                msg=f"Raiz apos find({k}) tem parent nao-nulo"
            )

    def test_parent_links_consistent_after_many_splays(self) -> None:
        """Ponteiros parent devem ser internamente consistentes apos 40 splays."""
        t: SplayTree[int] = SplayTree()
        rng = random.Random(42)
        keys = rng.sample(range(1, 500), 60)
        for k in keys:
            t.insert(k, k)
        for k in rng.choices(keys, k=40):
            t.find(k)
            assert t.root is not None
            self.assertTrue(
                _parent_links_ok(t.root),
                msg=f"Ponteiros parent inconsistentes apos find({k})"
            )


# ---------------------------------------------------------------------------
# Requisito 4 — Propriedade de ABB preservada
# ---------------------------------------------------------------------------

class SplayTreeBSTInvariantTests(unittest.TestCase):
    """Req 4 — A propriedade de ABB por ID e preservada apos qualquer operacao."""

    def test_bst_after_sequential_inserts(self) -> None:
        t: SplayTree[int] = SplayTree()
        for k in (10, 5, 20, 3, 7, 15, 25):
            t.insert(k, k)
        assert t.root is not None
        self.assertTrue(_is_bst(t.root))

    def test_bst_after_random_inserts_and_searches(self) -> None:
        t: SplayTree[int] = SplayTree()
        rng = random.Random(0)
        keys = rng.sample(range(1, 200), 40)
        for k in keys:
            t.insert(k, k)
        assert t.root is not None
        self.assertTrue(_is_bst(t.root))

        for _ in range(30):
            q = rng.choice(keys)
            t.find(q)
            assert t.root is not None
            self.assertTrue(_is_bst(t.root), msg=f"ABB violada apos find({q})")

        self.assertEqual(sorted(keys), t.keys_inorder())

    def test_bst_preserved_after_delete(self) -> None:
        """Delecao nao deve quebrar a ABB; tamanho deve diminuir."""
        t: SplayTree[int] = SplayTree()
        for k in range(1, 16):
            t.insert(k, k)

        for k in (5, 10, 1, 14):
            removed = t.delete(k)
            self.assertTrue(removed, msg=f"delete({k}) deveria retornar True")
            assert t.root is not None
            self.assertTrue(_is_bst(t.root), msg=f"ABB violada apos delete({k})")
            self.assertIsNone(t.find(k), msg=f"Chave {k} ainda encontravel apos delecao")

        self.assertEqual(len(t), 11)  # 15 - 4 deletados

    def test_bst_stress_interleaved_insert_find(self) -> None:
        """Intercalar insercoes e buscas nao deve quebrar a ABB (200 operacoes)."""
        t: SplayTree[int] = SplayTree()
        rng = random.Random(99)
        inserted: list[int] = []
        for _ in range(200):
            if not inserted or rng.random() < 0.6:
                k = rng.randint(1, 1000)
                t.insert(k, k)
                if k not in inserted:
                    inserted.append(k)
            else:
                k = rng.choice(inserted)
                t.find(k)
            assert t.root is not None
            self.assertTrue(_is_bst(t.root), msg="ABB violada durante stress")


if __name__ == "__main__":
    unittest.main()
