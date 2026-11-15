from decimal import Decimal as D

import pytest

from ryanair_price_monitor.decision import should_notify


def _decide(last, current, notified_before=True):
    return should_notify(
        notified_before=notified_before,
        last_notified_price=None if last is None else D(last),
        current_price=None if current is None else D(current),
        min_change_abs=D("10"),
        min_change_pct=D("2"),
    )


@pytest.mark.parametrize(
    ("last", "current", "expected"),
    [
        ("527.83", "527.83", False),
        ("527.83", "537.82", False),  # +9.99
        ("527.83", "537.83", True),  # +10.00, abs threshold reached
        ("527.83", "517.83", True),  # -10.00, either direction
        ("400.00", "408.00", True),  # +8.00 = 2%, pct threshold reached below 500
        ("400.00", "407.99", False),
        ("527.83", None, True),  # fare disappeared
        (None, "527.83", True),  # fare came back
        (None, None, False),
    ],
)
def test_thresholds(last, current, expected):
    assert _decide(last, current) is expected


def test_first_check_always_notifies():
    assert _decide(None, "527.83", notified_before=False) is True
