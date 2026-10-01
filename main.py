#!/usr/bin/env python3
"""Skyline Skip List — ponto de entrada Pygame."""

from __future__ import annotations

import random
import sys

import pygame

from database import DatabaseError
from game import GameSession
from ui import PygameApp, SCREEN_H, SCREEN_W

RANDOM_SEED = None


def _parse_fake_arg(argv: list[str]) -> int | None:
    if "--fake" not in argv:
        return None
    try:
        return int(argv[argv.index("--fake") + 1])
    except (IndexError, ValueError):
        return 10000


def _parse_energy_arg(argv: list[str]) -> int | None:
    if "--energy" not in argv:
        return None
    try:
        return int(argv[argv.index("--energy") + 1])
    except (IndexError, ValueError):
        return None


def main() -> None:
    fake_n = _parse_fake_arg(sys.argv)
    energy_arg = _parse_energy_arg(sys.argv)
    force_rebuild = "--rebuild-db" in sys.argv
    rng = random.Random(RANDOM_SEED)
    try:
        create_kwargs = {}
        if energy_arg is not None:
            create_kwargs["max_energy"] = energy_arg
        session = GameSession.create(
            rng,
            fake_n=fake_n,
            force_rebuild_db=force_rebuild,
            **create_kwargs,
        )
    except DatabaseError as exc:
        print(f"[erro] {exc}", file=sys.stderr)
        sys.exit(1)
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Skyline Skip List — iNaturalist")
    PygameApp(screen, session).run()


if __name__ == "__main__":
    main()
