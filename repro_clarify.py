from devgodzilla.cli.main import get_db
from devgodzilla.models.domain import Clarification

try:
    db = get_db()
    print("DB initialized")
    clarifications = db.list_clarifications(limit=10)
    print(f"Found {len(clarifications)} clarifications")
    for c in clarifications:
        print(c)
except Exception as e:
    import traceback
    traceback.print_exc()
