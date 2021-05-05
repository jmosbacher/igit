#!/usr/bin/env python
"""Tests for `igit` package."""
# pylint: disable=redefined-outer-name

import pytest
import random
import igit


@pytest.fixture(scope="module")
def memory_repo():
    r = igit.Repo.init("memory://igit_test")
    return r

def test_interval_group(memory_repo):
    memory_repo.new_interval_group("setting1")
    memory_repo.setting1[1,10] = 9
    assert memory_repo.setting1[5] == 9
    memory_repo.setting1[9,20] = 11
    assert memory_repo.setting1[15] == 11

def test_label_group(memory_repo):
    memory_repo.new_label_group("setting2")
    memory_repo.setting2["subsetting1"] = 1
    assert memory_repo.setting2["subsetting1"] == 1
    memory_repo.setting2["subsetting2"] = 9.9
    assert memory_repo.setting2["subsetting2"] == 9.9
    memory_repo.setting2["subsetting3"] = "text"
    memory_repo.setting2["subsetting3"] == "text"

def test_commit(memory_repo):
    memory_repo.igit.add()
    ref = memory_repo.igit.commit(f"commit {random.randint(1,10)}")
    assert isinstance(ref, igit.models.CommitRef)