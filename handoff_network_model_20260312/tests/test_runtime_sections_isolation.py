import tempfile
import unittest

import numpy as np

from handoff_network_model_20260312.river_for_net import River


class _DummyInterpolator:
    def get_section_at_xy(self, pt_xy):
        x = np.array([0.0, 10.0, 20.0, 30.0], dtype=float)
        z = np.array([10.0, 0.0, 0.0, 10.0], dtype=float) + float(pt_xy[0]) * 1.0e-4
        return {
            'X': x,
            'Z': z,
        }


def _build_river(shared_section_data, output_path):
    river_data = {
        'cell_num': 3,
        'pos': [
            [0.0, 1.0, 2.11],
            [100.0, 1.0, 2.08],
            [200.0, 1.0, 2.05],
            [300.0, 1.0, 2.02],
        ],
        'section_name': ['se1', 'se2', 'se3'],
    }
    section_pos = {
        'se1': np.array([50.0, 1.0], dtype=float),
        'se2': np.array([150.0, 1.0], dtype=float),
        'se3': np.array([250.0, 1.0], dtype=float),
    }
    sim_data = {
        'model_name': 'test_river',
        'sim_start_time': '2024-01-01 00:00:00',
        'sim_end_time': '2024-01-01 00:10:00',
        'time_step': 60,
        'output_path': output_path,
        'CFL': 0.3,
        'n': 0.03,
    }
    river = River(river_data, shared_section_data, section_pos, sim_data)
    river.Interpolator = _DummyInterpolator()
    river.section_interpolation_enabled = True
    return river


class RuntimeSectionsIsolationTest(unittest.TestCase):
    def test_fine_cell_property_does_not_pollute_other_rivers(self):
        shared_section_data = {
            'se1': [[0.0, 10.0], [10.0, 0.0], [20.0, 0.0], [30.0, 10.0]],
            'se2': [[0.0, 10.0], [10.0, 0.0], [20.0, 0.0], [30.0, 10.0]],
            'se3': [[0.0, 10.0], [10.0, 0.0], [20.0, 0.0], [30.0, 10.0]],
        }
        original_snapshot = {
            name: [row[:] for row in rows]
            for name, rows in shared_section_data.items()
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            river_a = _build_river(shared_section_data, tmpdir)
            river_b = _build_river(shared_section_data, tmpdir)

            self.assertEqual(set(river_a.raw_sections_data), {'se1', 'se2', 'se3'})
            self.assertEqual(set(river_b.sections_data), {'se1', 'se2', 'se3'})

            river_a.Fine_cell_property2()

            self.assertTrue(any(name.startswith('Interpolator_') for name in river_a.sections_data))
            self.assertFalse(any(name.startswith('Interpolator_') for name in river_a.raw_sections_data))
            self.assertFalse(any(name.startswith('Interpolator_') for name in river_b.sections_data))
            self.assertEqual(shared_section_data, original_snapshot)
            self.assertEqual(set(river_b.sections_data), {'se1', 'se2', 'se3'})


if __name__ == '__main__':
    unittest.main()
