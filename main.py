#!/usr/bin/env python3
"""The world in one day: Saturday 21 November 2026.

Entry program for make.fun's news-image-20261121 bounty
("Sum up 21 November's world news in one image", program/v1).

The program paints a 1024x1024 broadsheet-style poster with the
Python standard library alone: a flat RGB raster, a compact 5x7
bitmap typeface stored as row bitmasks, and a hand-rolled PNG
writer. It writes the picture to /output/entry.png, or to the
folder named by MAKEFUN_OUTPUT_DIR for local runs. There is no
clock, no randomness and no network access, so repeated runs
produce exactly the same bytes.

The front page, as reported on 21 November 2026 (SOURCES.md has
the detail): COP31 in Antalya runs into overtime with no deal
and a draft that drops fossil fuels; a Russian missile comes
down in Poland and Warsaw calls it a provocation; Anthropic
slides a day after its record debut as the AI sell-off deepens;
a strike on Kryvyi Rih kills two and injures 42; ESA and JAXA's
BepiColombo reaches Mercury after eight years; a vendor data
breach exposes Chase, Visa and Mastercard customer details;
and President Trump threatens a ban on US firms building AI
data centres overseas.
"""

import os
import struct
import zlib
from binascii import crc32

SIZE = 1024

# Broadsheet palette.
PAPER = (243, 239, 230)
CARD = (255, 255, 255)
INK = (18, 29, 40)
MUTE = (70, 80, 92)
GOLD = (233, 183, 72)
RED = (186, 48, 38)
BLUE = (33, 82, 158)
ORANGE = (211, 116, 22)
PURPLE = (98, 62, 158)
TEAL = (12, 118, 106)
DEEP = (35, 51, 116)


# Each glyph is seven rows of five pixels, packed as bitmasks
# (bit 4 is the leftmost pixel of a row).
GLYPHS = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (28, 18, 17, 17, 17, 18, 28),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10),
    "X": (17, 10, 4, 4, 4, 10, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (14, 16, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 1, 14),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8),
    "-": (0, 0, 0, 31, 0, 0, 0),
    ":": (0, 12, 12, 0, 12, 12, 0),
    "'": (4, 4, 8, 0, 0, 0, 0),
    "+": (0, 4, 4, 31, 4, 4, 0),
    "$": (4, 15, 20, 14, 5, 30, 4),
    "%": (24, 25, 2, 4, 8, 19, 3),
    "/": (1, 1, 2, 4, 8, 16, 16),
    "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 2, 4, 0, 4),
}


class Page:
    """A square RGB raster with rectangle, disc and text tools."""

    def __init__(self, side, ground):
        self.side = side
        self.buf = bytearray(ground * (side * side))

    def put(self, x, y, colour):
        if 0 <= x < self.side and 0 <= y < self.side:
            at = (y * self.side + x) * 3
            self.buf[at:at + 3] = bytes(colour)

    def rect(self, x, y, w, h, colour):
        top = max(0, y)
        bottom = min(self.side, y + h)
        left = max(0, x)
        right = min(self.side, x + w)
        if left >= right:
            return
        run = bytes(colour) * (right - left)
        for row in range(top, bottom):
            at = (row * self.side + left) * 3
            self.buf[at:at + len(run)] = run

    def frame(self, x, y, w, h, colour, thick=3):
        self.rect(x, y, w, thick, colour)
        self.rect(x, y + h - thick, w, thick, colour)
        self.rect(x, y, thick, h, colour)
        self.rect(x + w - thick, y, thick, h, colour)

    def disc(self, cx, cy, radius, colour):
        limit = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= limit:
                    self.put(x, y, colour)

    @staticmethod
    def measure(text, scale):
        return len(text) * 6 * scale - scale if text else 0

    def write(self, text, x, y, scale, colour):
        pen = x
        for ch in text.upper():
            rows = GLYPHS.get(ch, GLYPHS[" "])
            for r, bits in enumerate(rows):
                for c in range(5):
                    if bits & (1 << (4 - c)):
                        self.rect(pen + c * scale, y + r * scale,
                                  scale, scale, colour)
            pen += 6 * scale
        return pen - scale

    def write_mid(self, text, centre, y, scale, colour):
        return self.write(text, centre - self.measure(text, scale) // 2,
                          y, scale, colour)


def story_card(page, x, y, w, h, accent, kicker, head, body):
    """A white news card: accent strip, section tag, headline, notes."""
    page.rect(x, y, w, h, CARD)
    page.frame(x, y, w, h, INK)
    page.rect(x, y, w, 10, accent)
    page.write(kicker, x + 22, y + 22, 2, accent)
    line_y = y + 44
    for line in head:
        page.write(line, x + 22, line_y, 4, INK)
        line_y += 36
    note_y = y + 114
    for line in body:
        page.write(line, x + 22, note_y, 2, MUTE)
        note_y += 19


