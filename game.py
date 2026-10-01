"""Regras de gameplay (sem Pygame)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import colorsys

from animal import AnimalRecord
from database import (
    DatabaseError,
    all_taxonomic_classes,
    load_animal_tree,
    build_fake_tree,
)
from skip_list import BuildingNode, ScenarioSkipList
from splay_tree import SplayTree

MAX_ENERGY = 10


class GameState(str, Enum):
    PLAYING = "playing"
    GAME_OVER = "game_over"
    TARGET_REACHED = "target_reached"
    COMBAT_WIN = "combat_win"
    COMBAT_LOSE = "combat_lose"


@dataclass
class GameSession:
    """Estado de uma partida."""

    tree: SplayTree[AnimalRecord]
    scenario: ScenarioSkipList
    rng: random.Random
    max_energy: int = MAX_ENERGY
    energy: int | None = None
    current_node: BuildingNode | None = None
    current_level: int = 0
    target: AnimalRecord | None = None
    state: GameState = GameState.PLAYING
    message: str = ""
    moves: int = 0
    victories: int = 0
    _id_keys: list[int] = field(default_factory=list)
    _coin_flip: Callable[[], bool] | None = None

    def __post_init__(self) -> None:
        if self.energy is None:
            self.energy = self.max_energy
        if self.current_node is None:
            self.current_node = self.scenario.head
        if not self._id_keys:
            self._id_keys = self.tree.keys_inorder()
        if self.target is None and self.state == GameState.PLAYING:
            self.start_new_turn()

    @classmethod
    def create(
        cls,
        rng: random.Random,
        *,
        fake_n: int | None = None,
        force_rebuild_db: bool = False,
        max_energy: int = MAX_ENERGY,
    ) -> GameSession:
        if fake_n:
            tree = build_fake_tree(fake_n, rng)
        else:
            tree = load_animal_tree(force_rebuild=force_rebuild_db)
        classes = sorted(all_taxonomic_classes(tree))
        scenario = ScenarioSkipList(rng)
        nodes = scenario.bulk_load_classes(classes)
        _assign_building_colors(nodes)
        missing = all_taxonomic_classes(tree) - scenario.classes_present()
        if missing:
            raise DatabaseError(
                "Classes sem prédio na Skip List: " + ", ".join(sorted(missing))
            )
        return cls(tree=tree, scenario=scenario, rng=rng, max_energy=max_energy)

    def set_coin_flip(self, fn: Callable[[], bool] | None) -> None:
        self._coin_flip = fn

    def _flip_coin(self) -> bool:
        if self._coin_flip is not None:
            return self._coin_flip()
        return self.rng.choice([True, False])

    def start_new_turn(self) -> None:
        if not self._id_keys:
            self._id_keys = self.tree.keys_inorder()
        if not self._id_keys:
            raise DatabaseError("Splay Tree vazia: impossível sortear alvo.")
        chosen_id = self.rng.choice(self._id_keys)
        animal = self.tree.find(chosen_id)
        if animal is None:
            raise DatabaseError(f"ID sorteado ausente na árvore: {chosen_id}")
        self.target = animal
        self.current_node = self.scenario.head
        self.current_level = 0
        self.energy = self.max_energy
        self.moves = 0
        self.state = GameState.PLAYING
        self.message = ""

    def change_floor(self, delta: int) -> None:
        if self.state != GameState.PLAYING or self.current_node is None or self.energy <= 0:
            return
        top = self.scenario.height_of(self.current_node) - 1
        self.current_level = max(0, min(top, self.current_level + delta))

    def try_move_at_level(self, level: int | None = None) -> bool:
        """Consome exatamente 1 energia por ponteiro atravessado na Skip List."""
        if self.state != GameState.PLAYING or self.current_node is None or self.energy <= 0:
            return False
        lvl = self.current_level if level is None else level
        if not self.scenario.can_move(self.current_node, self.current_level, lvl):
            self.message = "Sem tirolesa neste andar."
            return False
        nxt = self.scenario.move(self.current_node, self.current_level, lvl)
        if nxt is None:
            return False
        self.current_node = nxt
        self.moves += 1
        self.energy -= 1
        self.message = ""
        self._after_move()
        return True

    def take_zip_line(self) -> bool:
        return self.try_move_at_level(None)

    def _after_move(self) -> None:
        if self.current_node is None or self.target is None:
            return
        if self._at_target_building():
            self._resolve_combat()
            return
        if self.energy <= 0:
            self.state = GameState.GAME_OVER
            self.message = "Você ficou sem energia antes de alcançar o alvo. Game Over."

    def _at_target_building(self) -> bool:
        if self.current_node is None or self.target is None:
            return False
        if self.current_node is self.scenario.head:
            return False
        return self.current_node.animal_class == self.target.taxonomic_class

    def _resolve_combat(self) -> None:
        """Interrompe a navegação e resolve o combate na moeda 50/50."""
        won = self._flip_coin()
        if won:
            self.victories += 1
            self.start_new_turn()
            self.message = "Vitória no combate da moeda (50/50)! Alvo anterior concluído. Novo turno iniciado!"
        else:
            self.state = GameState.GAME_OVER
            self.message = "Derrota no combate da moeda (50/50). Game Over imediato."

    def restart_turn(self) -> None:
        """Reinicia posição mantendo o mesmo alvo."""
        self.current_node = self.scenario.head
        self.current_level = 0
        self.energy = self.max_energy
        self.moves = 0
        self.state = GameState.PLAYING
        self.message = ""

    def new_target(self) -> None:
        self.start_new_turn()

    def target_class_label(self) -> str:
        if self.target is None:
            return "—"
        return self.target.taxonomic_class


def _assign_building_colors(nodes: list[BuildingNode]) -> None:
    for i, node in enumerate(nodes):
        hue = (i * 0.61803398875) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.85)
        node.color = (int(r * 255), int(g * 255), int(b * 255))
