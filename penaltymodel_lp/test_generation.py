# Copyright 2018 D-Wave Systems Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from itertools import product
import unittest
from unittest.mock import patch
from scipy.optimize import OptimizeWarning
from scipy.linalg import LinAlgWarning

import networkx as nx

import penaltymodel.lp as lp


#TODO: add tests on satisfying min_gap. Currently, we're always checking that gap > 0, and passive
# check that gap >= default 2.
class TestPenaltyModelLinearProgramming(unittest.TestCase):
    def verify_gate_bqm(self, bqm, nodes, get_gate_output, ground_energy=0, min_gap=2, places=7):
        """Check that all equally valid gate inputs are at ground and that invalid values meet
        threshold (min_gap) requirement.
        """
        for a, b, c in product([-1, 1], repeat=3):
            spin_state = {nodes[0]: a, nodes[1]: b, nodes[2]: c}
            energy = bqm.energy(spin_state)

            if c == get_gate_output(a, b):
                self.assertAlmostEqual(ground_energy, energy, places=places,
                                       msg="Failed for {}".format(spin_state))
            else:
                # We are rounding the energy so that we can do almost-equal-or-
                # greater-than comparison
                energy = round(energy, places)
                self.assertGreaterEqual(energy, ground_energy + min_gap,
                                        "Failed for {}".format(spin_state))

    def test_empty(self):
        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph([]), [], [])

    def test_dictionary_input(self):
        # Generate BQM with a dictionary
        nodes = ['a', 'b', 'c']
        ground = 0
        or_gate_values = {(-1, 1, 1): ground,
                          (1, -1, 1): ground,
                          (1, 1, 1): ground,
                          (-1, -1, -1): ground}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), or_gate_values, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, max, ground_energy=ground)

    def test_set_input(self):
        # Generate BQM with a set
        nodes = [1, 2, 3]
        and_gate_set = {(-1, -1, -1), (-1, 1, -1), (1, -1, -1), (1, 1, 1)}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), and_gate_set, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, min)

    def test_list_input(self):
        # Generate BQM with a list
        nodes = [1, 2, 3]
        nand_gate_list = [(-1, -1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)]
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), nand_gate_list, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, lambda x, y: -1 * min(x, y))

    def test_min_gap(self):
        # Testing that min_classical_gap parameter works
        def run_same_problem(min_gap):
            nodes = ['a', 'b']
            states = {(-1, -1): -1,
                      (-1, 1): -1,
                      (1, -1): -1}
            return lp.generate_bqm(nx.complete_graph(nodes), states, nodes,
                                   min_classical_gap=min_gap)

        # min_classical_gap=5 should be too large for the problem
        with self.assertRaises(ValueError):
            large_min_gap = 5
            run_same_problem(large_min_gap)

        # Lowering the min_classical_gap should allow a bqm to be found
        smaller_min_gap = 4
        bqm, gap = run_same_problem(smaller_min_gap)
        self.assertAlmostEqual(smaller_min_gap, gap)

    def test_linear_energy_range(self):
        # Test linear energy range
        nodes = ['a']
        linear_energy_range = {'a': (-5, -2)}
        config = {1: 96,
                  -1: 104}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes,
                                   linear_energy_ranges=linear_energy_range)

        # Verify that results match expected BQM
        self.assertAlmostEqual(100, bqm.offset)
        self.assertAlmostEqual(-4, bqm.linear['a'])   # linear bias falls within 'linear_energy_range'

    def test_quadratic_energy_range(self):
        # Test quadratic energy range
        nodes = ['a', 'b']
        quadratic_energy_range = {('a', 'b'): (-130, -120)}
        config = {(-1, -1): -82,
                  (1, 1): -80,
                  (1, -1): 162}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes,
                                   quadratic_energy_ranges=quadratic_energy_range)

        # Verify that results match expected BQM
        self.assertAlmostEqual(42, bqm.offset)
        self.assertAlmostEqual(-1, bqm.linear['a'])   # Bias within 'linear_energy_range'
        self.assertAlmostEqual(2, bqm.linear['b'])    # Bias within 'linear_energy_range'

        # Check that bias is within 'quadratic_energy_range'
        try:
            self.assertAlmostEqual(-123, bqm.quadratic[('a', 'b')])
        except KeyError:
            self.assertAlmostEqual(-123, bqm.quadratic[('b', 'a')])

    def test_multi_energy_bqm(self):
        # Create BQM for fully determined configuration with no ground states
        configurations = {(-1, -1): -.5, (-1, 1): 3.5, (1, -1): 1.5, (1, 1): 3.5}
        nodes = ['x', 'y']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), configurations, nodes)

        self.assertGreater(gap, 0)

        # Verify BQM
        for (x, y), expected_energy in configurations.items():
            energy = bqm.energy({'x': x, 'y': y})
            self.assertAlmostEqual(expected_energy, energy,
                                   msg="Failed for x:{}, y:{}".format(x, y))

    def test_mixed_specification_truth_table(self):
        # Set a ground state and a valid state with an energy level
        # Note: all other states should be invalid
        configurations = {(-1, -1, 1): 0, (1, -1, 1): 2}
        nodes = ['x', 'y', 'z']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), configurations, nodes)

        self.assertGreater(gap, 0)

        # Verify BQM
        for i, j, k in product([-1, 1], repeat=3):
            energy = bqm.energy({'x': i, 'y': j, 'z': k})
            if (i, j, k) in configurations.keys():
                self.assertAlmostEqual(energy, configurations[(i, j, k)])
            else:
                self.assertGreaterEqual(energy, 2)

    def test_gap_energy_level(self):
        """Check that gap is with respect to the highest energy level provided by user.
        """
        config = {(1, 1): 1, (-1, 1): 0, (1, -1): 0}
        nodes = ['a', 'b']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes)

        self.assertAlmostEqual(gap, 2)

        # Check specified config
        for a, b in config.keys():
            expected_energy = config[(a, b)]
            energy = bqm.energy({'a': a, 'b': b})
            self.assertAlmostEqual(expected_energy, energy)

        # Check unspecified configuration
        # Namely, threshold is gap + max-config-energy (i.e. 2 + 1). Threshold should not be based
        # on gap + smallest-config-energy (i.e. 2 + 0).
        energy = bqm.energy({'a': -1, 'b': -1})
        self.assertAlmostEqual(3, energy)

    def test_impossible_bqm(self):
        # Set up xor-gate
        # Note: penaltymodel-lp would need an auxiliary variable in order to handle this;
        #   however, no auxiliaries are provided, hence, it raise an error
        nodes = ['a', 'b', 'c']
        xor_gate_values = {(-1, -1, -1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)}

        # penaltymodel-lp should not be able to handle an xor-gate
        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph(nodes), xor_gate_values, nodes)

    @patch('scipy.optimize.linprog')
    def test_linprog_optimizewarning(self, dummy_linprog):
        """The linear program sometimes throws OptimizeWarning for matrices that
        are not full row rank. In such a case, penaltymodel-lp should give up
        and let a more sophisticated penaltymodel deal with the problem"""

        # Note: I'm using mock because it's difficult to think of a small ising
        #   system that is not full row rank. (i.e. need to consider linear states,
        #   quadratic states, offset and gap coefficients when building
        #   the non-full-row-rank matrix).
        dummy_linprog.return_value = OptimizeWarning

        # Placeholder problem
        nodes = ['r', 'a', 'n', 'd', 'o', 'm']
        values = {(1, 1, 1, 1, 1, 1), (1, 1, 0, 0, 0, 0)}

        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph(nodes), values, nodes)

    @patch('scipy.optimize.linprog')
    def test_linprog_linalgwarning(self, dummy_linprog):
        """The linear program sometimes throws LinAlgWarning for matrices that
        are ill-conditioned. In such a case, penaltymodel-lp should give up
        and let a more sophisticated penaltymodel deal with the problem"""

        # Note: I'm using mock because it's difficult to think of a small ising
        #   system that is ill-conditioned.
        dummy_linprog.return_value = LinAlgWarning

        # Placeholder problem
        nodes = ['r', 'a', 'n', 'd', 'o', 'm']
        values = {(1, 1, 1, 1, 1, 1), (1, 1, 0, 0, 0, 0)}

        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph(nodes), values, nodes)


if __name__ == "__main__":
    unittest.main()
