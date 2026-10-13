# -*- coding: utf-8 -*-
import unittest
import curve_pcg


class SamplingTests(unittest.TestCase):
    def test_open_curve(self):
        self.assertEqual(curve_pcg.sample_distances(600, 200), [0, 200, 400, 600])

    def test_closed_curve_has_no_duplicate_seam(self):
        self.assertEqual(curve_pcg.sample_distances(600, 200, True), [0, 200, 400])

    def test_remainder(self):
        self.assertEqual(curve_pcg.sample_distances(650, 200), [0, 200, 400, 600])

    def test_short_curve(self):
        self.assertEqual(curve_pcg.sample_distances(50, 200), [0])

    def test_invalid_spacing(self):
        with self.assertRaises(ValueError):
            curve_pcg.sample_distances(500, 0)

    def test_instance_limit(self):
        with self.assertRaises(ValueError):
            curve_pcg.sample_distances(5000, 1)


class MayaIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            import maya.cmds as cmds
        except ImportError:
            self.skipTest('Maya runtime required')
        self.cmds = cmds
        self.nodes = []

    def tearDown(self):
        if hasattr(self, 'cmds'):
            for node in self.nodes:
                if self.cmds.objExists(node):
                    self.cmds.delete(node)

    def test_generate_update_and_independent_copy(self):
        cmds = self.cmds
        model = curve_pcg.create_example('fence')
        self.nodes.append(model)
        curve = cmds.curve(degree=1, point=[(0, 0, 0), (600, 0, 0)])
        self.nodes.append(curve)
        length, closed = curve_pcg.curve_metrics(curve)
        self.assertAlmostEqual(length, 600)
        self.assertFalse(closed)
        group, count = curve_pcg.generate(model, curve, 200)
        self.nodes.append(group)
        self.assertEqual(count, 4)
        copy = curve_pcg.independent_result(group)
        self.nodes.append(copy)
        children = cmds.listRelatives(copy, children=True, fullPath=True)
        shapes = [cmds.listRelatives(child, shapes=True, fullPath=True)[0] for child in children]
        identities = [cmds.ls(shape, uuid=True)[0] for shape in shapes]
        self.assertEqual(len(set(identities)), 4)
        new_group, count = curve_pcg.generate(model, curve, 300, previous=group)
        self.nodes.append(new_group)
        self.assertEqual(count, 3)
        self.assertFalse(cmds.objExists(group))
        self.assertTrue(cmds.objExists(copy))
        self.assertTrue(cmds.objExists(model))
        self.assertTrue(cmds.objExists(curve))
        current = new_group
        for spacing, axis in ((150, 'Z'), (200, 'X'), (300, 'Z')):
            updated, count = curve_pcg.generate(model, curve, spacing, axis, previous=current)
            self.nodes.append(updated)
            self.assertFalse(cmds.objExists(current))
            self.assertEqual(count, len(curve_pcg.sample_distances(600, spacing)))
            self.assertEqual(cmds.getAttr(updated + '.pcgAxis'), axis)
            self.assertAlmostEqual(cmds.getAttr(updated + '.pcgSpacing'), spacing)
            self.assertTrue(cmds.objExists(copy))
            children = cmds.listRelatives(updated, children=True, fullPath=True)
            self.assertEqual(len(children), count)
            for child in children:
                self.assertEqual(len(cmds.ls(child, long=True)), 1)
            current = updated


    def test_surface_scatter_seed_and_update(self):
        import surface_pcg
        cmds = self.cmds
        model = curve_pcg.create_example('rock')
        self.nodes.append(model)
        ground = cmds.polyPlane(width=1000, height=1000, constructionHistory=False)[0]
        self.nodes.append(ground)
        group = surface_pcg.scatter([model], ground, count=20, seed=42)
        self.nodes.append(group)
        children = cmds.listRelatives(group, children=True, fullPath=True)
        self.assertEqual(len(children), 20)
        positions = [cmds.xform(node, query=True, worldSpace=True, rotatePivot=True) for node in children]
        updated = surface_pcg.scatter([model], ground, count=20, seed=42, previous=group)
        self.nodes.append(updated)
        self.assertFalse(cmds.objExists(group))
        updated_children = cmds.listRelatives(updated, children=True, fullPath=True)
        again = [cmds.xform(node, query=True, worldSpace=True, rotatePivot=True) for node in updated_children]
        self.assertEqual(positions, again)
        for point in again:
            self.assertAlmostEqual(point[1], 0)
            self.assertTrue(-500 <= point[0] <= 500)
            self.assertTrue(-500 <= point[2] <= 500)


if __name__ == '__main__':
    unittest.main()