def front_page():
    page = Page(SIZE, PAPER)

    # Masthead band naming the day.
    page.rect(0, 0, SIZE, 124, INK)
    page.write_mid("THE WORLD IN ONE DAY", SIZE // 2, 10, 2, GOLD)
    page.write_mid("21 NOVEMBER 2026", SIZE // 2, 30, 7, CARD)
    page.write_mid("SATURDAY - ONE DAY - ONE IMAGE - THE NEWS THAT MATTERED",
                   SIZE // 2, 88, 2, GOLD)

    # Lead story: the climate summit that would not finish.
    hx, hy, hw, hh = 16, 136, 992, 140
    page.rect(hx, hy, hw, hh, CARD)
    page.frame(hx, hy, hw, hh, INK)
    page.rect(hx, hy, hw, 10, TEAL)
    page.disc(hx + 76, hy + 76, 42, TEAL)
    page.write_mid("COP31", hx + 76, hy + 62, 2, CARD)
    page.write("ANTALYA - CLIMATE SUMMIT", hx + 148, hy + 20, 2, TEAL)
    page.write("COP31 TALKS GO INTO", hx + 148, hy + 40, 5, INK)
    page.write("OVERTIME - NO DEAL YET", hx + 148, hy + 82, 5, INK)
    page.write("200 NATIONS MISS FRIDAY DEADLINE - DRAFT OMITS FOSSIL FUELS",
               hx + 148, hy + 120, 2, MUTE)

    # Six cards, two columns by three rows.
    left, right, wide = 16, 520, 488
    rows = (288, 452, 616)
    story_card(page, left, rows[0], wide, 156, RED,
               "POLAND - NATO",
               ["RUSSIAN MISSILE", "HITS POLAND"],
               ["TUSK: A PROVOCATION - NO ONE HURT",
                "NATO JETS SCRAMBLED - TALKS SAT"])
    story_card(page, right, rows[0], wide, 156, PURPLE,
               "MARKETS - AI",
               ["ANTHROPIC SLIDES", "AS AI ROUT DEEPENS"],
               ["SHARES -13% A DAY AFTER IPO DEBUT",
                "S+P -3.7% - NASDAQ -5.3% FRIDAY"])
    story_card(page, left, rows[1], wide, 156, ORANGE,
               "UKRAINE - WAR",
               ["KRYVYI RIH STRIKE", "2 DEAD - 42 INJURED"],
               ["FOUR CHILDREN AMONG THE INJURED",
                "FRANCE SEEKS UN COUNCIL MEETING"])
    story_card(page, right, rows[1], wide, 156, DEEP,
               "SPACE - ESA AND JAXA",
               ["MERCURY ARRIVAL", "BEPICOLOMBO TODAY"],
               ["8 YEARS - 6 BILLION MILES FLOWN",
                "ONLY 2ND CRAFT TO ORBIT MERCURY"])
    story_card(page, left, rows[2], wide, 156, BLUE,
               "CYBER - BANKING",
               ["DATA BREACH HITS", "CARD CUSTOMERS"],
               ["BANKS BLAME THIRD-PARTY VENDOR",
                "CORE PAYMENT NETWORKS UNAFFECTED"])
    story_card(page, right, rows[2], wide, 156, GOLD,
               "WASHINGTON - AI POLICY",
               ["TRUMP THREATENS", "OVERSEAS AI BAN"],
               ["US FIRMS' DATA CENTRES ABROAD",
                "WHITE HOUSE FIRES CYBER CHIEF"])

    # Closing band: four more of the day's stories.
    fy = 784
    page.rect(0, fy, SIZE, SIZE - fy, INK)
    page.write_mid("ALSO TODAY", SIZE // 2, fy + 16, 2, GOLD)
    page.write_mid("RIGHTS GROUPS PRESS MYANMAR AFTER GENOCIDE RULING",
                   SIZE // 2, fy + 48, 3, CARD)
    page.write_mid("MAMDANI TO CLOSE NEW YORK'S RIKERS ISLAND BY 2032",
                   SIZE // 2, fy + 88, 3, CARD)
    page.write_mid("CYCLONE AKVAN LASHES INDIA'S ODISHA COAST",
                   SIZE // 2, fy + 128, 3, CARD)
    page.write_mid("NEPAL PM SHAH FACES INDIA TEST - VISIT NOV 22-23",
                   SIZE // 2, fy + 168, 3, CARD)
    page.write_mid("AS REPORTED ON 21 NOVEMBER 2026 - BBC - REUTERS - AP - AFP - ESA",
                   SIZE // 2, fy + 208, 2, GOLD)
    return page


def encode_png(page):
    """Serialise the raster as a PNG using zlib from the stdlib."""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", crc32(tag + payload) & 0xFFFFFFFF))

    scan = bytearray()
    stride = page.side * 3
    for row in range(page.side):
        scan.append(0)
        start = row * stride
        scan += page.buf[start:start + stride]
    ihdr = struct.pack(">IIBBBBB", page.side, page.side, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(scan), 9))
            + chunk(b"IEND", b""))


def main():
    folder = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(folder, exist_ok=True)
    data = encode_png(front_page())
    target = os.path.join(folder, "entry.png")
    with open(target, "wb") as handle:
        handle.write(data)
    print("wrote", target, len(data), "bytes")


if __name__ == "__main__":
    main()
