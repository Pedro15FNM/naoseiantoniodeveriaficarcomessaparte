#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SKYLINE SKIP LIST  -  MVP beta
Interface de visualização do dataset iNaturalist como um plataforma 2D.

ESTRUTURAS DE DADOS
  * Skip List (linear)      -> cada registro é um nó; nó de nível L = prédio de L andares.
  * Árvore AVL (hierárquica)-> indexa as categorias; sorteia o "prédio objetivo".

MODIFICAÇÕES NOS ALGORITMOS CLÁSSICOS (pontos de discussão na apresentação)
  1. Skip List: a busca clássica foi REMOVIDA. A travessia é feita pelo jogador,
     ponteiro a ponteiro (SkipList.next_at).
  2. Skip List: inserção clássica (busca + update[]) substituída por CARGA EM LOTE
     O(n) com vetor `tails[]` (sem nenhuma busca), pois os registros chegam ordenados.
  3. Skip List: cada nó guarda `idx` (posição ordinal). Serve de coordenada do cenário
     e de chave do culling.
  4. Skip List: `scan_window` é uma busca "modificada" usada SÓ para renderização:
     descida por níveis até a borda esquerda da câmera + varredura horizontal por
     nível até a borda direita. Custo O(log n + elementos visíveis) -> culling real.
  5. AVL: aumentada com `size` (nº de categorias na subárvore) => seleção por ordem
     (order-statistic). Sorteia uma categoria uniformemente em O(log n), sem percorrer.
  6. AVL: chaves duplicadas não criam nó; o registro entra no "bucket" da categoria.

Execução:  python skyline_skiplist.py            (usa DATASET_PATH ou fallback)
           python skyline_skiplist.py --fake 10000   (teste de estresse)
Controles: ↑/↓ (W/S) sobem/descem andar | ESPAÇO/→/D pega a tirolesa
           R reinicia | N novo objetivo | C legenda | F1 debug | ESC sai
