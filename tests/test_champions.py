"""Offline Champions snapshot integrity, mechanics regressions and browser behavior."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboard'))
from champions import DIRECTORY, filter_moves
from streamlit.testing.v1 import AppTest


class ChampionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
        cls.tables = {name: json.loads((DIRECTORY / f'{name}.json').read_text(encoding='utf-8'))
                      for name in cls.manifest['outputs']}
        cls.moves = {m['id']: m for m in cls.tables['moves']}

    def test_snapshot_integrity_and_relationships(self):
        for name, metadata in self.manifest['outputs'].items():
            content = (DIRECTORY / f'{name}.json').read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), metadata['sha256'])
        self.assertEqual(len(self.moves), len(self.tables['moves']))
        species = {p['id'] for p in self.tables['species']}
        routes = {(r['pokemon_id'], r['move_id']) for r in self.tables['learnsets']}
        self.assertEqual(len(routes), len(self.tables['learnsets']))
        for pokemon_id, move_id in routes:
            self.assertIn(pokemon_id, species)
            self.assertTrue(self.moves[move_id]['available'])
        self.assertFalse(self.manifest['official_regulation_verified'])

    def test_champions_overrides_and_inheritance(self):
        milk = self.moves['milkdrink']
        self.assertEqual(milk['target'], 'adjacentAllyOrSelf')
        self.assertEqual(milk['heal'], [1, 2])
        self.assertEqual(milk['pp'], 5)
        self.assertTrue(milk['desc'])
        self.assertTrue(all(m['desc'] for m in self.moves.values() if m['available']))
        self.assertTrue(milk['flags']['heal'])
        self.assertEqual(self.moves['anchorshot']['basePower'], 90)
        self.assertTrue(all(m['pp'] <= 20 for m in self.moves.values()))
        par = self.tables['checks']['paralysis']
        self.assertEqual(par['action_prevention_probability'], [1, 8])
        self.assertEqual(par['speed_101'], 50)
        self.assertEqual(par['quick_feet_speed_101'], 101)

    def test_competitive_filters(self):
        moves = self.tables['moves']
        result = filter_moves(moves, features=['Contact'], priority=True)
        self.assertIn('fakeout', [m['id'] for m in result])
        self.assertTrue(all(m['flags'].get('contact') and m['priority'] > 0 for m in result))
        self.assertIn('hypervoice', [m['id'] for m in filter_moves(moves, features=['Sound'], spread=True)])
        self.assertFalse(filter_moves(moves, query='no-such-move'))
        self.assertFalse(any(not m['available'] for m in filter_moves(moves)))
        self.assertGreater(len(filter_moves(moves, available=False)), len(filter_moves(moves)))

    def dex_app(self, view='dex', identifier=''):
        app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30)
        app.query_params.update({'page':'champions', 'view':view, 'id':identifier})
        return app.run()

    def test_full_dex_pages(self):
        for view, identifier in [('dex',''),('pokemon','incineroar'),('abilities',''),
                                 ('ability','intimidate'),('items',''),('item','sitrusberry'),('compare','')]:
            with self.subTest(view=view):
                app = self.dex_app(view,identifier)
                self.assertFalse(app.exception)
        app = self.dex_app('compare')
        app.multiselect(key='mc_compare').set_value(['incineroar','rillaboom']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value.loc['Attack','Incineroar'],115)

    def test_dex_filter_links_and_symbols(self):
        app = self.dex_app()
        app.text_input(key='mc_query').set_value('Incineroar').run()
        table = app.dataframe[0].value
        self.assertEqual(len(table),1)
        self.assertTrue(table['Sprite'].iloc[0].endswith('/incineroar.png'))
        self.assertIn('view=pokemon&id=incineroar',table['Pokémon'].iloc[0])
        self.assertTrue(table['Type 1'].iloc[0].startswith('data:image/svg+xml'))
        app.button(key='mc_nav_items').click().run()
        app.button(key='mc_nav_dex').click().run()
        self.assertEqual(app.text_input(key='mc_query').value,'Incineroar')
        app.toggle(key='mc_labels').set_value(True).run()
        self.assertEqual(app.dataframe[0].value['Type 1'].iloc[0],'Fire')

    def test_item_icons_and_readable_links(self):
        from champions_dex import item_icon
        from urllib.parse import urlsplit
        for item in self.tables['items']:
            self.assertTrue(item_icon(item['spritenum']).startswith('data:image/png;base64,'))
        app=self.dex_app('items')
        frame=app.dataframe[0].value
        self.assertTrue(frame['Icon'].str.startswith('data:image/png;base64,').all())
        self.assertTrue(all(not urlsplit(url).fragment.startswith('#') for url in frame['Item']))
        self.assertEqual(json.loads(app.dataframe[0].proto.columns)['Item']['width'],170)
        app=self.dex_app('item','chestoberry')
        self.assertFalse(app.exception)

    def test_mc_pool_and_type_defenses(self):
        from champions_dex import defenses
        pool={p['id']:p for p in self.tables['species'] if p['mc_species_allowed']}
        self.assertNotIn('meloettapirouette',pool)
        self.assertNotIn('terapagosterastal',pool)
        self.assertIn('incineroar',pool)
        self.assertEqual(defenses(pool['incineroar'],self.tables['types'])['Psychic'],0)
        self.assertEqual(defenses(pool['incineroar'],self.tables['types'])['Water'],2)
        app=self.dex_app('pokemon','incineroar')
        app.text_input(key='mc_learn_query').set_value('Fake Out').run()
        self.assertEqual(len(app.dataframe[0].value),1)
        self.assertIn('view=moves&id=fakeout',app.dataframe[0].value['Move'].iloc[0])

    def test_detail_uses_grouped_defenses_and_baseline_navigation(self):
        app = self.dex_app('pokemon', 'wigglytuff')
        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.tabs], ['Type defenses', 'Moves learned', 'Other forms'])
        markup = '\n'.join(m.value for m in app.markdown)
        self.assertIn('**Weaknesses**', markup)
        self.assertIn('**Resistances**', markup)
        self.assertIn('**Immunities**', markup)
        self.assertIn('Dragon', markup)
        self.assertIn('0×', markup)
        self.assertIn('½×', markup)
        self.assertTrue(any(e.label.startswith('Neutral damage') and not e.proto.expanded for e in app.expander))
        self.assertTrue(any(b.label == 'Compare this Pokémon' for b in app.button))
        self.assertEqual(len(app.get('popover')), 3)
        app.button(key='mc_pokemon_ability_cutecharm_pokemon').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.query_params['view'], 'ability')
        app = self.dex_app('pokemon', 'raichumegay')
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == '← Previous').click().run()
        self.assertFalse(app.exception)
        self.assertNotEqual(app.query_params['id'], 'raichumegay')

    def test_preview_search_and_navigation(self):
        app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=30)
        app.query_params['page'] = 'champions'
        app.query_params['view'] = 'moves'
        app.run()
        self.assertFalse(app.exception)
        app.text_input(key='champ_query').set_value('Milk Drink').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value['Move'].tolist(), ['Milk Drink'])
        self.assertEqual(app.dataframe[0].value['Target'].tolist(), ['User or adjacent ally'])
        app.text_input(key='champ_query').set_value('no-such-move').run()
        self.assertTrue(any('No matches' in i.value for i in app.info))
        next(b for b in app.button if b.label == '← Emerald Pokédex').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 386)


if __name__ == '__main__':
    unittest.main()
