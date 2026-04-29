"""Tests for the daily scheduler (_schedule_loop, _seconds_until) in main.py."""
from __future__ import annotations

import datetime

from main import _schedule_loop, _seconds_until

# --- _seconds_until ---

def test_seconds_until_future_time() -> None:
    """Target later today returns the correct second count."""
    fake_now = datetime.datetime(2025, 1, 1, 8, 0, 0)
    secs = _seconds_until(9, 0, _now=fake_now)
    assert abs(secs - 3600.0) < 1.0


def test_seconds_until_past_time_adds_day() -> None:
    """Target already passed today returns approximately 23h from now."""
    fake_now = datetime.datetime(2025, 1, 1, 10, 0, 0)
    secs = _seconds_until(9, 0, _now=fake_now)
    assert abs(secs - 23 * 3600) < 1.0


def test_seconds_until_same_minute_adds_day() -> None:
    """Exact same time as now (target == now) is treated as already passed."""
    fake_now = datetime.datetime(2025, 1, 1, 9, 0, 0)
    secs = _seconds_until(9, 0, _now=fake_now)
    assert abs(secs - 24 * 3600) < 1.0


def test_seconds_until_midnight_target() -> None:
    """Target at midnight from mid-day returns approximately 12h."""
    fake_now = datetime.datetime(2025, 1, 1, 12, 0, 0)
    secs = _seconds_until(0, 0, _now=fake_now)
    assert abs(secs - 12 * 3600) < 1.0


# --- _schedule_loop ---

def test_schedule_loop_invalid_format_does_not_run(mocker) -> None:
    """An invalid time string prints an error and returns without calling run_once."""
    mock_run = mocker.patch("main.run_once")
    _schedule_loop("25:99")
    mock_run.assert_not_called()


def test_schedule_loop_invalid_format_non_numeric(mocker) -> None:
    """A non-numeric time string is rejected without calling run_once."""
    mock_run = mocker.patch("main.run_once")
    _schedule_loop("nine-am")
    mock_run.assert_not_called()


def test_schedule_loop_runs_once_immediately(mocker) -> None:
    """run_once is called on startup before the first sleep."""
    mock_run = mocker.patch("main.run_once")
    mocker.patch("main._seconds_until", return_value=3600.0)
    mocker.patch("main.time.sleep", side_effect=KeyboardInterrupt)
    _schedule_loop("09:00")
    assert mock_run.call_count == 1


def test_schedule_loop_sleeps_correct_duration(mocker) -> None:
    """time.sleep receives the value returned by _seconds_until."""
    mocker.patch("main.run_once")
    mocker.patch("main._seconds_until", return_value=7200.0)
    mock_sleep = mocker.patch("main.time.sleep", side_effect=KeyboardInterrupt)
    _schedule_loop("10:00")
    mock_sleep.assert_called_once_with(7200.0)


def test_schedule_loop_runs_again_after_sleep(mocker) -> None:
    """run_once is called a second time after the first sleep completes."""
    mock_run = mocker.patch("main.run_once")
    mocker.patch("main._seconds_until", return_value=3600.0)
    mocker.patch("main.time.sleep", side_effect=[None, KeyboardInterrupt])
    _schedule_loop("09:00")
    assert mock_run.call_count == 2


def test_schedule_loop_keyboard_interrupt_does_not_raise(mocker) -> None:
    """KeyboardInterrupt during sleep exits cleanly without propagating."""
    mocker.patch("main.run_once")
    mocker.patch("main._seconds_until", return_value=3600.0)
    mocker.patch("main.time.sleep", side_effect=KeyboardInterrupt)
    _schedule_loop("09:00")  # must not raise
