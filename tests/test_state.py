"""Tests for state.py."""


class TestStateStore:
    def test_is_seen_false_initially(self, in_memory_state):
        assert in_memory_state.is_seen("test:123") is False

    def test_is_seen_true_after_mark(self, in_memory_state):
        in_memory_state.mark_seen("test:123", "test", "https://example.com")
        assert in_memory_state.is_seen("test:123") is True

    def test_idempotent_mark(self, in_memory_state):
        in_memory_state.mark_seen("test:123", "test", "https://example.com")
        in_memory_state.mark_seen("test:123", "test", "https://example.com")
        assert in_memory_state.count() == 1

    def test_count(self, in_memory_state):
        assert in_memory_state.count() == 0
        in_memory_state.mark_seen("a:1", "a", "")
        in_memory_state.mark_seen("a:2", "a", "")
        assert in_memory_state.count() == 2

    def test_different_uids_independent(self, in_memory_state):
        in_memory_state.mark_seen("a:1", "a", "")
        assert in_memory_state.is_seen("a:1") is True
        assert in_memory_state.is_seen("a:2") is False
