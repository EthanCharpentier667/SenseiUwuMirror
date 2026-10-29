"""Petit exemple avec une erreur volontaire pour la démonstration de Sensai."""


def subtotal(prices: list[int]) -> int:
    """Calculer le sous-total ; le panier vide contient volontairement un défaut."""
    return sum(prices) if prices else 1
