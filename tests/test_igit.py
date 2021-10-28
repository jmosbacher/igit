#!/usr/bin/env python
"""Tests for `igit` package."""
# pylint: disable=redefined-outer-name

import pytest
import random
import igit
import random


@pytest.fixture(scope="module")
def memory_repo():
    return igit.init("memory://igit_test")

def test_interval_tree():
    tree = igit.IntervalTree()
    tree[1,10] = 9
    assert tree[5] == 9
    tree[5,20] = 11
    assert tree[15] == 11
    assert tree[10] == 11
    assert tree[2] == 9

def test_label_tree():
    setting2 = igit.LabelTree()
    setting2["subsetting1"] = 1
    assert setting2["subsetting1"] == 1
    setting2["subsetting2"] = 9.9
    assert setting2["subsetting2"] == 9.9
    setting2["subsetting3"] = "text"
    assert setting2["subsetting3"] == "text"

def test_commit(memory_repo):
    tree = igit.LabelTree()
    tree['test'] = 'string'
    memory_repo.add(label_tree=tree)
    ref = memory_repo.commit(f"commit {random.randint(1,10)}")
    assert isinstance(ref, igit.models.CommitRef)