import unittest

import networkx as nx

import dimod

import penaltymodel.core as pm
import penaltymodel.cache as pmc
import penaltymodel.maxgap as maxgap
from pkg_resources import iter_entry_points


class TestInterfaceWithCache(unittest.TestCase):
    def test_retrieval(self):
        # put some stuff in the database

        spec = pm.Specification(nx.path_graph(2), (0, 1), {(-1, -1), (1, 1)}, vartype=pm.SPIN)
        model = dimod.BinaryQuadraticModel({0: 0, 1: 0}, {(0, 1): -1}, 0.0, vartype=pm.SPIN)
        widget = pm.PenaltyModel.from_specification(spec, model, 2, -1)

        for cache in pm.iter_caches():
            cache(widget)

        # now try to get it back
        new_widget = pm.get_penalty_model(spec)

        self.assertEqual(widget, new_widget)


class TestInterfaceWithMaxGap(unittest.TestCase):
    def test_retrieval(self):

        eq = {(-1, -1), (1, 1)}

        spec = pm.Specification(nx.path_graph(2), (0, 1), eq, vartype=pm.SPIN)
        widget = pm.get_penalty_model(spec)

        self.assertEqual(widget.model.linear, {0: 0, 1: 0})
        self.assertEqual(widget.model.quadratic, {(0, 1): -1})


class TestFactories(unittest.TestCase):
    def test_retrieval(self):
        factories = list(iter_entry_points('penaltymodel_factory'))
        self.assertGreaterEqual(len(factories), 0)
