import threading


def test_event_bus_singleton_thread_safe() -> None:
    from devgodzilla.services.events import _reset_event_bus_for_tests, get_event_bus

    _reset_event_bus_for_tests()
    results = []
    lock = threading.Lock()

    def worker() -> None:
        bus = get_event_bus()
        with lock:
            results.append(bus)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    first = results[0]
    assert all(item is first for item in results)


def test_registry_singleton_thread_safe() -> None:
    from devgodzilla.engines.registry import _reset_registry_for_tests, get_registry

    _reset_registry_for_tests()
    results = []
    lock = threading.Lock()

    def worker() -> None:
        registry = get_registry()
        with lock:
            results.append(registry)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    first = results[0]
    assert all(item is first for item in results)


def test_config_singleton_thread_safe() -> None:
    from devgodzilla.config import _reset_config_for_tests, get_config

    _reset_config_for_tests()
    results = []
    lock = threading.Lock()

    def worker() -> None:
        cfg = get_config()
        with lock:
            results.append(cfg)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    first = results[0]
    assert all(item is first for item in results)
