###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search.demo.util import set_dict_values


def test_set_dict_values():
    assert set_dict_values({"a": 1, "b": {"c": None, "d": {"e": True}}}, [["a"], ["b", "d"]], [2, False]) == {
        "a": 2,
        "b": {"c": None, "d": False},
    }


def test_set_dict_values1():
    assert set_dict_values({}, [["a"]], [1, 2]) == {"a": 1}


def test_set_dict_values2():
    assert set_dict_values({}, [["a", "b"]], [1, 2]) == {"a": {"b": 1}}


def test_set_dict_values3():
    assert set_dict_values({}, [["a"], ["b"]], [1]) == {"a": 1}


def test_set_dict_values4():
    with pytest.raises(TypeError):
        set_dict_values({}, [["a"], ["a", "b"]], [1, None])


def test_set_dict_values5():
    assert set_dict_values({}, [["a"], ["a", "b"]], [{"c": None}, 2]) == {"a": {"c": None, "b": 2}}
