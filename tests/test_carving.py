from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"atelier"))

from palace_carving import _carved_ribbon, carving_fraction
from palace_architecture import _architecture_wall
from palace_room import RoomMeshes, build_palace, palace_palette
from palace_search import search_hall
import random


class CarvingTests(unittest.TestCase):
    def test_ribbon_has_closed_section_and_attachment(self):
        meshes=RoomMeshes(carving=.40)
        _carved_ribbon(meshes,"sample",lambda x,y,z:(x,y,z),
                       [(0,0,20,35),(55,9,15,24),(105,17,12,15)])
        vertices,triangles=meshes.parts["sample","plaster"]
        edges=Counter()
        for i in range(0,len(triangles),3):
            a,b,c=triangles[i:i+3]
            for x,y in ((a,b),(b,c),(c,a)):
                edges[tuple(sorted((x,y)))]+=1
        self.assertEqual(set(edges.values()),{2})
        self.assertEqual(min(vertices[2::3]),-2)
        self.assertEqual(max(vertices[2::3]),35)

    def test_influence_changes_carving_inside_the_same_room(self):
        size=(6500,5400,3800)
        plan=search_hall("Аркады. Три поля.",style="bavarian",seed=419,
                         backend="rules",size_m=tuple(x/1000 for x in size))
        base=build_palace(plan,size,detail=1,painting=False,carving_pct=0)
        shaped=build_palace(plan,size,detail=1,painting=False,carving_pct=78)
        repeat=build_palace(plan,size,detail=1,painting=False,carving_pct=78)
        self.assertEqual(shaped.parts,repeat.parts)
        self.assertGreater(shaped.carved_pieces,200)
        self.assertGreater(base.carved_pieces,200)
        self.assertNotIn("gold",palace_palette(plan["style"],True))
        self.assertTrue(all(material!="gold" for zone,material in shaped.parts))
        surfaces=[key for key in shaped.parts if key[0].startswith(("Паркет","Окна")) and key[1] in ("wood","glass")]
        self.assertTrue(surfaces)
        self.assertTrue(all(base.parts[key]==shaped.parts[key] for key in surfaces))
        vault=next(key for key in shaped.parts if "резной свод" in key[0] and key[1]=="plaster")
        self.assertNotEqual(base.parts[vault],shaped.parts[vault])

    def test_strength_limits(self):
        self.assertEqual(carving_fraction(0),0)
        self.assertEqual(carving_fraction(100),1)
        for invalid in (-1,101,float("nan")):
            with self.assertRaises(ValueError):
                carving_fraction(invalid)

    def test_carved_canopies_have_no_separate_wall_arcs(self):
        plan={"seed":19,"style":"bavarian","curl":.72,"foliage":.65,"gilding":.4,
              "wall_bays":3,"wall_rhythm":"even",
              "architecture":{"walls":"canopy","section":"vertical","reach":.71,
                              "asymmetry":.31,"order":3}}
        frame=lambda x,y,z:(x,y,z)
        frames=[("Окна",6500,frame),("Стена",5400,frame)]
        classic=RoomMeshes()
        carved=RoomMeshes(carving=.68)
        for mesh in (classic,carved):
            _architecture_wall(mesh,plan,(6500,5400,3800),1,1.,frames,random.Random(19))
        self.assertTrue(classic.parts)
        self.assertFalse(carved.parts)
