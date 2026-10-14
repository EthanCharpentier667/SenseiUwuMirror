"""Persona dataclass for the Sensai chatbot."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    """An agent persona defined by a name, description, and system prompt.

    Attributes:
        name: Display name of the persona.
        description: Short human-readable summary of the persona's role.
        system_prompt: The system-level instruction injected at the start of every conversation.
    """

    name: str
    description: str
    system_prompt: str
