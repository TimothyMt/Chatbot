from shopbot.training import parse_callback, parse_teach_command


def test_parse_teach_command_ok():
    assert parse_teach_command("/day ship về Cần Thơ mấy ngày | Dạ 3-4 ngày ạ") == (
        "ship về Cần Thơ mấy ngày",
        "Dạ 3-4 ngày ạ",
    )


def test_parse_teach_command_bad():
    assert parse_teach_command("/day") is None
    assert parse_teach_command("/day chỉ có câu hỏi") is None
    assert parse_teach_command("/day  | chỉ có đáp") is None


def test_parse_callback_ok():
    assert parse_callback("teach:ok:12") == ("ok", 12)
    assert parse_callback("teach:no:7") == ("no", 7)


def test_parse_callback_bad():
    assert parse_callback("teach:maybe:1") is None
    assert parse_callback("khac:ok:1") is None
    assert parse_callback("teach:ok:abc") is None
    assert parse_callback("") is None
