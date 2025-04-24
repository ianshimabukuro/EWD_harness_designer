
SYMBOL_TYPES = ["outlet", "switch","light","junction box","electrical panel"]

CEILING_HEIGHT = 8
DEFAULTS = {
    'outlet': {'amperage': 15, 'height': CEILING_HEIGHT - 1},
    'switch': {'amperage': 15, 'height': CEILING_HEIGHT - 4},
    'light': {'amperage': 1, 'height': CEILING_HEIGHT},
    'junction box': {'amperage': None, 'height': CEILING_HEIGHT},
    'electrical panel': {'amperage': None, 'height': 6}
}

UNIT_PRICES = {
    "14 AWG": 0.5,
    "12 AWG": 0.6,
    "10 AWG": 0.8,
    "8 AWG": 1,
    "Consult engineer": 0.00  # default fallback
}