"""

import colorsys
import csv
import math
import os
import random
import sys

import pygame

# =============================================================================
# CONFIGURAÇÕES GLOBAIS (injeção de assets)
# =============================================================================
DATASET_PATH = "data/inaturalist_observations.csv"  # CSV exportado do iNaturalist
BG_IMAGE_PATH = "assets/background.png"  # imagem de fundo (opcional)
BG_FALLBACK_COLOR = (22, 30, 56)  # cor sólida se não houver imagem
FALLBACK_NODES = 500  # nós fictícios se não houver CSV
MAX_RECORDS = 20000  # limite de leitura do CSV (None = tudo)
RANDOM_SEED = None  # defina um int para reprodutibilidade

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

SKIP_P = 0.5  # probabilidade de promoção de nível
MAX_LEVEL = 12  # nível máximo (~log2(n) para n = 4096+; suficiente para 10k+)

# Layout do cenário (coordenadas de mundo)
FLOOR_H = 40  # altura de um andar
BUILD_W = 64  # largura de um prédio
SPACING = 120  # distância horizontal entre prédios
X0 = 200  # x do prédio 0 (INÍCIO)
GROUND_Y = 640  # y (tela) do chão

LEVEL_COLORS = [
    (255, 214, 102),
    (255, 159, 67),
    (255, 107, 107),
    (238, 90, 200),
    (162, 120, 255),
    (90, 160, 255),
    (72, 214, 232),
    (80, 220, 160),
    (170, 230, 90),
    (240, 240, 120),
    (255, 255, 255),
    (200, 200, 200),
]

ICONIC_TAXA = [
    "Aves",
    "Mammalia",
    "Reptilia",
    "Amphibia",
    "Actinopterygii",
    "Insecta",
    "Arachnida",
    "Mollusca",
    "Plantae",
    "Fungi",
    "Protozoa",
    "Animalia",
]


# =============================================================================
# DADOS: leitura do CSV e fallback fictício
# =============================================================================
def generate_fake_records(n, rng):
    """Gera n registros fictícios já ordenados por chave (ids crescentes)."""
    adj = [
        "Veloz",
        "Dourado",
        "Sombrio",
        "Gigante",
        "Miúdo",
        "Listrado",
        "Noturno",
        "Azul",
    ]
    ani = [
        "Jaguar",
        "Tucano",
        "Sapo",
        "Borboleta",
        "Tartaruga",
        "Aranha",
        "Lobo",
        "Peixe",
    ]
    recs, key = [], 0
    for _ in range(n):
        key += rng.randint(1, 40)
        a, b = rng.choice(adj), rng.choice(ani)
        recs.append((key, f"{b} {a}", f"Fictus {b.lower()}", rng.choice(ICONIC_TAXA)))
    return recs


def _pick(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None


def load_csv(path):
    """Lê o CSV do iNaturalist tolerando variações de nomes de colunas."""
    recs = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return recs
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
        cols = set(reader.fieldnames)
        c_id = _pick(cols, ("id", "observation_id", "taxon_id"))
        c_name = _pick(
            cols, ("common_name", "taxon_common_name", "species_guess", "name")
        )
        c_sci = _pick(cols, ("scientific_name", "taxon_scientific_name"))
        c_cat = _pick(
            cols,
            (
                "iconic_taxon_name",
                "taxon_iconic_group_name",
                "iconic_taxon",
                "category",
                "taxon_kingdom_name",
            ),
        )
        for n, row in enumerate(reader, start=1):
            if MAX_RECORDS and n > MAX_RECORDS:
                break
            try:
                key = int(row[c_id]) if c_id else n
            except (ValueError, TypeError):
                key = n
            sci = (row.get(c_sci) or "").strip() if c_sci else ""
            name = (row.get(c_name) or "").strip() if c_name else ""
            cat = (row.get(c_cat) or "").strip() if c_cat else ""
            recs.append(
                (key, name or sci or f"Registro {key}", sci, cat or "Sem categoria")
            )
    return recs


def load_records(rng, fake_n=None):
    if fake_n:
        print(f"[dados] modo estresse: {fake_n} nós fictícios")
        return generate_fake_records(fake_n, rng)
    if os.path.isfile(DATASET_PATH):
        try:
            recs = load_csv(DATASET_PATH)
            if recs:
                print(f"[dados] {len(recs)} registros lidos de {DATASET_PATH}")
                return recs
        except Exception as exc:  # CSV corrompido -> cai no fallback
            print(f"[dados] erro lendo CSV ({exc}); usando fallback")
    print(f"[dados] CSV não encontrado; gerando {FALLBACK_NODES} nós fictícios")
    return generate_fake_records(FALLBACK_NODES, rng)


# =============================================================================
# ESTRUTURA LINEAR: SKIP LIST
# =============================================================================
class SkipNode:
    """Nó da Skip List. `forward[i]` é o ponteiro do nível i (andar i do prédio)."""

    __slots__ = ("idx", "key", "name", "sci", "category", "level", "forward", "color")

    def __init__(self, idx, key, name, sci, category, level):
        self.idx = idx  # posição ordinal (coordenada X do prédio)
        self.key = key  # chave de ordenação (id do iNaturalist)
        self.name, self.sci, self.category = name, sci, category
        self.level = level  # nº de níveis == nº de andares do prédio
        self.forward = [None] * level
        self.color = (120, 120, 140)


class SkipList:
    """Skip List probabilística SEM busca pública: quem navega é o jogador."""

    def __init__(self, rng):
        self.rng = rng
        # Sentinela: nível máximo, vira o prédio de INÍCIO (idx 0).
        self.head = SkipNode(0, -1, "INÍCIO", "", "—", MAX_LEVEL)
        self.level = 1  # maior nível efetivamente em uso
        self.size = 0

    def _random_level(self):
        lvl = 1
        while lvl < MAX_LEVEL and self.rng.random() < SKIP_P:
            lvl += 1
        return lvl

    def bulk_load(self, records):
        """MODIFICAÇÃO: carga em lote O(n) sem busca.
        `tails[l]` guarda o último nó já ligado em cada nível; como os registros
        chegam ordenados, basta encadear no fim (substitui o update[] da inserção
        clássica, que exigiria uma busca por registro)."""
        tails = [self.head] * MAX_LEVEL
        nodes = []
        for i, (key, name, sci, cat) in enumerate(records, start=1):
            node = SkipNode(i, key, name, sci, cat, self._random_level())
            for l in range(node.level):
                tails[l].forward[l] = node
                tails[l] = node
            if node.level > self.level:
                self.level = node.level
            nodes.append(node)
        self.size = len(nodes)
        return nodes

    def height_of(self, node):
        """Altura do prédio (o INÍCIO mostra só os níveis em uso)."""
        return self.level if node is self.head else node.level

    @staticmethod
    def next_at(node, level):
        """Ponteiro de avanço daquele nível (ou None). Único meio de travessia do jogo."""
        return node.forward[level] if level < len(node.forward) else None

    def scan_window(self, lo, hi):
        """MODIFICAÇÃO (apenas renderização): culling pela própria estrutura.
        1) desce do nível mais alto ao 0 parando no último nó com idx < lo;
        2) em cada nível varre para a direita até idx > hi coletando ponteiros.
        Inclui tirolesas que nascem fora da tela mas cruzam a câmera.
        Retorna (prédios_visíveis, [(origem, nível, destino), ...])."""
        buildings, edges = [], []
        x = self.head
        for l in range(self.level - 1, -1, -1):
            while x.forward[l] is not None and x.forward[l].idx < lo:
                x = x.forward[l]
            n = x
            while n is not None and n.idx <= hi:
                nxt = n.forward[l]
                if nxt is not None:
                    edges.append((n, l, nxt))
                if l == 0 and n.idx >= lo:
                    buildings.append(n)
                n = nxt
        return buildings, edges


# =============================================================================
# ESTRUTURA HIERÁRQUICA: AVL DE CATEGORIAS (aumentada com `size`)
# =============================================================================
class AVLNode:
    __slots__ = ("key", "bucket", "left", "right", "height", "size", "color")

    def __init__(self, key, color):
        self.key = key  # categoria (ex.: "Aves")
        self.bucket = []  # nós da Skip List dessa categoria
        self.left = self.right = None
        self.height = 1
        self.size = 1  # nº de categorias (nós AVL) na subárvore
        self.color = color


def _h(n):
    return n.height if n else 0


def _sz(n):
    return n.size if n else 0


def _update(n):
    n.height = 1 + max(_h(n.left), _h(n.right))
    n.size = 1 + _sz(n.left) + _sz(n.right)  # manutenção do campo aumentado


def _rot_right(y):
    x = y.left
    y.left, x.right = x.right, y
    _update(y)
    _update(x)
    return x


def _rot_left(x):
    y = x.right
    x.right, y.left = y.left, x
    _update(x)
    _update(y)
    return y


def _balance(n):
    _update(n)
    bf = _h(n.left) - _h(n.right)
    if bf > 1:
        if _h(n.left.left) < _h(n.left.right):
            n.left = _rot_left(n.left)
        return _rot_right(n)
    if bf < -1:
        if _h(n.right.right) < _h(n.right.left):
            n.right = _rot_right(n.right)
        return _rot_left(n)
    return n


class CategoryAVL:
    """AVL paralela à Skip List: chave = categoria, valor = bucket de nós."""

    def __init__(self):
        self.root = None
        self._last = None
        self._count = 0

    def _new_color(self):
        hue = (self._count * 0.61803398875) % 1.0  # cores bem espaçadas
        self._count += 1
        r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.85)
        return int(r * 255), int(g * 255), int(b * 255)

    def insert(self, category, skip_node):
        self.root = self._insert(self.root, category, skip_node)
        return self._last  # AVLNode onde o registro entrou

    def _insert(self, n, key, item):
        if n is None:
            new = AVLNode(key, self._new_color())
            new.bucket.append(item)
            self._last = new
            return new
        if key < n.key:
            n.left = self._insert(n.left, key, item)
        elif key > n.key:
            n.right = self._insert(n.right, key, item)
        else:  # MODIFICAÇÃO: duplicata vai pro bucket, sem rotação
            n.bucket.append(item)
            self._last = n
            return n
        return _balance(n)

    def select(self, k):
        """k-ésima categoria em ordem (0-based) em O(log n) usando `size`."""
        n = self.root
        while n:
            ls = _sz(n.left)
            if k < ls:
                n = n.left
            elif k == ls:
                return n
            else:
                k -= ls + 1
                n = n.right
        return None

    def random_target(self, rng):
        """Sorteia categoria (uniforme entre categorias) e um animal dentro dela."""
        if not self.root:
            return None
        cat = self.select(rng.randrange(self.root.size))
        return cat.key, rng.choice(cat.bucket)

    def inorder(self):
        out, stack, cur = [], [], self.root
        while stack or cur:
            while cur:
                stack.append(cur)
                cur = cur.left
            cur = stack.pop()
            out.append(cur)
            cur = cur.right
        return out


# =============================================================================
# JOGO
# =============================================================================
def world_x(idx):
    return X0 + idx * SPACING


def star_points(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(n * 2):
        ang = -math.pi / 2 + i * math.pi / n
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


class Game:
    def __init__(self, screen, records, rng):
        self.screen = screen
        self.rng = rng
        self.clock = pygame.time.Clock()

        # ---- Estruturas de dados ----
        records = sorted(records, key=lambda r: r[0])  # Skip List exige ordem por chave
        self.sl = SkipList(rng)
        nodes = self.sl.bulk_load(records)
        self.avl = CategoryAVL()
        for node in nodes:  # indexação hierárquica paralela
            node.color = self.avl.insert(node.category, node).color
        self.sl.head.color = (90, 100, 130)
        self.legend = [(a.key, len(a.bucket), a.color) for a in self.avl.inorder()]

        # ---- Recursos visuais ----
        self.f_s = pygame.font.SysFont("dejavusans,arial", 12)
        self.f_m = pygame.font.SysFont("dejavusans,arial", 16)
        self.f_b = pygame.font.SysFont("dejavusans,arial", 30, bold=True)
        self.digits = [
            self.f_s.render(str(i), True, (20, 20, 30)) for i in range(1, MAX_LEVEL + 1)
        ]
        self.label_cache = {}
        self.bg = self._load_bg()
        self.show_legend = False
        self.show_debug = False
        self.dbg = (0, 0)

        self.new_round(new_goal=True)
        self.cam_x = self.p_x - SCREEN_W / 2

    # ---------------- fundo ----------------
    def _load_bg(self):
        if os.path.isfile(BG_IMAGE_PATH):
            try:
                img = pygame.image.load(BG_IMAGE_PATH).convert()
                w = max(1, int(img.get_width() * SCREEN_H / img.get_height()))
                return pygame.transform.smoothscale(img, (w, SCREEN_H))
            except pygame.error:
                pass
        return None

    # ---------------- rodada ----------------
    def new_round(self, new_goal):
        if new_goal or not hasattr(self, "goal"):
            # AVL define o prédio objetivo (sorteio por ordem estatística)
            self.goal_cat, self.goal = self.avl.random_target(self.rng)
        self.node = self.sl.head
        self.floor = 0
        self.moves = 0
        self.state = "play"  # play | won | lost
        self.msg = ""
        self.p_x = world_x(0) + BUILD_W / 2
        self.p_y = self._feet_y(0)

    def _feet_y(self, floor):
        return GROUND_Y - floor * FLOOR_H - 4

    # ---------------- ações do jogador ----------------
    def change_floor(self, d):
        if self.state != "play":
            return
        top = self.sl.height_of(self.node) - 1
        self.floor = max(0, min(top, self.floor + d))

    def take_zip(self):
        if self.state != "play":
            return
        tgt = self.sl.next_at(self.node, self.floor)  # travessia manual: 1 ponteiro
        if tgt is None:
            self.msg = "Sem tirolesa neste andar (fim da lista neste nível)."
            return
        self.node = tgt
        self.moves += 1
        self.msg = ""
        if tgt is self.goal:
            self.state = "won"
        elif tgt.idx > self.goal.idx:
            self.state = "lost"  # listas só avançam: passou do alvo

    # ---------------- atualização ----------------
    def update(self, dt):
        k = min(1.0, dt * 9)
        self.p_x += (world_x(self.node.idx) + BUILD_W / 2 - self.p_x) * k
        self.p_y += (self._feet_y(self.floor) - self.p_y) * k
        self.cam_x += (self.p_x - SCREEN_W / 2 - self.cam_x) * min(1.0, dt * 8)

    # ---------------- renderização ----------------
    def draw_background(self):
        if self.bg is None:
            self.screen.fill(BG_FALLBACK_COLOR)
        else:
            bw = self.bg.get_width()
            off = -int(self.cam_x * 0.25) % bw
            x = off - bw
            while x < SCREEN_W:
                self.screen.blit(self.bg, (x, 0))
                x += bw
        pygame.draw.rect(
            self.screen, (30, 34, 44), (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y)
        )
        pygame.draw.line(
            self.screen, (90, 96, 110), (0, GROUND_Y), (SCREEN_W, GROUND_Y), 3
        )

    def draw_zip(self, src, lvl, dst):
        cam = self.cam_x
        y = GROUND_Y - lvl * FLOOR_H - FLOOR_H // 2
        sx = world_x(src.idx) + BUILD_W - cam
        ex = world_x(dst.idx) - cam
        active = src is self.node and lvl == self.floor and self.state == "play"
        col = LEVEL_COLORS[lvl % len(LEVEL_COLORS)]
        x1, x2 = max(sx, -20), min(ex, SCREEN_W + 20)  # clipping horizontal
        if x2 > x1:
            pygame.draw.line(
                self.screen,
                (255, 255, 255) if active else col,
                (x1, y),
                (x2, y),
                4 if active else 2,
            )
        if -10 < sx < SCREEN_W + 10:
            pygame.draw.circle(self.screen, col, (int(sx), y), 4)
        if -10 < ex < SCREEN_W + 10:
            pygame.draw.circle(self.screen, col, (int(ex), y), 4)

    def label(self, node):
        s = self.label_cache.get(node.idx)
        if s is None:
            if len(self.label_cache) > 600:
                self.label_cache.clear()
            s = (
                self.f_s.render(f"#{node.idx}", True, (170, 176, 190)),
                self.f_s.render(node.name[:12], True, (210, 214, 224)),
            )
            self.label_cache[node.idx] = s
        return s

    def draw_building(self, node):
        h = self.sl.height_of(node)
        sx = world_x(node.idx) - self.cam_x
        top = GROUND_Y - h * FLOOR_H
        body = pygame.Rect(int(sx), top, BUILD_W, h * FLOOR_H)
        pygame.draw.rect(self.screen, shade(node.color, 0.45), body)
        is_player = node is self.node
        for f in range(h):
            fy = GROUND_Y - (f + 1) * FLOOR_H
            win = pygame.Rect(int(sx) + 4, fy + 4, BUILD_W - 8, FLOOR_H - 8)
            hot = is_player and f == self.floor and self.state == "play"
            pygame.draw.rect(
                self.screen,
                (255, 245, 170) if hot else node.color,
                win,
                border_radius=3,
            )
            self.screen.blit(self.digits[f], (win.x + 4, win.y + 3))
            if self.sl.next_at(node, f) is None and node is not self.sl.head:
                pygame.draw.line(
                    self.screen,
                    (40, 40, 50),
                    (win.right - 10, win.y + 4),
                    (win.right - 4, win.y + 10),
                    2,
                )
        if node is self.goal:
            pygame.draw.rect(self.screen, (255, 215, 0), body.inflate(8, 8), 4)
            pygame.draw.polygon(
                self.screen,
                (255, 215, 0),
                star_points(sx + BUILD_W / 2, top - 22, 14, 6),
            )
        elif is_player:
            pygame.draw.rect(self.screen, (255, 255, 255), body.inflate(4, 4), 2)
        l1, l2 = self.label(node)
        cx = sx + BUILD_W / 2
        self.screen.blit(l1, (cx - l1.get_width() / 2, GROUND_Y + 6))
        self.screen.blit(l2, (cx - l2.get_width() / 2, GROUND_Y + 20))

    def draw_player(self):
        px, py = self.p_x - self.cam_x, self.p_y
        pygame.draw.rect(
            self.screen, (235, 80, 70), (px - 6, py - 20, 12, 18), border_radius=3
        )
        pygame.draw.circle(self.screen, (250, 220, 180), (int(px), int(py - 26)), 6)

    def draw_minimap(self):
        x0, x1, y = 40, SCREEN_W - 40, 692
        pygame.draw.rect(
            self.screen, (60, 66, 82), (x0, y, x1 - x0, 6), border_radius=3
        )
        n = max(1, self.sl.size)
        mx = lambda i: x0 + (x1 - x0) * i / n
        pygame.draw.polygon(
            self.screen, (255, 215, 0), star_points(mx(self.goal.idx), y + 3, 9, 4)
        )
        pygame.draw.circle(
            self.screen, (255, 255, 255), (int(mx(self.node.idx)), y + 3), 6
        )
        self.screen.blit(
            self.f_s.render(f"{self.sl.size} nós", True, (150, 156, 170)),
            (x1 - 50, y + 10),
        )

    def text(self, s, pos, font=None, color=(235, 238, 245)):
        self.screen.blit((font or self.f_m).render(s, True, color), pos)

    def draw_hud(self):
        panel = pygame.Surface((560, 104), pygame.SRCALPHA)
        panel.fill((10, 12, 20, 170))
        self.screen.blit(panel, (8, 8))
        g = self.goal
        self.text(
            f"ALVO: {g.name}  [{g.category}]  — prédio #{g.idx}",
            (18, 14),
            color=(255, 215, 0),
        )
        self.text(
            f"Movimentos: {self.moves}     Prédio atual: #{self.node.idx}  andar {self.floor + 1}",
            (18, 38),
        )
        n = self.node
        self.text(
            f"{n.name}  |  {n.sci or '—'}  |  {n.category}",
            (18, 60),
            self.f_s,
            (190, 196, 210),
        )
        tgt = self.sl.next_at(n, self.floor)
        info = (
            f"Tirolesa do andar {self.floor + 1}: → #{tgt.idx} {tgt.name[:18]} (+{tgt.idx - n.idx} prédios)"
            if tgt
            else f"Andar {self.floor + 1}: sem tirolesa (fim da lista neste nível)"
        )
        self.text(
            info, (18, 80), self.f_s, LEVEL_COLORS[self.floor % len(LEVEL_COLORS)]
        )
        dist = self.goal.idx - n.idx
        self.text(
            f"Alvo a {dist} prédios à frente" if dist > 0 else "",
            (380, 60),
            self.f_s,
            (255, 215, 0),
        )
        if self.msg:
            self.text(self.msg, (18, 116), self.f_s, (255, 140, 140))

        help_ = [
            "↑/↓ andar   ESPAÇO/→ tirolesa",
            "R reinicia  N novo alvo",
            "C legenda  F1 debug",
        ]
        for i, h in enumerate(help_):
            s = self.f_s.render(h, True, (200, 205, 220))
            self.screen.blit(s, (SCREEN_W - s.get_width() - 14, 12 + i * 16))
        if self.show_legend:
            y = 70
            for cat, cnt, col in self.legend:
                pygame.draw.rect(self.screen, col, (SCREEN_W - 190, y, 12, 12))
                self.text(f"{cat[:18]} ({cnt})", (SCREEN_W - 172, y - 3), self.f_s)
                y += 16
        if self.show_debug:
            vb, ve = self.dbg
            self.text(
                f"FPS {self.clock.get_fps():.0f} | prédios renderizados {vb} | tirolesas {ve} "
                f"| total {self.sl.size} | nível máx {self.sl.level}",
                (10, SCREEN_H - 22),
                self.f_s,
                (120, 255, 160),
            )

    def draw_overlay(self):
        if self.state == "play":
            return
        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        self.screen.blit(veil, (0, 0))
        won = self.state == "won"
        title = "VITÓRIA!" if won else "VOCÊ PASSOU DO ALVO"
        sub = (
            f"Chegou em {self.moves} movimentos."
            if won
            else "A Skip List só avança: tente outro caminho de tirolesas."
        )
        t = self.f_b.render(title, True, (120, 255, 160) if won else (255, 120, 120))
        self.screen.blit(t, (SCREEN_W / 2 - t.get_width() / 2, 260))
        s = self.f_m.render(
            sub + "   [R] repetir  [N] novo alvo", True, (235, 238, 245)
        )
        self.screen.blit(s, (SCREEN_W / 2 - s.get_width() / 2, 310))

    def draw(self):
        self.draw_background()
        # Culling: só o que intersecta a câmera é coletado da Skip List.
        lo = max(0, int((self.cam_x - X0) // SPACING) - 1)
        hi = int((self.cam_x + SCREEN_W - X0) // SPACING) + 1
        buildings, edges = self.sl.scan_window(lo, hi)
        self.dbg = (len(buildings), len(edges))
        for src, lvl, dst in edges:  # tirolesas atrás dos prédios
            self.draw_zip(src, lvl, dst)
        for b in buildings:
            self.draw_building(b)
        self.draw_player()
        self.draw_minimap()
        self.draw_hud()
        self.draw_overlay()
        pygame.display.flip()

    # ---------------- loop ----------------
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key in (pygame.K_UP, pygame.K_w):
            self.change_floor(+1)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.change_floor(-1)
        elif key in (pygame.K_SPACE, pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN):
            self.take_zip()
        elif key == pygame.K_r:
            self.new_round(new_goal=False)
        elif key == pygame.K_n:
            self.new_round(new_goal=True)
        elif key == pygame.K_c:
            self.show_legend = not self.show_legend
        elif key == pygame.K_F1:
            self.show_debug = not self.show_debug
        return True

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    running = self.handle_key(ev.key) and running
            self.update(dt)
            self.draw()
        pygame.quit()


def main():
    fake_n = None
    if "--fake" in sys.argv:
        try:
            fake_n = int(sys.argv[sys.argv.index("--fake") + 1])
        except (IndexError, ValueError):
            fake_n = 10000
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Skyline Skip List — iNaturalist")
    rng = random.Random(RANDOM_SEED)
    Game(screen, load_records(rng, fake_n), rng).run()


if __name__ == "__main__":
    main()
