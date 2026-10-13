import unittest
import city_core as core


class CityTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(core.DEFAULTS)

    def test_reproducible(self):
        self.assertEqual(core.block_plan(self.config,0,0),core.block_plan(self.config,0,0))
        self.assertNotEqual(core.block_plan(self.config,0,0),core.block_plan(self.config,0,0,1))

    def test_buildings_within_block(self):
        c=self.config
        for name,b in core.block_plan(c,1,1):
            self.assertGreaterEqual(b[0]-b[3]/2,c['sidewalk'])
            self.assertLessEqual(b[0]+b[3]/2,c['block_x']-c['sidewalk'])
            self.assertGreaterEqual(b[2]-b[5]/2,c['sidewalk'])
            self.assertLessEqual(b[2]+b[5]/2,c['block_z']-c['sidewalk'])
            self.assertGreaterEqual(b[4],c['height_min'])
            self.assertLessEqual(b[4],c['height_max'])

    def test_road_area_without_overlaps(self):
        roads,extent=core.road_plan(self.config)
        c=self.config
        area=sum(b[3]*b[5] for name,b in roads)
        self.assertAlmostEqual(area,extent[0]*extent[1]-c['nx']*c['nz']*c['block_x']*c['block_z'])
        for index,(name,a) in enumerate(roads):
            for other,b in roads[index+1:]:
                overlap_x=min(a[0]+a[3]/2,b[0]+b[3]/2)-max(a[0]-a[3]/2,b[0]-b[3]/2)
                overlap_z=min(a[2]+a[5]/2,b[2]+b[5]/2)-max(a[2]-a[5]/2,b[2]-b[5]/2)
                self.assertFalse(overlap_x>0.001 and overlap_z>0.001)

    def test_density(self):
        self.config['density']=0
        self.assertEqual(core.block_plan(self.config,0,0),[])
        self.config['density']=1
        self.assertEqual(len(core.block_plan(self.config,0,0)),9)

    def test_invalid_layout(self):
        self.config['sidewalk']=4000
        with self.assertRaises(ValueError):
            core.validate(self.config)

    def test_max_lots(self):
        self.config['nx']=30
        self.config['nz']=30
        with self.assertRaises(ValueError):
            core.validate(self.config)


if __name__=='__main__':
    unittest.main()
