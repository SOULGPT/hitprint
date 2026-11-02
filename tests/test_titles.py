from hitprint.titles import title_features


def test_title_features_basic():
    f = title_features("What if YOU were the toaster? 🍞")
    assert f["has_you"] is True
    assert f["is_question"] is True
    assert f["has_emoji"] is True
    assert f["has_number"] is False
    assert f["series_prefix"] == "what if you"
    assert f["title_len"] == len("What if YOU were the toaster? 🍞")


def test_title_number():
    assert title_features("Apple rejected my app 3 times")["has_number"] is True


def test_you_is_whole_word():
    assert title_features("Young bayou")["has_you"] is False
    assert title_features("you're it")["has_you"] is True
