"""Cooperative cancellation shared by core services and desktop jobs."""
from threading import Event


class OperationCancelled(Exception):
    pass


class CancellationToken:
    def __init__(self):
        self.event = Event()

    def cancel(self):
        self.event.set()

    def check(self):
        if self.event.is_set():
            raise OperationCancelled("Operação cancelada com segurança")
