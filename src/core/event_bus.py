"""EventBus central do sistema (arquitetura event-driven)."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, DefaultDict, List

from src.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Barramento de eventos central do sistema.

    Implementa padrão publish-subscribe para desacoplamento entre módulos.
    """

    def __init__(self) -> None:
        """Inicializa o EventBus com registro vazio de subscribers."""
        self._subscribers: DefaultDict[str, List[Callable[[BaseEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[BaseEvent], None]) -> None:
        """Registra um handler para um tipo de evento.

        Args:
            event_type: Tipo lógico do evento (ex: "MARKET_DATA").
            handler: Função que recebe uma instância de `BaseEvent`.
        """
        self._subscribers[event_type].append(handler)
        logger.debug("Handler registrado para %s: %s", event_type, getattr(handler, "__name__", str(handler)))

    def publish(self, event: BaseEvent) -> None:
        """Publica um evento para todos os handlers inscritos.

        Args:
            event: Instância do evento a ser publicado.
        """
        event_type = getattr(event, "event_type", event.__class__.__name__)
        handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            logger.debug("Evento %s publicado sem subscribers", event_type)
            return

        logger.debug("Publicando %s para %d handlers", event_type, len(handlers))

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.exception(
                    "Erro ao processar evento %s no handler %s: %s",
                    event_type,
                    getattr(handler, "__name__", str(handler)),
                    exc,
                )


# Singleton de módulo
event_bus = EventBus()
