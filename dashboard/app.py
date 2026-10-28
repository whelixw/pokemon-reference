"""Emerald-only reference browser. Run with streamlit run dashboard/app.py."""
from html import escape
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, quote

import pandas as pd
import streamlit as st

from data_access import COLORS, ROOT, STATS, enriched, learning_routes, load_live, load_saved, pretty, search_routes
from icons import icon_uri, svg

st.set_page_config(page_title='Champions reference' if st.query_params.get('page') == 'champions' else 'Emerald Pokédex', page_icon='🌿', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container {max-width:1240px;padding-top:3.75rem;padding-bottom:2rem;}
h1,h2,h3 {letter-spacing:-.035em;color:#214f3c;}
h1 {font-size:2rem !important;} h2 {font-size:1.35rem !important;}
[data-testid="stSidebar"] {border-right:1px solid #dce5db;}
.eyebrow {font-size:11px;font-weight:750;letter-spacing:.18em;color:#5f7e69;margin-bottom:2px;}
.subtitle {color:#6e7f73;font-size:14px;line-height:1.45;margin-bottom:8px;}
.type-pill {display:inline-block;border-radius:5px;padding:4px 12px;margin:0 5px 6px 0;
color:white;font-size:11px;letter-spacing:.08em;font-weight:750;text-transform:uppercase;}
.portrait {background:radial-gradient(circle,#e7efdd 0%,#f5f7ef 58%,transparent 72%);
display:flex;align-items:center;justify-content:center;min-height:185px;border-radius:18px;}
.portrait img {width:180px;max-width:100%;height:180px;object-fit:contain;}
.summary {border:1px solid #dde5da;background:white;border-radius:12px;padding:20px 24px;margin:8px 0 20px;}
.stat {display:grid;grid-template-columns:76px 35px 1fr;align-items:center;gap:10px;margin:10px 0;font-size:13px;}
.track {height:10px;background:#edf1e9;border-radius:4px;overflow:hidden;}
.fill {height:100%;border-radius:4px;background:#6d9870;}
.match {border:1px solid #e0e6dc;border-radius:7px;padding:10px 6px;text-align:center;background:white;}
.match small {display:block;color:#758174;font-size:10px;margin-bottom:4px;}
.match strong {font-size:20px;}
.brand {font-size:24px;font-weight:800;color:#24583f;letter-spacing:-.06em;margin:8px 0 0;}
.brand-sub {font-size:10px;letter-spacing:.2em;color:#6d836d;margin:3px 0 12px;}
div[data-testid="stMetric"] {background:white;border:1px solid #e0e6da;border-radius:9px;padding:8px 12px;}
.footer {border-top:1px solid #e0e6dc;margin-top:20px;padding-top:14px;font-size:11px;color:#798775;}
[data-testid="stVerticalBlock"] {gap:.65rem;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.5rem;}
[data-testid="stHeadingWithActionElements"] h1 {padding-top:0;padding-bottom:.35rem;}
[data-testid="stMetricValue"] {font-size:1.5rem;}
@media (max-width:640px) {
    .block-container {padding:3.75rem 1rem 1rem;}
    h1 {font-size:1.7rem !important;}
    .portrait {min-height:130px;}
    .portrait img {height:130px;width:130px;}
}
</style>''', unsafe_allow_html=True)


@st.cache_data
def saved_data(snapshot_version):
    return load_saved()


def browse_context():
    return json.dumps(st.session_state.get('browse_filters', {}), separators=(',', ':'))


def remembered(kind, label, area=st, **kwargs):
    """Keep non-sensitive browsing controls across page changes and linked tabs."""
    store = st.session_state.setdefault('browse_filters', {})
    scope = store.setdefault(page, {})
    key = kwargs.pop('key', f'filter_{page}_{label}')
    saved = scope.get(label)
    if key not in st.session_state and saved is not None:
        options = kwargs.get('options')
        valid = True
        if options is not None:
            valid = all(item in options for item in saved) if kind == 'multiselect' and isinstance(saved, list) else saved in options
        if kind in ('number_input', 'slider'):
            valid = isinstance(saved, (int, float)) and kwargs.get('min_value', saved) <= saved <= kwargs.get('max_value', saved)
        if kind in ('checkbox', 'toggle'):
            valid = isinstance(saved, bool)
        if kind == 'text_input':
            valid = isinstance(saved, str)
        if valid:
            st.session_state[key] = saved
    value = getattr(area, kind)(label, key=key, **kwargs)
    scope[label] = value
    return value


def go(page, identifier=None):
    st.session_state['nav_version'] = st.session_state.get('nav_version', 0) + 1
    params = {'page': page, 'filters': browse_context()}
    if identifier is not None:
        params['id'] = str(int(identifier))
    st.query_params.from_dict(params)
    st.rerun()


def artwork(pid):
    source = 10003 if int(pid) == 386 else int(pid)
    return f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{source}.png'


def sprite(pid):
    source = 386 if int(pid) == 386 else int(pid)
    return f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-iii/emerald/{source}.png'


def portrait(pid, label):
    st.markdown(f'<div class="portrait"><img src="{artwork(pid)}" alt="{escape(label)}" /></div>', unsafe_allow_html=True)


def badges(types):
    st.markdown(''.join(f'<span class="type-pill" style="background:{COLORS[t]}">{escape(t)}</span>' for t in types), unsafe_allow_html=True)


def title(text, eyebrow='POKÉMON EMERALD', subtitle=''):
    st.markdown(f'<div class="eyebrow">{escape(eyebrow)}</div>', unsafe_allow_html=True)
    st.title(text)
    if subtitle:
        st.markdown(f'<div class="subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def selectable(frame, page, id_column, key, column_config=None, height=480, extra_links=None):
    if frame.empty:
        st.info('No matches. Try broadening your filters.')
        return
    name_column = {'pokemon': 'Pokémon', 'move': 'Move', 'ability': 'Ability'}[page]
    links = {name_column: (page, id_column), **(extra_links or {})}
    config = {target_id: None for _, target_id in links.values()}
    config.update(column_config or {})
    frame = frame.copy()
    for column, (target_page, target_id) in links.items():
        if target_page != 'pokemon':
            continue
        picture_column = 'Picture' if column == 'Pokémon' else f'{column} sprite'
        if picture_column not in frame:
            frame.insert(frame.columns.get_loc(column), picture_column, frame[target_id].map(sprite))
        config[picture_column] = st.column_config.ImageColumn('', width=45)
    if not st.session_state.get('show_inheritance_details', False):
        for column in ('Learned by', 'Learned by sprite', 'Inherited'):
            if column in frame:
                config[column] = None
    if not st.session_state.get('full_move_labels', False):
        for column, kind in [('Type', 'type'), ('Category', 'category')]:
            if column in frame and page == 'move':
                frame = frame.copy()
                frame[column] = frame[column].map(lambda label: icon_uri(kind, label.lower()))
                config[column] = st.column_config.ImageColumn(column if kind == 'type' else 'Cat.', width=52,
                    help='See the icon legend, or enable full labels in the sidebar.')
    # Keep labels in the URL fragment so native links retain readable names.
    # Fragments do not affect the query-parameter route.
    display = frame.reset_index(drop=True).copy()
    current_url = urlsplit(st.context.url or 'http://localhost:8502/')
    base_url = f'{current_url.scheme}://{current_url.netloc}{current_url.path}'
    for column, (target_page, target_id) in links.items():
        display[column] = [f'{base_url}?page={target_page}&id={int(identifier)}&filters={quote(browse_context(), safe="")}#{label}'
                           for identifier, label in zip(display[target_id], display[column])]
        if column not in config or config[column] is not None:
            config[column] = st.column_config.LinkColumn(column, display_text=r'#(.*)$')
    st.dataframe(display, hide_index=True, width='stretch',
                 height=min(height, max(120, 35 * (len(frame) + 1) + 4)),
                 column_config=config, placeholder='—', row_height=35, key=key)


def grouped_routes(view, page, id_column, key, extra_links=None, column_config=None):
    if view.empty:
        st.info('No matches. Try broadening your filters.')
        return
    methods = [method for method in ['Level up', 'TM / HM', 'Move tutor', 'Breeding']
               if view['Method'].eq(method).any()]
    tabs = st.tabs([f'{method} ({view["Method"].eq(method).sum()})' for method in methods])
    for method, tab in zip(methods, tabs):
        with tab:
            group = view[view['Method'] == method]
            selectable(group.drop(columns='Method'), page, id_column, f'{key}_{method}',
                       height=400, extra_links=extra_links, column_config=column_config)



def pokemon_table(frame, key='pokemon_table'):
    view = frame[['pokemon_id', 'display_name', 'types', 'bst', *STATS]].copy()
    view.insert(1, 'No.', view.pokemon_id)
    view.insert(2, 'Picture', view.pokemon_id.map(sprite))
    view['types'] = view.types.map(lambda ts: ' / '.join(pretty(t) for t in ts))
    view = view.rename(columns={'display_name': 'Pokémon', 'types': 'Type', 'bst': 'BST', **STATS})
    selectable(view, 'pokemon', 'pokemon_id', key, {'Picture': st.column_config.ImageColumn(''), 'No.': st.column_config.NumberColumn('No.', format='%03d', width=55)})


page = st.query_params.get('page', 'pokedex')
if page == 'champions':
    from champions import render
    render()
    st.stop()
if 'browse_filters' not in st.session_state:
    try:
        initial_filters = json.loads(st.query_params.get('filters', '{}'))
        if not isinstance(initial_filters, dict) or any(not isinstance(value, dict) for value in initial_filters.values()):
            initial_filters = {}
    except (ValueError, TypeError):
        initial_filters = {}
    st.session_state['browse_filters'] = initial_filters

groups = {'pokemon': 'pokedex', 'move': 'moves', 'ability': 'abilities'}
active = groups.get(page, page)
with st.sidebar:
    st.markdown('<div class="brand">Emerald</div><div class="brand-sub">POKÉDEX & FIELD GUIDE</div>', unsafe_allow_html=True)
    for section, destinations in [
        ('BROWSE', [('pokedex', 'Pokédex'), ('moves', 'Moves'), ('abilities', 'Abilities')]),
        ('TEAM TOOLS', [('search', 'Advanced search'), ('compare', 'Compare Pokémon')]),
    ]:
        st.caption(section)
        for target, label in destinations:
            if st.button(label, key=f'nav_{target}', width='stretch', type='primary' if active == target else 'secondary'):
                go(target)
    st.caption('COMPETITIVE REFERENCE')
    if st.button('Champions preview', key='nav_champions', width='stretch'):
        go('champions')
    with st.expander('Display & browsing help'):
        st.toggle('Show full move type/category labels', value=False, key='full_move_labels')
        st.toggle('Show inheritance details', value=False, key='show_inheritance_details',
                  help='Show the original learning Pokémon, its sprite and whether the route is inherited.')
        st.caption('Names in tables open details in a new tab. Your filters are carried over; data connections stay in the original tab.')
        st.caption('386 Pokémon · Generation III · Vanilla Emerald stats, abilities & learnsets')
    with st.expander('Data connection'):
        public_mode = os.environ.get('POKEMON_PUBLIC_MODE') == '1'
        mode = 'Saved dataset' if public_mode else st.radio('Data source', ['Saved dataset', 'Snowflake'], key='data_mode')
        if mode == 'Snowflake':
            st.caption('Use the existing local connection. All queries are read-only.')
            passphrase = st.text_input('Key passphrase (if not set in terminal)', type='password', key='connection_passphrase')
            if st.button('Connect / refresh'):
                try:
                    with st.spinner('Loading Emerald data…'):
                        loaded = load_live(passphrase)
                    st.session_state['live_tables'] = loaded
                    st.success('Connected')
                except Exception as error:
                    # Do not echo connection exceptions that might contain credentials.
                    st.error('Could not load Snowflake data. Check your connection settings, passphrase and deployed views.')
        else:
            st.caption('Packaged, validated model results. No Snowflake login needed.')

if mode == 'Snowflake' and 'live_tables' not in st.session_state:
    title('Connect to your Emerald data')
    st.info('Open Data connection in the sidebar to connect, or choose Saved dataset to browse immediately.')
    st.stop()
try:
    data = st.session_state['live_tables'] if mode == 'Snowflake' else saved_data((ROOT / 'dashboard' / 'data' / 'manifest.json').stat().st_mtime_ns)
except (FileNotFoundError, ValueError):
    st.error('Saved data is missing or invalid. Rebuild it using the dashboard run instructions.')
    st.stop()
if not {'accuracy', 'pp', 'machine'}.issubset(data['moves'].columns):
    st.info('The loaded move data needs refreshing for accuracy, PP and TM/HM numbers. Update the Snowflake move model, then use Connect / refresh, or choose Saved dataset.')
    st.stop()
pokedex = enriched(data)
pokemon_names = pokedex.set_index('pokemon_id').display_name.to_dict()
move_names = data['moves'].set_index('move_id').name.map(pretty).to_dict()
type_names = data['types'].set_index('type_id').name.to_dict()
regular_types = sorted(data['types'].loc[data['types'].type_id <= 17, 'name'])


def icon_legend():
    with st.expander('Type & category icon legend'):
        for kind, names in [('category', ['physical', 'special', 'status']), ('type', regular_types + ['unknown'])]:
            markup = ''.join(f'<span style="display:inline-flex;align-items:center;gap:6px;margin:5px 16px 5px 0">{svg(kind,name)}<span>{pretty(name)}</span></span>' for name in names)
            st.markdown(markup, unsafe_allow_html=True)
        st.caption('Category icons describe Gen 3 mechanics. “—” accuracy means no normal accuracy check applies; percentages are base values, not calculated hit chances.')


def valid_id(table, column):
    try:
        identifier = int(st.query_params.get('id', '0'))
    except ValueError:
        identifier = 0
    row = table[table[column] == identifier]
    if row.empty:
        st.info('This entry could not be found.')
        st.stop()
    return identifier, row.iloc[0]


if page == 'pokedex':
    title('Pokédex', subtitle='Find Pokémon by name, number, type or generation.')
    a, b, c = st.columns([2, 1, 1])
    query = remembered('text_input', 'Search Pokémon', area=a, placeholder='Name or National Pokédex number')
    chosen_type = remembered('selectbox', 'Type', area=b, options=['All types'] + regular_types, format_func=pretty)
    generation = remembered('selectbox', 'Introduced in', area=c, options=['All generations', 'Generation I', 'Generation II', 'Generation III'])
    results = pokedex.copy()
    if query:
        results = results[results.display_name.str.contains(query, case=False, regex=False) | results.pokemon_id.astype(str).eq(query.lstrip('0'))]
    if chosen_type != 'All types':
        results = results[results.types.map(lambda ts: chosen_type in ts)]
    if generation != 'All generations':
        low, high = {'Generation I': (1, 151), 'Generation II': (152, 251), 'Generation III': (252, 386)}[generation]
        results = results[results.pokemon_id.between(low, high)]
    st.markdown(f'**{len(results)} Pokémon**')
    pokemon_table(results)

elif page == 'pokemon':
    pid, row = valid_id(pokedex, 'pokemon_id')
    back, previous, following = st.columns([4, 1, 1])
    if back.button('← Back to Pokédex'):
        go('pokedex')
    if pid > 1 and previous.button(f'← #{pid-1:03d}'):
        go('pokemon', pid - 1)
    if pid < 386 and following.button(f'#{pid+1:03d} →'):
        go('pokemon', pid + 1)
    picture, information, stats = st.columns([1.05, 1.25, 1.6], gap='large')
    with picture:
        portrait(pid, row.display_name)
        st.caption('Artwork · PokéAPI / Pokémon')
    with information:
        title(row.display_name, eyebrow=f'NATIONAL POKÉDEX · #{pid:03d}')
        badges(row.types)
        st.markdown('**Abilities in Emerald**')
        assignments = data['pokemon_abilities'].query('pokemon_id == @pid').merge(data['abilities'], on='ability_id').sort_values('slot')
        for ability in assignments.itertuples():
            if st.button(pretty(ability.name), key=f'ability_{ability.ability_id}'):
                go('ability', ability.ability_id)
            st.caption(ability.description)
        if st.button('Compare this Pokémon'):
            st.session_state['compare_ids'] = [pid]
            go('compare')
    with stats:
        st.subheader('Base stats')
        markup = ''.join(f'<div class="stat"><span>{label}</span><strong>{int(row[col])}</strong><div class="track"><div class="fill" style="width:{int(row[col])/255*100}%"></div></div></div>' for col, label in STATS.items())
        st.markdown(markup, unsafe_allow_html=True)
        st.markdown(f'**Base stat total · {int(row.bst)}**')
    details, learnset, evolution = st.tabs(['Type defenses', 'Moves learned', 'Evolution family'])
    with details:
        st.subheader('Type defenses')
        st.caption('Incoming attack multipliers. Abilities and battle conditions are not applied.')
        defenses = data['pokemon_defensive_matchups'].query('pokemon_id == @pid and attacking_type_id <= 17')
        def defense_group(label, explanation, subset, accent, background):
            st.markdown(f'**{label}** · {explanation}')
            if subset.empty:
                st.caption('None')
                return
            cards = []
            for defense in subset.itertuples():
                type_name = type_names[defense.attacking_type_id]
                multiplier = {0.5: '½×', 0.25: '¼×'}.get(float(defense.modifier), f'{float(defense.modifier):g}×')
                cards.append(
                    f'<div style="display:flex;align-items:center;gap:12px;padding:7px 10px;'
                    f'border:1px solid {accent};border-radius:8px;background:{background}">'
                    f'<span class="type-pill" style="background:{COLORS[type_name]};margin:0;min-width:72px;text-align:center">{escape(pretty(type_name))}</span>'
                    f'<strong style="color:{accent};font-size:20px;min-width:42px;text-align:right">{multiplier}</strong></div>')
            st.markdown('<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 18px">' + ''.join(cards) + '</div>', unsafe_allow_html=True)

        defense_group('Weaknesses', 'takes more damage',
                      defenses[defenses.modifier > 1].sort_values('modifier', ascending=False), '#a23d30', '#fff4ef')
        defense_group('Resistances', 'takes less damage',
                      defenses[(defenses.modifier > 0) & (defenses.modifier < 1)].sort_values('modifier'), '#27694c', '#edf7ef')
        defense_group('Immunities', 'takes no damage',
                      defenses[defenses.modifier == 0], '#585a83', '#f2f0fa')
        neutral = defenses[defenses.modifier == 1]
        with st.expander(f'Neutral damage · {len(neutral)} types · 1×'):
            defense_group('Neutral', 'takes normal damage', neutral, '#58685d', '#f4f6f2')
        st.caption('4× = quadruple damage · 2× = double · ½× = half · ¼× = quarter · 0× = no damage')
        if pid == 292:
            st.info('Shedinja has Wonder Guard. The values above show its types only, not Wonder Guard’s protection.')
    with learnset:
        st.subheader('Emerald learnset')
        include = st.toggle('Include earlier evolutions', value=True)
        routes = learning_routes(data, include).query('pokemon_id == @pid')
        a, b = st.columns([2, 1])
        move_query = a.text_input('Find a move', placeholder='Search this learnset')
        methods = b.multiselect('Learning method', ['level_up', 'machine', 'tutor', 'breeding'], format_func=pretty)
        if move_query:
            routes = routes[routes.name.str.contains(move_query.replace(' ', '-'), case=False, regex=False)]
        if methods:
            routes = routes[routes.learning_method.isin(methods)]
        st.caption('Level refers to the original learning Pokémon. Evolution timing and complete moveset legality are not calculated.')
        icon_legend()
        view = routes[['move_id', 'name', 'type_id', 'category', 'power', 'accuracy', 'pp', 'machine', 'learning_method', 'source_pokemon_id', 'source_name', 'source_level_learned_at', 'is_inherited']].copy()
        view.loc[view.learning_method != 'machine', 'machine'] = None
        for column in ['name', 'category', 'learning_method', 'source_name']:
            view[column] = view[column].map(pretty)
        view['type_id'] = view.type_id.map(type_names).map(pretty)
        view = view.rename(columns={'name':'Move', 'type_id':'Type', 'category':'Category', 'power':'Power', 'accuracy':'Acc.', 'pp':'PP', 'machine':'TM / HM', 'learning_method':'Method', 'source_name':'Learned by', 'source_level_learned_at':'Source level', 'is_inherited':'Inherited'})
        grouped_routes(view, 'move', 'move_id', 'learnset', column_config={'Acc.': st.column_config.NumberColumn('Acc.', format='%d%%', width=60)},
                   extra_links={'Learned by': ('pokemon', 'source_pokemon_id')})
    with evolution:
        st.subheader('Evolution family')
        # Include connected relatives for context, not for move inheritance.
        family = {pid}
        edges = data['evolutions']
        while True:
            connected = edges[edges.from_pokemon_id.isin(family) | edges.to_pokemon_id.isin(family)]
            expanded = family | set(connected.from_pokemon_id) | set(connected.to_pokemon_id)
            if expanded == family:
                break
            family = expanded
        if connected.empty:
            st.caption('No evolution paths in Emerald.')
        if not connected.empty:
            def family_node(member, path=frozenset()):
                if member in path:
                    return ''
                children = connected[connected.from_pokemon_id == member]
                highlight = '#e3efdf' if member == pid else 'white'
                card = (f'<a href="?page=pokemon&id={member}&filters={quote(browse_context(), safe="")}" target="_self" '
                        f'style="display:flex;align-items:center;gap:6px;min-width:135px;padding:8px;'
                        f'border:1px solid #bdd0ba;border-radius:10px;background:{highlight};color:#176b89">'
                        f'<img src="{sprite(member)}" width="56" height="56" alt="" />'
                        f'<span>#{member:03d}<br><strong>{escape(pokemon_names[member])}</strong></span></a>')
                branches = ''.join(
                    '<div style="border-left:2px solid #bdd0ba;padding:10px 0 10px 20px">'
                    f'<div style="font-size:12px;color:#536c59;margin-bottom:7px">→ {escape(edge.criterion)}</div>'
                    + family_node(int(edge.to_pokemon_id), path | {member}) + '</div>'
                    for edge in children.itertuples())
                return '<div style="display:flex;align-items:center;gap:20px">' + card + ('<div>' + branches + '</div>' if branches else '') + '</div>'
            roots = sorted(set(connected.from_pokemon_id) - set(connected.to_pokemon_id))
            st.markdown('<div style="overflow-x:auto;padding:10px 0">' + ''.join(family_node(int(root)) for root in roots) + '</div>', unsafe_allow_html=True)
            st.caption('Highlighted Pokémon is the current entry. Follow a name to browse its family. Evolution requirements use Emerald rules.')

elif page == 'moves':
    title('Moves', subtitle='Explore the 354 moves available in Emerald’s ruleset.')
    a, b, c = st.columns([2, 1, 1])
    query = remembered('text_input', 'Search moves', area=a, placeholder='Move name or description')
    chosen_type = remembered('selectbox', 'Move type', area=b, options=['All types'] + regular_types, format_func=pretty)
    category = remembered('selectbox', 'Category', area=c, options=['Any', 'physical', 'special', 'status'], format_func=pretty)
    moves = data['moves'].copy()
    if query:
        moves = moves[moves.name.str.contains(query.replace(' ', '-'), case=False, regex=False) | moves.description.str.contains(query, case=False, regex=False)]
    if chosen_type != 'All types':
        moves = moves[moves.type_id.map(type_names) == chosen_type]
    if category != 'Any':
        moves = moves[moves.category == category]
    view = moves[['move_id', 'name', 'type_id', 'category', 'power', 'accuracy', 'pp', 'machine', 'description']].copy()
    view['name'] = view.name.map(pretty)
    view['type_id'] = view.type_id.map(type_names).map(pretty)
    view['category'] = view.category.map(pretty)
    st.markdown(f'**{len(view)} moves**')
    icon_legend()
    selectable(view.rename(columns={'name':'Move','type_id':'Type','category':'Category','power':'Power','accuracy':'Acc.', 'pp':'PP', 'machine':'TM / HM','description':'Description'}), 'move', 'move_id', 'moves',
               column_config={'Acc.': st.column_config.NumberColumn('Acc.', format='%d%%', width=60)})

elif page == 'move':
    mid, row = valid_id(data['moves'], 'move_id')
    if st.button('← Back to moves'):
        go('moves')
    title(pretty(row['name']), eyebrow='MOVE · EMERALD')
    badges([type_names[row.type_id]])
    st.markdown(row.description)
    a, b, c, d = st.columns(4)
    a.metric('Category', pretty(row.category))
    b.metric('Base power', 'Variable' if row.variable_power else ('—' if pd.isna(row.power) else int(row.power)))
    c.metric('Deals damage', 'Yes' if row.damaging else 'No')
    d.metric('Base accuracy', '—' if pd.isna(row.accuracy) else f'{int(row.accuracy)}%')
    st.markdown(f'**Base PP:** {int(row.pp)} · **With maximum PP Ups:** {int(row.pp) * 8 // 5} · **Emerald machine:** {row.machine if pd.notna(row.machine) else "—"}')
    st.caption('Physical / special follows Gen 3’s type-based split. A dash means base power does not apply.')
    st.caption('Accuracy is the Emerald base value; “—” means no normal accuracy check. Battle conditions and special effects can change whether a move succeeds.')
    st.subheader('Pokémon that learn this move')
    include = st.toggle('Include earlier evolutions', value=True)
    routes = learning_routes(data, include).query('move_id == @mid')
    methods = st.multiselect('Learning method', ['level_up', 'machine', 'tutor', 'breeding'], format_func=pretty)
    if methods:
        routes = routes[routes.learning_method.isin(methods)]
    st.caption(f'{routes.pokemon_id.nunique()} Pokémon · {len(routes)} learning routes')
    view = routes[['pokemon_id','learning_method','source_pokemon_id','source_name','source_level_learned_at','is_inherited']].copy()
    view.insert(1,'Pokémon',view.pokemon_id.map(pokemon_names))
    view['source_name'] = view.source_name.map(pretty)
    view['learning_method'] = view.learning_method.map(pretty)
    grouped_routes(view.rename(columns={'learning_method':'Method','source_name':'Learned by','source_level_learned_at':'Source level','is_inherited':'Inherited'}), 'pokemon', 'pokemon_id', 'learners',
               extra_links={'Learned by': ('pokemon', 'source_pokemon_id')})

elif page in ('abilities', 'ability'):
    abilities = data['abilities']
    if page == 'abilities':
        title('Abilities', subtitle='The abilities used by Pokémon in Emerald.')
        query = remembered('text_input', 'Search abilities', placeholder='Name or description')
        results = abilities[abilities.name.str.contains(query.replace(' ', '-'), case=False, regex=False) | abilities.description.str.contains(query, case=False, regex=False)]
        view = results.copy()
        view['name'] = view.name.map(pretty)
        selectable(view.rename(columns={'name':'Ability','description':'Description'}), 'ability', 'ability_id', 'abilities')
    else:
        aid, row = valid_id(abilities, 'ability_id')
        if st.button('← Back to abilities'):
            go('abilities')
        title(pretty(row['name']), eyebrow='ABILITY · EMERALD')
        st.markdown(row.description)
        st.subheader('Pokémon with this ability')
        matches = data['pokemon_abilities'].query('ability_id == @aid').pokemon_id
        pokemon_table(pokedex[pokedex.pokemon_id.isin(matches)], key='ability_pokemon')

elif page == 'search':
    title('Find your next teammate', eyebrow='ADVANCED SEARCH', subtitle='Combine base stats, move properties and learning routes.')
    pokemon_filters, move_filters, learning_filters = st.tabs(['Pokémon & stats', 'Qualifying move', 'Learning requirements'])
    with pokemon_filters:
        a, b, c = st.columns(3)
        chosen_type = remembered('selectbox', 'Pokémon type', area=a, options=['All types'] + regular_types, format_func=pretty)
        ability_options = data['abilities'].set_index('ability_id').name.map(pretty).to_dict()
        ability = remembered('selectbox', 'Ability', area=b, options=[None, *ability_options], format_func=lambda aid: 'Any ability' if aid is None else ability_options[aid])
        attack = remembered('number_input', 'Minimum base Attack', area=c, min_value=0, max_value=255, value=90)
        with st.expander('Other base stat minimums'):
            stat_columns = st.columns(3)
            minimums = {stat: remembered('number_input', f'Minimum base {label}', area=stat_columns[index % 3], min_value=0, max_value=255, value=0, key=f'search_{stat}')
                        for index, (stat, label) in enumerate((item for item in STATS.items() if item[0] != 'base_attack'))}
    with move_filters:
        a, b, c = st.columns(3)
        category = remembered('selectbox', 'Move category', area=a, options=['Any', 'physical', 'special', 'status'], index=1, format_func=pretty)
        power = remembered('number_input', 'Minimum fixed base power', area=b, min_value=0, max_value=250, value=80, step=10)
        accuracy = remembered('slider', 'Minimum move accuracy (%)', area=c, min_value=0, max_value=100, value=0, step=5)
        a, b = st.columns(2)
        stab = remembered('toggle', 'Require STAB', area=a, value=True, help='Require an attacking move that shares a type with the Pokémon.')
        no_check = remembered('checkbox', 'Include moves with no normal accuracy check', area=b, value=True)
        st.caption('Set power to 0 to include moves without fixed base power. These filters apply to qualifying moves, not separately required moves.')
    with learning_filters:
        a, b = st.columns(2)
        required = remembered('multiselect', 'Must also learn all these moves (up to 4)', area=a, options=list(move_names), format_func=move_names.get, max_selections=4)
        methods = remembered('multiselect', 'Allowed learning methods', area=b, options=['level_up', 'machine', 'tutor', 'breeding'], format_func=pretty)
        inherited = remembered('toggle', 'Include earlier evolutions', value=True)
        st.caption('Move requirements describe individual learning options, not a validated four-move combination.')
    active_filters = [f'Attack ≥ {attack}', f'{pretty(category)} moves' if category != 'Any' else 'Any move category', f'Power ≥ {power}']
    if chosen_type != 'All types':
        active_filters.append(pretty(chosen_type))
    if ability is not None:
        active_filters.append(ability_options[ability])
    active_filters.extend(f'{STATS[stat]} ≥ {value}' for stat, value in minimums.items() if value)
    if stab:
        active_filters.append('STAB')
    if accuracy:
        active_filters.append(f'Accuracy ≥ {accuracy}%')
    if not no_check:
        active_filters.append('Normal accuracy check only')
    if required:
        active_filters.append('Must learn: ' + ', '.join(move_names[mid] for mid in required))
    if methods:
        active_filters.append(' / '.join(pretty(method) for method in methods))
    active_filters.append('Earlier evolutions included' if inherited else 'Direct learning only')
    st.caption('Active filters: ' + ' · '.join(active_filters))
    result = search_routes(data, attack, category, power, stab, inherited, required, methods,
                           min_stats=minimums, ability_id=ability, min_accuracy=accuracy, include_no_check=no_check)
    if chosen_type != 'All types':
        eligible = pokedex[pokedex.types.map(lambda ts: chosen_type in ts)].pokemon_id
        result = result[result.pokemon_id.isin(eligible)]
    st.markdown(f'**{result.pokemon_id.nunique()} matching Pokémon** · {len(result)} qualifying learning routes')
    pokemon_table(pokedex[pokedex.pokemon_id.isin(result.pokemon_id)], key='search_pokemon')
    with st.expander('View matching moves and learning routes'):
        icon_legend()
        view = result[['pokemon_id','move_id','source_pokemon_id','name','type_id','category','power','accuracy','pp','machine','learning_method','source_name','source_level_learned_at','is_inherited']].copy()
        view.insert(0, 'Pokémon', view.pokemon_id.map(pokemon_names))
        view.loc[view.learning_method != 'machine', 'machine'] = None
        for col in ('name','learning_method','source_name'):
            view[col] = view[col].map(pretty)
        view['type_id'] = view.type_id.map(type_names).map(pretty)
        view['category'] = view.category.map(pretty)
        view = view.rename(columns={'name':'Move','type_id':'Type','category':'Category','power':'Power','accuracy':'Acc.', 'pp':'PP', 'machine':'TM / HM','learning_method':'Method','source_name':'Learned by','source_level_learned_at':'Source level','is_inherited':'Inherited'})
        selectable(view, 'move', 'move_id', 'search_routes',
                   column_config={'Acc.': st.column_config.NumberColumn('Acc.', format='%d%%', width=60)},
                   extra_links={'Pokémon': ('pokemon', 'pokemon_id'), 'Learned by': ('pokemon', 'source_pokemon_id')})
        download = view.drop(columns=['pokemon_id','move_id','source_pokemon_id'])
        st.download_button('Download matching routes', download.to_csv(index=False), 'emerald-search.csv', 'text/csv')

elif page == 'compare':
    title('Compare Pokémon', subtitle='Pictures, base stats and types side by side.')
    selected = st.multiselect('Choose up to four Pokémon', list(pokemon_names), default=st.session_state.get('compare_ids', [285,286]), format_func=pokemon_names.get, max_selections=4)
    if not selected:
        st.info('Choose Pokémon above to start a comparison.')
    else:
        columns = st.columns(len(selected))
        for column, pid in zip(columns, selected):
            row = pokedex[pokedex.pokemon_id == pid].iloc[0]
            with column:
                st.markdown(f'<div style="text-align:center"><img src="{sprite(pid)}" alt="{escape(row.display_name)}" style="height:85px;max-width:100%;object-fit:contain;image-rendering:pixelated" /></div>', unsafe_allow_html=True)
                st.markdown(f'**[{row.display_name}](?page=pokemon&id={pid}&filters={quote(browse_context(), safe="")})**')
                badges(row.types)
                assigned = data['pokemon_abilities'].query('pokemon_id == @pid').merge(data['abilities'], on='ability_id').sort_values('slot')
                for ability in assigned.itertuples():
                    st.markdown(f'[{pretty(ability.name)}](?page=ability&id={ability.ability_id}&filters={quote(browse_context(), safe="")})', help=ability.description)

        stats_tab, defenses_tab = st.tabs(['Base stats', 'Type defenses'])
        with stats_tab:
            comparison = pd.DataFrame({pokemon_names[pid]: [int(pokedex.set_index('pokemon_id').loc[pid, col]) for col in STATS] + [int(pokedex.set_index('pokemon_id').loc[pid, 'bst'])] for pid in selected}, index=[*STATS.values(), 'BST'])
            st.dataframe(comparison, width='stretch', height=284)
        with defenses_tab:
            st.caption('Incoming damage by attacking type. Abilities are not applied, including Levitate and Wonder Guard.')
            defense_rows = data['pokemon_defensive_matchups'].query('attacking_type_id <= 17')
            defense_comparison = pd.DataFrame({pokemon_names[pid]: defense_rows.query('pokemon_id == @pid').set_index('attacking_type_id').modifier for pid in selected})
            defense_comparison.index = defense_comparison.index.map(lambda tid: pretty(type_names[tid]))
            defense_comparison.index.name = 'Attacking type'
            def defense_color(value):
                color = '#ffe2d9' if value >= 4 else '#fff0e9' if value > 1 else '#eee9fa' if value == 0 else '#d8efde' if value < 0.5 else '#edf7ef' if value < 1 else '#fafbf8'
                return f'background-color: {color}; color: #233c32'
            st.dataframe(defense_comparison.style.map(defense_color).format(lambda value: {0.5:'½×', 0.25:'¼×'}.get(float(value), f'{value:g}×')),
                         width='stretch', height=440)
            st.caption('Red = weakness · Green = resistance · Purple = immunity · Neutral = 1×')



else:
    st.info('Page not found. Choose a section in the sidebar.')

st.markdown('<div class="footer">VANILLA POKÉMON EMERALD · Generation III rules · Artwork & sprites via PokéAPI. Pokémon © Nintendo / Game Freak / Creatures.<br>All Gen 1–3 species are included; availability in a particular playthrough is not implied.</div>', unsafe_allow_html=True)
