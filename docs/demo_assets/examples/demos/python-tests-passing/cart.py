"""Version correcte du calcul de panier utilisée en démonstration."""


def subtotal(prices: list[int]) -> int:
    """Calculer le sous-total, y compris pour un panier vide."""
    return sum(prices)
