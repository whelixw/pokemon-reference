"""Saved-data and read-only Snowflake loading, independent of the UI."""
import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ['pokemon', 'types', 'abilities', 'moves', 'pokemon_types', 'pokemon_abilities',
          'pokemon_moves', 'evolutions', 'type_effectiveness', 'pokemon_defensive_matchups',
          'pokemon_evolution_ancestry', 'pokemon_move_options', 'physical_stab_candidates']
STATS = {'base_hp': 'HP', 'base_attack': 'Attack', 'base_defense': 'Defense',
         'base_special_attack': 'Sp. Atk', 'base_special_defense': 'Sp. Def', 'base_speed': 'Speed'}
COLORS = {'normal': '#8b8d77', 'fire': '#cb6741', 'water': '#4487b3', 'electric': '#b48d24',
          'grass': '#4b8c54', 'ice': '#469b9e', 'fighting': '#ad574e', 'poison': '#925b98',
          'ground': '#a8894c', 'flying': '#8078ac', 'psychic': '#bd5f82', 'bug': '#7d913a',
          'rock': '#99854c', 'ghost': '#736293', 'dragon': '#6b65ad', 'dark': '#685a53', 'steel': '#737f8d', 'fairy': '#c66d9c', 'stellar': '#599e9d', 'unknown': '#777777'}


def pretty(value):
    names = {'mr-mime': 'Mr. Mime', 'nidoran-f': 'Nidoran ♀', 'nidoran-m': 'Nidoran ♂',
             'ho-oh': 'Ho-Oh', 'farfetchd': "Farfetch’d", 'deoxys': 'Deoxys (Speed Form)'}
    names.update({'level_up': 'Level up', 'machine': 'TM / HM', 'breeding': 'Breeding', 'tutor': 'Move tutor'})
    return names.get(str(value), str(value).replace('-', ' ').replace('_', ' ').title())


def normalize(tables):
    for frame in tables.values():
        frame.columns = frame.columns.str.lower()
        for column in frame:
            if column.endswith('_id') or column in ('slot', 'evolution_steps', 'level_learned_at', 'source_level_learned_at', 'power', 'accuracy', 'pp'):
                frame[column] = pd.to_numeric(frame[column], errors='raise').astype('Int64')
            if column in ('damaging', 'variable_power', 'is_inherited'):
                frame[column] = frame[column].map(lambda value: str(value).lower() in ('true', '1'))
    return tables


def load_saved():
    return normalize({name: pd.read_csv(ROOT / 'dashboard' / 'data' / f'{name}.csv') for name in TABLES})


def load_live(passphrase=''):
    import yaml
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    profile_path = ROOT / 'profiles.yml'
    if not profile_path.exists():
        raise ValueError('Local Snowflake profile not found. Saved dataset remains available.')
    profile = yaml.safe_load(profile_path.read_text())['pokemon_emerald']
    output = profile['outputs'][profile.get('target', 'dev')]

    def resolve(value):
        if not isinstance(value, str) or '{{' not in value:
            return value
        match = re.fullmatch(r"\s*\{\{\s*env_var\(['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]*)['\"])?\)\s*\}\}\s*", value)
        if not match:
            raise ValueError('Unsupported profile expression; use the documented environment-variable profile.')
        name, default = match.groups()
        if name == 'DBT_KEY_PASSPHRASE' and passphrase:
            return passphrase
        result = os.environ.get(name, default)
        if result is None:
            raise ValueError(f'Set {name} in the terminal before starting the app, or enter the key passphrase here.')
        return result

    allowed = ('account', 'user', 'password', 'authenticator', 'warehouse', 'role', 'database', 'schema')
    connection_args = {key: resolve(output[key]) for key in allowed if key in output}
    if output.get('private_key_path'):
        key_password = resolve(output.get('private_key_passphrase', ''))
        key = serialization.load_pem_private_key(Path(resolve(output['private_key_path'])).expanduser().read_bytes(),
                                                password=key_password.encode() if key_password else None)
        connection_args['private_key'] = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                                           serialization.NoEncryption())
    database, schema = str(connection_args['database']), str(connection_args['schema'])
    quote = lambda name: '"' + name.replace('"', '""') + '"'
    tables = {}
    with snowflake.connector.connect(**connection_args) as connection:
        for name in TABLES:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT * FROM {quote(database)}.{quote(schema)}.{quote(name.upper())}')
                tables[name] = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
    if 'accuracy' not in tables['moves'].columns.str.lower():
        raise ValueError('Moves view is missing accuracy. Refresh raw_moves and its downstream models first.')
    return normalize(tables)


def enriched(tables):
    pokemon = tables['pokemon'].copy()
    types = tables['pokemon_types'].merge(tables['types'], on='type_id').sort_values('slot')
    pokemon['types'] = pokemon.pokemon_id.map(types.groupby('pokemon_id')['name'].agg(list))
    pokemon['display_name'] = pokemon.name.map(pretty)
    return pokemon


def learning_routes(tables, include_inherited=True):
    routes = tables['pokemon_move_options'].copy()
    if not include_inherited:
        routes = routes[~routes.is_inherited]
    routes = routes.merge(tables['moves'], on='move_id')
    routes = routes.merge(tables['pokemon'][['pokemon_id', 'name']].rename(columns={'pokemon_id': 'source_pokemon_id', 'name': 'source_name'}), on='source_pokemon_id')
    types = tables['pokemon_types'][['pokemon_id', 'type_id']].assign(stab=True)
    routes = routes.merge(types, on=['pokemon_id', 'type_id'], how='left')
    routes['stab'] = routes['stab'].eq(True) & routes.damaging
    return routes


def search_routes(tables, min_attack=90, category='physical', min_power=80, stab=True,
                  include_inherited=True, required_moves=(), learning_methods=(),
                  min_stats=None, ability_id=None, min_accuracy=0, include_no_check=True):
    routes = learning_routes(tables, include_inherited)
    eligible = tables['pokemon'].loc[tables['pokemon'].base_attack >= min_attack, 'pokemon_id']
    for stat, minimum in (min_stats or {}).items():
        if stat not in STATS:
            raise ValueError(f'Unknown base stat: {stat}')
        eligible = eligible[eligible.isin(tables['pokemon'].loc[tables['pokemon'][stat] >= minimum, 'pokemon_id'])]
    if ability_id is not None:
        eligible = eligible[eligible.isin(tables['pokemon_abilities'].loc[tables['pokemon_abilities'].ability_id == ability_id, 'pokemon_id'])]
    result = routes[routes.pokemon_id.isin(eligible)]
    if min_accuracy:
        accuracy_matches = result.accuracy.ge(min_accuracy)
        if include_no_check:
            accuracy_matches |= result.accuracy.isna()
        result = result[accuracy_matches]
    elif not include_no_check:
        result = result[result.accuracy.notna()]

    if category != 'Any':
        result = result[result.category == category]
    if min_power:
        result = result[result.power.ge(min_power) & ~result.variable_power & result.damaging]
    if stab:
        result = result[result.stab]
    if learning_methods:
        result = result[result.learning_method.isin(learning_methods)]
    if required_moves:
        # All-of move requirement applies to the whole available learnset, not
        # only the particular attacks that pass the power/category filters.
        selected = routes[routes.move_id.isin(required_moves)]
        counts = selected.groupby('pokemon_id').move_id.nunique()
        result = result[result.pokemon_id.isin(counts[counts == len(set(required_moves))].index)]
    return result
