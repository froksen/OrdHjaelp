from ordhjaelp.platform.linux.selection import FreshnessTracker


def test_same_selection_not_read_twice() -> None:
    t = FreshnessTracker()
    assert t.fresh("hej", 1) == "hej"
    # Markeringen er fjernet på skærmen, men programmet udbyder stadig "hej"
    assert t.fresh("hej", 1) is None


def test_reselecting_same_text_is_fresh() -> None:
    t = FreshnessTracker()
    assert t.fresh("hej", 1) == "hej"
    assert t.fresh("hej", 2) == "hej"  # markeret igen -> ny hændelse


def test_new_text_is_fresh() -> None:
    t = FreshnessTracker()
    assert t.fresh("hej", 1) == "hej"
    assert t.fresh("farvel", 1) == "farvel"


def test_without_watcher_compares_text_only() -> None:
    t = FreshnessTracker()
    assert t.fresh("hej", None) == "hej"
    assert t.fresh("hej", None) is None
    assert t.fresh("ny", None) == "ny"


def test_empty_is_none_and_does_not_reset() -> None:
    t = FreshnessTracker()
    assert t.fresh("hej", 1) == "hej"
    assert t.fresh(None, 1) is None
    assert t.fresh("", 1) is None
    assert t.fresh("hej", 1) is None


def test_x11_poller_reports_only_new_selections(monkeypatch) -> None:
    import threading

    from ordhjaelp.platform.linux import selection as sel

    texts = iter(["allerede markeret", "allerede markeret", "nyt ord", "nyt ord"])
    monkeypatch.setattr(sel, "_X11_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(sel, "_run", lambda _cmds: next(texts, "nyt ord"))
    changed = threading.Event()
    calls: list[int] = []

    def on_change() -> None:
        calls.append(1)
        changed.set()

    poller = sel._X11SelectionPoller()
    poller.add_callback(on_change)
    assert changed.wait(1)
    threading.Event().wait(0.1)
    assert calls == [1]  # kun "nyt ord" er en ændring
