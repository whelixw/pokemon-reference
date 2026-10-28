"""Champions reference preview, isolated from the Emerald rules and connection."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DIRECTORY = Path(__file__).parent / 'data' / 'champions'
TARGETS = {'normal': 'One adjacent Pokémon', 'self': 'User',
           'adjacentAllyOrSelf': 'User or adjacent ally', 'adjacentAlly': 'Adjacent ally',
           'allAdjacent': 'All adjacent Pokémon', 'allAdjacentFoes': 'All adjacent foes',
           'allySide': 'Ally side', 'foeSide': 'Foe side', 'all': 'Entire field',
           'any': 'Any other Pokémon', 'randomNormal': 'Random adjacent foe',
           'allyTeam': 'Ally team', 'scripted': 'Depends on effect'}
FEATURES = {'Contact': 'contact', 'Sound': 'sound', 'Powder': 'powder', 'Punch': 'punch',
            'Bite': 'bite', 'Slicing': 'slicing', 'Bullet / bomb': 'bullet',
            'Blocked by Protect (base flag)': 'protect'}


@st.cache_data
def load_snapshot(manifest_content):
    manifest = json.loads(manifest_content)
    tables = {}
    for name, metadata in manifest['outputs'].items():
        content = (DIRECTORY / f'{name}.json').read_bytes()
        if hashlib.sha256(content).hexdigest() != metadata['sha256']:
            raise ValueError(f'Champions snapshot checksum mismatch: {name}')
        tables[name] = json.loads(content)
    return manifest, tables


def filter_moves(moves, query='', available=True, move_type='Any', category='Any', features=(), priority=False, spread=False):
    return [m for m in moves
            if (not available or m['available'])
            and (not query or query.casefold() in (m['name'] + ' ' + (m['desc'] or '')).casefold())
            and (move_type == 'Any' or m['type'] == move_type)
            and (category == 'Any' or m['category'] == category)
            and all(m['flags'].get(FEATURES[feature]) for feature in features)
            and (not priority or m['priority'] > 0)
            and (not spread or m['target'] in ('allAdjacent', 'allAdjacentFoes'))]


def render():
    from champions_dex import render_page, go, symbols, pokemon_table
    view = st.query_params.get('view', 'dex')
    with st.sidebar:
        st.markdown('### Champions')
        st.caption('REGULATION M-C · DOUBLES')
        for target, label in [('dex','Pokédex'),('moves','Moves'),('abilities','Abilities'),('items','Items'),('compare','Compare Pokémon'),('audit','Mechanics & source')]:
            active = {'pokemon':'dex','ability':'abilities','item':'items'}.get(view,view)
            if st.button(label, key='mc_nav_'+target, width='stretch', type='primary' if active==target else 'secondary'):
                go(target)
        with st.expander('Display & symbols'):
            st.toggle('Show full type/category labels', key='mc_labels')
            from icons import svg
            st.markdown(' '.join(svg('category',name)+' '+name.title() for name in ['physical','special','status']),unsafe_allow_html=True)
        if st.button('← Emerald Pokédex', width='stretch'):
            st.query_params.from_dict({'page': 'pokedex'})
            st.rerun()
    try:
        manifest, tables = load_snapshot((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        st.error(f'Champions data could not be loaded: {error}')
        return
    st.caption('Regulation M-C · Pinned Showdown rules · Official event verification pending')
    if view not in ('moves', 'audit'):
        render_page(view, tables)
        return
    st.title('Moves' if view == 'moves' else 'Mechanics & source')
    moves_tab, mechanics_tab, audit_tab = st.tabs(['Moves', 'Verified source mechanics', 'Source audit'])
    with moves_tab:
        a, b, c = st.columns([2, 1, 1])
        query = a.text_input('Search Champions moves', placeholder='Name or effect', key='champ_query')
        move_type = b.selectbox('Move type', ['Any', *sorted({m['type'] for m in tables['moves']})], key='champ_type')
        category = c.selectbox('Category', ['Any', 'Physical', 'Special', 'Status'], key='champ_category')
        with st.expander('Competitive filters'):
            features = st.multiselect('Required move features', list(FEATURES), key='champ_features')
            a, b, c = st.columns(3)
            priority = a.checkbox('Positive priority only', key='champ_priority')
            spread = b.checkbox('Spread attacks only', key='champ_spread')
            available = c.checkbox('Available in source only', value=True, key='champ_available')
        results = sorted(filter_moves(tables['moves'], query, available, move_type, category, features, priority, spread), key=lambda m: m['name'])
        st.caption(f'{len(results)} moves · Base flags can have ability, item or field exceptions.')
        if not results:
            st.info('No matches. Try broadening your filters.')
        else:
            rows = [{'Move': m['name'], 'Type': m['type'], 'Category': m['category'],
                     'Power': m['basePower'] or None, 'Acc.': None if m['accuracy'] is True else m['accuracy'],
                     'PP': m['pp'], 'Priority': m['priority'], 'Target': TARGETS.get(m['target'], m['target']),
                     'Contact': bool(m['flags'].get('contact')), 'Available': m['available']} for m in results]
            frame = pd.DataFrame(rows)
            config = symbols(frame)
            config['Acc.'] = st.column_config.NumberColumn(format='%d%%')
            st.dataframe(frame, hide_index=True, width='stretch', height=min(400, 35*(len(rows)+1)+4),
                         placeholder='—', column_config=config)
            st.caption('— accuracy: no normal accuracy check. — power: status move or damage determined by an effect.')
            by_id = {m['id']: m for m in results}
            requested = st.query_params.get('id')
            options = list(by_id)
            selected = st.selectbox('Inspect move', options, index=options.index(requested) if requested in options else 0, format_func=lambda mid: by_id[mid]['name'], key='champ_detail')
            move = by_id[selected]
            st.subheader(move['name'])
            st.write('Restores ½ of the user’s or an adjacent ally’s maximum HP.' if selected == 'milkdrink' else (move['desc'] or 'No source description available.'))
            st.caption('Source description; conditional effects and inherited wording may require further verification.')
            if selected == 'milkdrink':
                st.success('Champions override verified: heals the user or an adjacent ally for ½ of the target’s maximum HP.')
            a, b = st.columns(2)
            a.write('**Target:** ' + TARGETS.get(move['target'], move['target']))
            b.write('**Features:** ' + (', '.join(label for label, flag in FEATURES.items() if move['flags'].get(flag)) or 'None of the listed flags'))
            with st.expander('Effect details and source'):
                st.write('Original source description: ' + (move['desc'] or 'Unavailable'))
                effect_fields = ['heal','drain','recoil','multihit','status','volatileStatus','sideCondition',
                                 'weather','terrain','pseudoWeather','boosts','self','secondaries',
                                 'selfSwitch','forceSwitch','breaksProtect','ignoreAbility','scripted_callbacks']
                st.json({key:move[key] for key in effect_fields if move.get(key)})
                st.caption('Fractions are numerator/denominator pairs. Scripted effects need simulator context; they are not missing or zero effects.')
                st.link_button('Open pinned Champions overrides', f"{manifest['source']}/blob/{manifest['revision']}/data/mods/champions/moves.ts")
            with st.expander('Pokémon with this move in the source'):
                ids = {row['pokemon_id'] for row in tables['learnsets'] if row['move_id'] == selected}
                learners = [p for p in tables['species'] if p['id'] in ids and p['mc_species_allowed']]
                if learners:
                    pokemon_table(learners, 'mc_move_learners')
                else:
                    st.caption('No source-available learners in this snapshot.')
                st.caption('Includes battle forms. Individual learning options do not establish a legal complete set or team.')
            st.download_button('Download filtered move data', json.dumps(results, indent=2), 'champions-moves.json', 'application/json')
    with mechanics_tab:
        st.subheader('Champions-specific checks')
        st.markdown('**Milk Drink** · Targets the user or an adjacent ally; heals ½ of the target’s maximum HP.\n\n'
                    '**Paralysis** · 1 in 8 (12.5%) chance of preventing a move. Speed is halved with rounding down; '
                    'Quick Feet bypasses that penalty.\n\n'
                    '**Stat calculation** · The audited standard formula uses base stat + stat points + 75 for HP; '
                    'other stats use base stat + stat points + 20 before the alignment/nature modifier. '
                    'Special cases and alternative formats need their own handling.')
        st.caption('These checks execute the pinned Showdown implementation. They are not independent in-game tests.')
        st.json(tables['checks'], expanded=False)
        st.link_button('Paralysis override source', f"{manifest['source']}/blob/{manifest['revision']}/data/mods/champions/conditions.ts")
    with audit_tab:
        st.markdown(f"**Source revision:** [{manifest['revision'][:12]}]({manifest['source']}/tree/{manifest['revision']})\n\n"
                    f"**Source commit:** {manifest['source_commit_date']}\n\n"
                    f"**Retrieved:** {manifest['retrieved_at']}")
        st.write(f"{manifest['available_moves']} source-available moves · {len(tables['species'])} source-available forms · {len(tables['learnsets']):,} learning options")
        st.markdown('**VGC formats present in this snapshot**')
        for fmt in tables['formats']:
            st.write(f"{fmt['name']} · {fmt['gameType']} · bring {fmt['min_team_size']}, pick {fmt['picked_team_size']} · {fmt['stat_point_limit']} stat points total")
        st.markdown('**Verification still needed**')
        for limitation in manifest['limitations']:
            st.write('• ' + limitation)
        st.caption('Items and abilities now have reference pages. Full condition explanations and stat-range tools remain later increments.')
        st.json(manifest['audit_counts'])
        st.link_button('Official Champions gameplay and regulation overview', 'https://champions.pokemon.com/en-us/gameplay/')
    st.caption('Data and mechanics: Pokémon Showdown contributors (MIT). Sprites: Pokémon Showdown. Pokémon © Nintendo / Game Freak / Creatures.')
