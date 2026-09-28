"""tests.test_maya_utils

Tests for the Maya wrappers that can be exercised without Maya.

maya_utils.cmds() returns a cached module reference, and that cache exists
precisely so tests can inject a stand-in. Everything here drives a fake
cmds object; nothing touches a real Maya session.

Coverage:
    - keyframe_range: the animation's real extent, not the playback range
    - subtree_joints: root + descendants
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mtu_maya.core import maya_utils


class _FakeCmds:
    """Minimal stand-in for maya.cmds covering what these helpers call."""

    def __init__(self, keys=None, children=None, existing=None, raises=False):
        self._keys = keys                     # None means "no animation"
        self._children = children or {}
        self._existing = existing
        self._raises = raises
        self.keyframe_calls = []

    def keyframe(self, nodes, query=False, timeChange=False):
        if self._raises:
            raise RuntimeError("no such node")
        self.keyframe_calls.append(nodes)
        return self._keys

    def objExists(self, node):
        if self._existing is None:
            return True
        return node in self._existing

    def listRelatives(self, node, allDescendents=False, type=None, fullPath=False):
        if self._raises:
            raise RuntimeError("node is gone")
        return self._children.get(node)

    def ls(self, node, long=False):
        return [node]


class _InjectFakeCmds(unittest.TestCase):
    """Swap maya_utils' cached cmds for the duration of a test."""

    def use(self, fake):
        self._original = maya_utils._cmds
        maya_utils._cmds = fake
        self.addCleanup(self._restore)
        return fake

    def _restore(self):
        maya_utils._cmds = self._original


class TestKeyframeRange(_InjectFakeCmds):
    def test_returns_first_and_last_key(self):
        self.use(_FakeCmds(keys=[0.0, 12.0, 35.0]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (0, 35))

    def test_ignores_key_order(self):
        self.use(_FakeCmds(keys=[35.0, 0.0, 12.0]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (0, 35))

    def test_range_is_independent_of_the_timeline(self):
        # The whole point: a 0-35 clip inside a default 1-120 timeline must
        # report 0-35, not the slider's span.
        self.use(_FakeCmds(keys=[0.0, 35.0]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (0, 35))

    def test_animation_not_starting_at_zero(self):
        self.use(_FakeCmds(keys=[10.0, 60.0]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (10, 60))

    def test_single_key_gives_an_equal_range(self):
        self.use(_FakeCmds(keys=[7.0]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (7, 7))

    def test_fractional_times_round_to_nearest(self):
        self.use(_FakeCmds(keys=[0.4, 34.6]))
        self.assertEqual(maya_utils.keyframe_range(["|Hips"]), (0, 35))

    def test_no_keys_returns_none(self):
        self.use(_FakeCmds(keys=[]))
        self.assertIsNone(maya_utils.keyframe_range(["|root"]))

    def test_none_from_maya_returns_none(self):
        self.use(_FakeCmds(keys=None))
        self.assertIsNone(maya_utils.keyframe_range(["|root"]))

    def test_empty_node_list_short_circuits(self):
        fake = self.use(_FakeCmds(keys=[1.0, 2.0]))
        self.assertIsNone(maya_utils.keyframe_range([]))
        self.assertEqual(fake.keyframe_calls, [])

    def test_maya_error_returns_none(self):
        self.use(_FakeCmds(raises=True))
        self.assertIsNone(maya_utils.keyframe_range(["|gone"]))


class TestSubtreeJoints(_InjectFakeCmds):
    def test_includes_root_and_descendants(self):
        self.use(_FakeCmds(children={"|root": ["|root|pelvis", "|root|pelvis|spine"]}))
        found = maya_utils.subtree_joints("|root")
        self.assertIn("|root", found)
        self.assertIn("|root|pelvis|spine", found)
        self.assertEqual(len(found), 3)

    def test_childless_root_returns_just_the_root(self):
        self.use(_FakeCmds(children={}))
        self.assertEqual(maya_utils.subtree_joints("|lonely"), ["|lonely"])

    def test_missing_root_returns_empty(self):
        self.use(_FakeCmds(existing=set()))
        self.assertEqual(maya_utils.subtree_joints("|nope"), [])

    def test_empty_name_returns_empty(self):
        self.assertEqual(maya_utils.subtree_joints(""), [])

    def test_maya_error_returns_empty(self):
        self.use(_FakeCmds(raises=True))
        self.assertEqual(maya_utils.subtree_joints("|root"), [])


if __name__ == "__main__":
    unittest.main()
