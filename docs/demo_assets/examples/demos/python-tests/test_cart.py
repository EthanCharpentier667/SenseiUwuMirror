"""Deux contrôles dont un échoue volontairement dans le projet de démonstration."""

from cart import subtotal


def test_regular_basket() -> None:
    """Le sous-total d'un panier rempli est correct."""
    assert subtotal([10, 20]) == 30


def test_empty_basket() -> None:
    """Un panier vide doit coûter zéro, ce qui expose le défaut volontaire."""
    assert subtotal([]) == 0
