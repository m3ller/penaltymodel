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

import dimod
import itertools
import networkx as nx
import unittest

import penaltymodel.core as pm
from penaltymodel.core.utilities import get_uniform_penaltymodel


class TestPenaltyModel(unittest.TestCase):
    def test_construction(self):

        # build a specification
        graph = nx.complete_graph(10)
        decision_variables = (0, 4, 5)
        feasible_configurations = {(-1, -1, -1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)

        # build a model
        model = dimod.BinaryQuadraticModel({v: 0 for v in graph},
                                           {edge: 0 for edge in graph.edges},
                                           0.0,
                                           vartype=dimod.SPIN)

        # build a PenaltyModel explicitly
        pm0 = pm.PenaltyModel(graph, decision_variables, feasible_configurations, dimod.SPIN, model, .1, 0)

        # build from spec
        pm1 = pm.PenaltyModel.from_specification(spec, model, .1, 0)

        # should result in equality
        self.assertEqual(pm0, pm1)

    def test_relabel(self):
        graph = nx.path_graph(3)
        decision_variables = (0, 2)
        feasible_configurations = {(-1, -1): 0., (+1, +1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)
        linear = {v: 0 for v in graph}
        quadratic = {edge: -1 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

        # now set up the same widget with 0 relabelled to 'a'
        graph = nx.path_graph(3)
        graph = nx.relabel_nodes(graph, {0: 'a'})
        decision_variables = ('a', 2)
        feasible_configurations = {(-1, -1): 0., (+1, +1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)
        linear = {v: 0 for v in graph}
        quadratic = {edge: -1 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        test_widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

        # without copy
        new_widget = widget.relabel_variables({0: 'a'}, inplace=False)
        self.assertEqual(test_widget, new_widget)
        self.assertEqual(new_widget.decision_variables, ('a', 2))

        widget.relabel_variables({0: 'a'}, inplace=True)
        self.assertEqual(widget, test_widget)
        self.assertEqual(widget.decision_variables, ('a', 2))

    def test_bad_energy_range(self):
        graph = nx.path_graph(3)
        decision_variables = (0, 2)
        feasible_configurations = {(-1, -1): 0., (+1, +1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)

        linear = {v: -3 for v in graph}
        quadratic = {edge: -1 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        with self.assertRaises(ValueError):
            widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

        linear = {v: 0 for v in graph}
        quadratic = {edge: 5 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        with self.assertRaises(ValueError):
            widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

    def test_relabel_forwards_and_backwards(self):
        graph = nx.path_graph(4)
        graph.add_edge(0, 2)
        decision_variables = (0, 2)
        feasible_configurations = {(-1, -1): 0., (+1, +1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)
        linear = {v: 0 for v in graph}
        quadratic = {edge: -1 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

        # make another one
        graph = nx.path_graph(4)
        graph.add_edge(0, 2)
        decision_variables = (0, 2)
        feasible_configurations = {(-1, -1): 0., (+1, +1): 0.}
        spec = pm.Specification(graph, decision_variables, feasible_configurations, vartype=dimod.SPIN)
        linear = {v: 0 for v in graph}
        quadratic = {edge: -1 for edge in graph.edges}
        model = dimod.BinaryQuadraticModel(linear, quadratic, 0.0, vartype=dimod.SPIN)
        original_widget = pm.PenaltyModel.from_specification(spec, model, 2., -2)

        new_label_sets = [(10, 1),
                          ('a', 'b'),
                          (1, 'b'),
                          ('1', '2', '3', '4'),
                          ('a', 'b', 'c', 'd')]
        new_label_sets.extend(itertools.permutations(graph))

        for new in new_label_sets:
            mapping = dict(enumerate(new))
            inv_mapping = {u: v for v, u in mapping.items()}

            # apply then invert with copy=False
            widget.relabel_variables(mapping, inplace=True)
            widget.relabel_variables(inv_mapping, inplace=True)
            self.assertEqual(widget, original_widget)

            # apply then invert with copy=True
            copy_widget = widget.relabel_variables(mapping, inplace=False)
            inv_copy = copy_widget.relabel_variables(inv_mapping, inplace=False)
            self.assertEqual(inv_copy, original_widget)

    def test_bqm_and_graph_label_matching(self):
        vartype = dimod.BINARY
        bqm = dimod.BinaryQuadraticModel({'a': -1, 'b': 0}, {('c', 'a'): 0}, 0,
                                         vartype)
        g1 = nx.complete_graph(['a', 1, 2])
        g2 = nx.complete_graph(['a', 'b', 'c'])

        with self.assertRaises(ValueError):
            pm.PenaltyModel(g1, ['a'], {(0, )}, vartype, bqm, 2, 0)

        pm.PenaltyModel(g2, ['a'], {(0, )}, vartype, bqm, 2, 0)


class TestPenaltyModelBalance(unittest.TestCase):
    def check_balance(self, balanced_pmodel, original_pmodel):
        # Sample the balanced penaltymodel
        sampleset = dimod.ExactSolver().sample(balanced_pmodel.model)
        sample_states = sampleset.lowest().record.sample

        # Reorder sample columns to match feasible_configuration
        index_dict = {v: i for i, v in enumerate(sampleset.variables)}
        indices = [index_dict[dv] for dv in original_pmodel.decision_variables]
        decision_states = list(map(tuple, sample_states[:, indices]))

        # Checking that the gap is larger than min_classical_gap with some tolerance
        self.assertGreaterEqual(balanced_pmodel.classical_gap, original_pmodel.min_classical_gap)

        # Check that there are no duplicates
        self.assertEqual(len(set(decision_states)), len(decision_states),
                         msg="There are duplicate states in balanced solution")

        # Check that we have the correct number of states
        self.assertEqual(len(decision_states), len(original_pmodel.feasible_configurations),
                         msg="Incorrect number of states in balanced solution")

        # Check that all states are valid
        for state in decision_states:
            self.assertIn(state, original_pmodel.feasible_configurations,
                          msg="{} is not a feasible configuration".format(state))

        # Check is_uniform flag
        self.assertTrue(balanced_pmodel.is_uniform)

    def test_balance_with_empty_penaltymodel(self):
        # Build a penaltymodel with an empty bqm
        vartype = dimod.SPIN
        empty_model = dimod.BinaryQuadraticModel.empty(vartype)
        n_nodes = 3
        graph = nx.complete_graph(n_nodes)
        decision_variables = list(range(n_nodes - 1))
        feasible_configurations = {(-1, -1), (1, 1)}
        classical_gap = 2
        ground_energy = 0
        pmodel = pm.PenaltyModel(graph, decision_variables, feasible_configurations, vartype,
                                 empty_model, classical_gap, ground_energy)

        with self.assertRaises(TypeError):
            pmodel.balance_penaltymodel(n_tries=10)

    def test_balance_with_impossible_model(self):
        pass

    def test_balance_with_already_balanced_model(self):
        """Test balance on an already balanced NOT-gate penaltymodel
        """
        # Set up
        g = nx.Graph([('in', 'out')])
        decision_variables = ['in', 'out']
        linear_biases = {}
        quadratic_biases = {('in', 'out'): 1}
        feasible_config = {(-1, +1), (+1, -1)}  # not-gate
        vartype = dimod.SPIN
        offset = 0

        # Construct a balanced BQM to put in penaltymodel
        model = dimod.BinaryQuadraticModel(linear_biases, quadratic_biases, offset, vartype)

        # Construct and rebalance penaltymodel
        pmodel = pm.PenaltyModel(g, decision_variables, feasible_config, vartype, model,
                                 classical_gap=2, ground_energy=0)
        new_pmodel = get_uniform_penaltymodel(pmodel)

        self.assertEqual(model, new_pmodel.model)
        self.assertTrue(new_pmodel.is_uniform)

    def test_balance_with_qubo(self):
        decision_variables = ['a', 'b']
        feasible_config = {(1, 0), (0, 1)}
        vartype = dimod.BINARY
        classical_gap = 0.5
        ground_energy = -1
        g = nx.complete_graph(decision_variables)

        model = dimod.BinaryQuadraticModel({'a': -1, 'b': 0.5, 'c': -.5},
                                           {'ab': 1, 'bc': -1, 'ac': 0.5}, 0, vartype)
        pmodel = pm.PenaltyModel(g, decision_variables, feasible_config,
                                 vartype, model, classical_gap, ground_energy)
        new_pmodel = get_uniform_penaltymodel(pmodel)
        self.check_balance(new_pmodel, pmodel)

    def test_balance_with_ising(self):
        #TODO: perhaps a shorter problem for unit tests? but this IS representative
        # Constructing three-input AND-gate graph
        decision_variables = ['in0', 'in1', 'in2', 'out']
        feasible_config = {(0, 0, 0, 0),
                           (0, 0, 1, 0),
                           (0, 1, 0, 0),
                           (0, 1, 1, 0),
                           (1, 0, 0, 0),
                           (1, 0, 1, 0),
                           (1, 1, 0, 0),
                           (1, 1, 1, 1)}
        classical_gap = 2
        ground_energy = 0
        vartype = dimod.SPIN

        # Construct a bqm that is an imbalanced penaltymodel
        linear_biases = {'in0': -1, 'in1': -.5, 'in2': 0,       # Shore 0
                         'out': 2, 'aux0': .5, 'aux1': 1}       # Shore 1
        quadratic_biases = \
            {('in0', 'out'): -1, ('in0', 'aux0'): -.5, ('in0', 'aux1'): -.5,
             ('in1', 'out'): -1, ('in1', 'aux0'): 1, ('in1', 'aux1'): -.5,
             ('in2', 'out'): -1, ('in2', 'aux0'): 0, ('in2', 'aux1'): 1}
        feasible_config = {(-1, -1, -1, -1),
                           (-1, -1, +1, -1),
                           (-1, +1, -1, -1),
                           (-1, +1, +1, -1),
                           (+1, -1, -1, -1),
                           (+1, -1, +1, -1),
                           (+1, +1, -1, -1),
                           (+1, +1, +1, +1)}
        offset = 4.5
        vartype = dimod.SPIN
        classical_gap = 2
        ground_energy = 0
        tol = 1e-12

        model = dimod.BinaryQuadraticModel(linear_biases, quadratic_biases, offset, vartype)
        pmodel = pm.PenaltyModel(g, decision_variables, feasible_config,
                                 vartype, model, classical_gap, ground_energy)

        new_pmodel = get_uniform_penaltymodel(pmodel, tol=tol)
        self.check_balance(new_pmodel, pmodel)
