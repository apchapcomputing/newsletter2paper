"""/health reports a scheduler that failed to start, so the deploy health check catches it."""
import main


async def test_healthy_when_scheduler_started(monkeypatch):
    monkeypatch.setattr(main.app.state, 'scheduler_error', None, raising=False)
    body = await main.health_check()
    assert body['status'] == 'healthy' and body['scheduler'] == 'running'


async def test_degraded_when_scheduler_failed(monkeypatch):
    monkeypatch.setattr(main.app.state, 'scheduler_error', 'SCHEDULER_LOCK_TIMEOUT_MINUTES=5 must exceed', raising=False)
    body = await main.health_check()
    # The deploy greps for "healthy"; "degraded" must not match it.
    assert body['status'] == 'degraded' and 'healthy' not in str(body)
    assert body['scheduler'].startswith('disabled: SCHEDULER_LOCK_TIMEOUT_MINUTES')
