from types import SimpleNamespace
from unittest.mock import patch

import pytest
from choreographer.browsers.chromium import Chromium

from reporting import signals


@pytest.fixture(autouse=True)
def isolated_worker(monkeypatch):
    # Each test starts as a fresh worker, and init_kaleido's patch of Chromium is undone.
    monkeypatch.setattr(signals, "worker_queues", set())
    monkeypatch.setattr(Chromium, "get_cli", Chromium.get_cli)


def start_worker(*queues):
    worker = SimpleNamespace(app=SimpleNamespace(amqp=SimpleNamespace(queues=SimpleNamespace(consume_from=dict.fromkeys(queues)))))
    signals.record_worker_queues(sender="worker@host", instance=worker)


def test_kaleido_starts_in_a_worker_reading_the_reports_queue():
    start_worker("reports", "celery")

    with patch("reporting.signals.kaleido.start_sync_server") as start_sync_server:
        signals.init_kaleido()

    start_sync_server.assert_called_once()


def test_kaleido_stays_off_in_a_worker_without_the_reports_queue():
    """Chrome costs memory in every pool process, for charts this worker never renders."""
    start_worker("interactive")

    with patch("reporting.signals.kaleido.start_sync_server") as start_sync_server:
        signals.init_kaleido()

    start_sync_server.assert_not_called()


def test_kaleido_is_only_stopped_where_it_was_started():
    start_worker("interactive")

    with patch("reporting.signals.kaleido.stop_sync_server") as stop_sync_server:
        signals.shutdown_kaleido()

    stop_sync_server.assert_not_called()
