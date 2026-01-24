import os
from utils import db
from utils import warnings as warn_utils


def test_warnings_crud(tmp_path):
    db_path = str(tmp_path / "test_warnings.sqlite3")
    # initialize DB using a test file
    db.init_db(db_path)

    guild_id = 12345
    user_id = 111
    mod_id = 222

    # ensure clean
    warn_utils.clear_warnings(guild_id)

    wid = warn_utils.add_warning(guild_id, user_id, mod_id, "Test sebep")
    assert isinstance(wid, int)

    lst = warn_utils.list_warnings(guild_id, user_id)
    assert len(lst) == 1
    assert lst[0]["reason"] == "Test sebep"

    ok = warn_utils.remove_warning(guild_id, wid)
    assert ok is True

    lst2 = warn_utils.list_warnings(guild_id, user_id)
    assert len(lst2) == 0
