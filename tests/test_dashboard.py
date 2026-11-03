"""Offline behavior tests for the Streamlit reference browser."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboard'))
from data_access import learning_routes, load_saved, search_routes
from streamlit.testing.v1 import AppTest


class DashboardTests(unittest.TestCase):
    def test_ability_explanation_links_to_pokemon(self):
        app = self.app('pokemon', 1).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.get('popover'))
        next(b for b in app.button if b.label == 'Pokémon with this ability →').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.query_params['page'], 'ability')
        self.assertTrue(any(h.value == 'Pokémon with this ability' for h in app.subheader))

    @classmethod
    def setUpClass(cls):
        cls.data = load_saved()

    def app(self, page='pokedex', identifier=None):
        app = AppTest.from_file(str(ROOT / 'dashboard' / 'app.py'), default_timeout=30)
        app.query_params['page'] = page
        if identifier:
            app.query_params['id'] = str(identifier)
        return app

    def test_search_matches_dbt_snapshot(self):
        result = search_routes(self.data)
        self.assertEqual(len(result), len(self.data['physical_stab_candidates']))
        self.assertEqual(result.pokemon_id.nunique(), 51)
        self.assertEqual(search_routes(self.data, include_inherited=False).pokemon_id.nunique(), 50)

    def test_extended_search_filters_apply_together(self):
        result = search_routes(self.data, min_attack=0, min_power=0, category='Any', stab=False,
                               min_stats={'base_speed': 100, 'base_special_attack': 90},
                               ability_id=9, min_accuracy=95, include_no_check=False)
        self.assertFalse(result.empty)
        species = self.data['pokemon'].set_index('pokemon_id').loc[result.pokemon_id]
        self.assertTrue(species.base_speed.ge(100).all())
        self.assertTrue(species.base_special_attack.ge(90).all())
        allowed = self.data['pokemon_abilities'].query('ability_id == 9').pokemon_id
        self.assertTrue(result.pokemon_id.isin(allowed).all())
        self.assertTrue(result.accuracy.ge(95).all())
        no_check = search_routes(self.data, min_attack=0, min_power=0, category='Any', stab=False, min_accuracy=100)
        self.assertTrue(no_check.accuracy.isna().any())

    def test_required_move_is_separate_from_attack_filter(self):
        # Spore is a status move, but can be required alongside a strong attack.
        result = search_routes(self.data, required_moves=[147])
        self.assertIn(286, result.pokemon_id.tolist())
        self.assertTrue(result.power.ge(80).all())
        direct = search_routes(self.data, required_moves=[147], include_inherited=False)
        self.assertNotIn(286, direct.pokemon_id.tolist())

    def test_inherited_source_and_historical_category(self):
        routes = learning_routes(self.data)
        spore = routes.query('pokemon_id == 286 and move_id == 147')
        self.assertEqual(spore.source_pokemon_id.tolist(), [285])
        self.assertEqual(spore.source_level_learned_at.tolist(), [54])
        moves = self.data['moves'].set_index('name')
        self.assertEqual(moves.loc['shadow-ball', 'category'], 'physical')
        self.assertEqual(moves.loc['bite', 'category'], 'special')
        self.assertEqual(moves.loc['tackle', 'accuracy'], 95)
        self.assertEqual(moves.loc['soft-boiled', 'pp'], 10)
        self.assertEqual(moves.loc['earthquake', 'machine'], 'TM26')
        self.assertEqual(moves.loc['surf', 'machine'], 'HM03')
        self.assertEqual(moves.machine.notna().sum(), 58)
        self.assertEqual(moves.loc['thunder', 'accuracy'], 70)
        self.assertTrue(pd.isna(moves.loc['aerial-ace', 'accuracy']))
        self.assertTrue(search_routes(self.data, min_attack=0, category='status', min_power=0, stab=True).empty)

    def test_move_icons_accuracy_and_full_label_option(self):
        app = self.app('moves').run()
        frame = app.dataframe[0].value
        self.assertTrue(frame['Type'].str.startswith('data:image/svg+xml;base64,').all())
        self.assertTrue(frame['Category'].str.startswith('data:image/svg+xml;base64,').all())
        self.assertEqual(frame.loc[frame['Move'].str.endswith('#Tackle'), 'Acc.'].iloc[0], 95)
        next(toggle for toggle in app.toggle if toggle.label == 'Show full move type/category labels').set_value(True).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.dataframe[0].value['Type'].iloc[0], 'Normal')

    def test_all_pages_render_offline(self):
        with patch('data_access.load_live', side_effect=AssertionError('Offline mode accessed Snowflake')):
            for page, identifier in [('pokedex',None),('pokemon',286),('moves',None),('move',147),
                                      ('abilities',None),('ability',27),('search',None),('compare',None)]:
                with self.subTest(page=page):
                    app = self.app(page, identifier).run()
                    self.assertFalse(app.exception)

    def test_name_filter_and_empty_state(self):
        app = self.app().run()
        app.text_input[0].set_value('Breloom').run()
        self.assertEqual(len(app.dataframe[0].value), 1)
        app.text_input[0].set_value('no-such-pokemon').run()
        self.assertTrue(any('No matches' in item.value for item in app.info))

    def test_connection_failure_does_not_echo_credentials(self):
        app = self.app().run()
        app.radio[0].set_value('Snowflake').run()
        with patch('data_access.load_live', side_effect=ValueError('secret-password-sentinel')):
            next(button for button in app.button if button.label == 'Connect / refresh').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertNotIn('secret-password-sentinel', ' '.join(item.value for item in app.error))

    def test_filtered_names_are_native_links(self):
        app = self.app('moves').run()
        next(field for field in app.text_input if field.label == 'Search moves').set_value('Earthquake').run()
        link = app.dataframe[0].value['Move'].iloc[0]
        self.assertEqual(parse_qs(urlsplit(link).query)['id'], ['89'])
        self.assertEqual(urlsplit(link).fragment, 'Earthquake')
        self.assertFalse(app.exception)

    def test_filters_survive_linked_detail_and_return(self):
        app = self.app('moves').run()
        next(field for field in app.text_input if field.label == 'Search moves').set_value('Earthquake').run()
        link = app.dataframe[0].value['Move'].iloc[0]
        detail = self.app('move', 89)
        detail.query_params['filters'] = parse_qs(urlsplit(link).query)['filters'][0]
        detail.run()
        next(button for button in detail.button if button.label == '← Back to moves').click().run()
        self.assertFalse(detail.exception)
        self.assertEqual(next(field for field in detail.text_input if field.label == 'Search moves').value, 'Earthquake')
        self.assertEqual(len(detail.dataframe[0].value), 1)
        self.assertNotIn('passphrase', link)

    def test_pokedex_numbers_and_filter_restoration(self):
        app = self.app().run()
        app.text_input[0].set_value('286').run()
        self.assertEqual(app.dataframe[0].value['No.'].tolist(), [286])
        next(button for button in app.button if button.key == 'nav_moves').click().run()
        next(button for button in app.button if button.key == 'nav_pokedex').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input[0].value, '286')
        self.assertEqual(len(app.dataframe[0].value), 1)

    def test_grouped_learning_routes_keep_inherited_source(self):
        app = self.app('pokemon', 286).run()
        next(field for field in app.text_input if field.label == 'Find a move').set_value('Spore').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 1)
        table = app.dataframe[0].value
        row = table[table['Move'].str.endswith('#Spore')].iloc[0]
        self.assertEqual(parse_qs(urlsplit(row['Move']).query)['id'], ['147'])
        self.assertEqual(parse_qs(urlsplit(row['Learned by']).query)['id'], ['285'])
        self.assertEqual(row['Source level'], 54)
        self.assertTrue(row['Inherited'])
        self.assertNotIn('Method', app.dataframe[0].value)

    def test_reverse_lookup_groups_without_losing_routes(self):
        app = self.app('move', 147).run()
        self.assertFalse(app.exception)
        frames = [table.value for table in app.dataframe]
        self.assertEqual(sum(len(frame) for frame in frames), len(learning_routes(self.data).query('move_id == 147')))
        rows = pd.concat(frames)
        row = rows[rows['Pokémon'].str.endswith('#Breloom')].iloc[0]
        self.assertEqual(parse_qs(urlsplit(row['Learned by']).query)['id'], ['285'])

    def test_route_sprites_and_optional_inheritance_details(self):
        for page, identifier in [('pokemon', 286), ('move', 147), ('search', None)]:
            with self.subTest(page=page):
                app = self.app(page, identifier).run()
                route_table = next(table for table in app.dataframe if 'Learned by' in table.value)
                config = json.loads(route_table.proto.columns)
                self.assertTrue(config['Learned by']['hidden'])
                self.assertTrue(config['Inherited']['hidden'])
                self.assertTrue(config['Learned by sprite']['hidden'])
                if page in ('move', 'search'):
                    self.assertTrue(route_table.value['Picture'].str.contains('/generation-iii/emerald/', regex=False).all())
                next(toggle for toggle in app.toggle if toggle.label == 'Show inheritance details').set_value(True).run()
                self.assertFalse(app.exception)
                route_table = next(table for table in app.dataframe if 'Learned by' in table.value)
                config = json.loads(route_table.proto.columns)
                self.assertFalse(config['Learned by'].get('hidden', False))
                self.assertFalse(config.get('Inherited', {}).get('hidden', False))
                self.assertEqual(config['Learned by sprite']['type_config']['type'], 'image')

    def test_compact_comparison_includes_all_stats_and_total(self):
        app = self.app('compare').run()
        self.assertFalse(app.exception)
        table = app.dataframe[0].value
        self.assertEqual(table.loc['Attack', 'Breloom'], 130)
        self.assertEqual(table.loc['BST', 'Breloom'], 460)
        self.assertEqual(len(table), 7)


if __name__ == '__main__':
    unittest.main()
