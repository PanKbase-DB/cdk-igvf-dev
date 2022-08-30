import pytest


def test_lambdas_counter_increament_increment_counter():
    from cleaner.lambdas.counter.increment import increment_counter
    event = {
        'iterator': {
            'index': 0,
            'step': 1,
            'count': 5
        }
    }
    assert increment_counter(event, {}) == {
        'index': 1,
        'step': 1,
        'count': 5,
        'continue': True
    }
    event = {
        'iterator': {
            'index': 5,
            'step': 3,
            'count': 8
        }
    }
    assert increment_counter(event, {}) == {
        'index': 8,
        'step': 3,
        'count': 8,
        'continue': False
    }
