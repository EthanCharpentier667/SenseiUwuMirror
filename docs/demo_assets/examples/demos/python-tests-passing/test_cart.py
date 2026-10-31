"""Contrôles du panier rempli et du panier vide dans la version correcte."""

from cart import subtotal


def test_regular_basket() -> None:
    """Le sous-total d'un panier rempli est correct."""
    assert subtotal([10, 20]) == 30


def test_empty_basket() -> None:
    """Un panier vide doit coûter zéro."""
    assert subtotal([]) == 0
