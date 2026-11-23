# tests/test_workspace.py
def test_create_workspace(ws):
    assert ws.root.exists()
    assert ws.meta["name"] == "w1"
    assert ws.catalog_path.exists()


def test_catalog_has_creation_event(ws):
    events = list(ws.catalog)
    assert events[0]["event"] == "workspace_created"
# tests/test_workspace.py — adição

def test_context_manager_closes_connection(ws):
    with ws as w:
        w.db.execute("SELECT 1")
    assert ws._db is None


def test_context_manager_closes_connection(ws):
    with ws as w:
        w.db.execute("SELECT 1")
    assert ws._db is None

def test_context_manager_closes_connection(ws):
    with ws as w: w.db.execute("SELECT 1")
    assert ws._db is None

def test_context_manager_closes_connection(ws):
    with ws as w: w.db.execute("SELECT 1")
    assert ws._db is None

def test_context_manager_closes_connection(ws):
    with ws as w: w.db.execute("SELECT 1")
    assert ws._db is None
