"""Pokédex presentation for the pinned Champions Regulation M-C snapshot."""
from html import escape
import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from PIL import Image
from urllib.parse import quote, urlsplit
import pandas as pd
import streamlit as st
from icons import icon_uri, svg
from defense_ui import defense_cards, multiplier_label

STATS = {'hp':'HP', 'atk':'Attack', 'def':'Defense', 'spa':'Sp. Atk', 'spd':'Sp. Def', 'spe':'Speed'}


def link(view, identifier='', name=''):
    current = urlsplit(st.context.url or 'http://localhost:8502/')
    base = f'{current.scheme}://{current.netloc}{current.path}?page=champions&view={view}&id={quote(identifier)}'
    return base + ('#' + quote(name) if name else '')


def go(view, identifier=''):
    st.query_params.from_dict({'page':'champions', 'view':view, 'id':identifier})
    st.rerun()


def sprite(p):
    return f"https://play.pokemonshowdown.com/sprites/gen5/{p['spriteid']}.png"


@lru_cache(maxsize=256)
def item_icon(spritenum):
    """Extract the same 24px tile used by Showdown's item icon renderer."""
    with Image.open(Path(__file__).parent / 'assets' / 'itemicons-sheet.png') as sheet:
        x, y = (spritenum % 16) * 24, (spritenum // 16) * 24
        if spritenum < 0 or x + 24 > sheet.width or y + 24 > sheet.height:
            return None
        tile = sheet.crop((x, y, x + 24, y + 24))
        buffer = BytesIO()
        tile.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def badges(types):
    st.markdown(' '.join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">{svg("type", t.lower())}{escape(t)}</span>' for t in types), unsafe_allow_html=True)


def symbols(frame, category=False):
    config = {}
    if not st.session_state.get('mc_labels', False):
        for column in ('Type', 'Type 1', 'Type 2', 'Category'):
            if column not in frame:
                continue
            kind = 'category' if column == 'Category' else 'type'
            frame[column] = frame[column].map(lambda v: icon_uri(kind, v.lower()) if v else None)
            config[column] = st.column_config.ImageColumn(column, width=55, help='Enable full labels in the sidebar for names.')
    return config


def pokemon_table(species, key):
    if not species:
        st.info('No matches. Try broadening your filters.')
        return
    rows=[]
    for p in species:
        rows.append({'No.':p['num'], 'Sprite':sprite(p), 'Pokémon':link('pokemon',p['id'],p['name']),
                     'Type 1':p['types'][0], 'Type 2':p['types'][1] if len(p['types'])>1 else None,
                     **{label:p['baseStats'][stat] for stat,label in STATS.items()}, 'BST':sum(p['baseStats'].values())})
    frame=pd.DataFrame(rows)
    config=symbols(frame)
    config.update({'Sprite':st.column_config.ImageColumn('',width=50),
                   'Pokémon':st.column_config.LinkColumn(display_text=r'#(.*)$'),
                   'No.':st.column_config.NumberColumn(format='%03d',width=55)})
    # URL fragments carry readable labels, like the Emerald tables.
    frame['Pokémon']=[link('pokemon',p['id'],p['name']).split('#')[0]+'#'+p['name'] for p in species]
    st.dataframe(frame,hide_index=True,width='stretch',height=min(480,35*(len(rows)+1)+4),
                 column_config=config,placeholder='—',key=key)


def move_table(moves,key):
    if not moves:
        st.info('No matching moves.')
        return
    frame=pd.DataFrame([{'Move':link('moves',m['id'])+'#'+m['name'], 'Type':m['type'], 'Category':m['category'],
                         'Power':m['basePower'] or None,'Acc.':None if m['accuracy'] is True else m['accuracy'],
                         'PP':m['pp'],'Priority':m['priority'],'Target':m['target']} for m in moves])
    config=symbols(frame)
    config.update({'Move':st.column_config.LinkColumn(display_text=r'#(.*)$'), 'Acc.':st.column_config.NumberColumn(format='%d%%')})
    st.dataframe(frame,hide_index=True,width='stretch',height=min(450,35*(len(moves)+1)+4),column_config=config,placeholder='—',key=key)


def defenses(p,types):
    charts={t['name']:t['damageTaken'] for t in types}
    result={}
    for attack in charts:
        multiplier=1
        for defense in p['types']:
            multiplier *= {0:1,1:2,2:.5,3:0}[charts[defense].get(attack,0)]
        result[attack]=multiplier
    return result


def defense_table(species,types):
    frame=pd.DataFrame({p['name']:defenses(p,types) for p in species})
    def color(value):
        return 'background-color: '+('#ffe2d9' if value>1 else '#e9e2f5' if value==0 else '#e1f0e3' if value<1 else '#fafbf8')
    frame.index.name = 'Attacking type'
    st.dataframe(frame.style.map(color).format(multiplier_label),width='stretch',height=380)
    st.caption('Typing only: ability, item and field effects are not applied. Red: weakness · green: resistance · purple: immunity.')


def render_page(view,tables):
    keys = ['mc_query','mc_type','mc_form','mc_ability','mc_required','mc_compare', *['mc_min_'+stat for stat in STATS]]
    saved = st.session_state.setdefault('mc_saved_filters', {})
    for key in keys:
        if key not in st.session_state and key in saved:
            st.session_state[key] = saved[key]
    try:
        _render_page(view,tables)
    finally:
        for key in keys:
            if key in st.session_state:
                saved[key] = st.session_state[key]


def _render_page(view,tables):
    pool=sorted([p for p in tables['species'] if p['mc_species_allowed']],key=lambda p:(p['num'],p['name']))
    by_id={p['id']:p for p in pool}
    identifier=st.query_params.get('id','')
    moves={m['id']:m for m in tables['moves'] if m['available']}
    abilities={a['name']:a for a in tables['abilities']}
    if view=='dex':
        st.title('Champions Pokédex')
        st.caption('Regulation M-C · Browse Pokémon and battle forms')
        a,b,c=st.columns([2,1,1])
        query=a.text_input('Search Pokémon',placeholder='Name or National number',key='mc_query')
        kind=b.selectbox('Type',['All types',*sorted({t for p in pool for t in p['types']})],key='mc_type')
        form=c.selectbox('Forms',['All forms','Non-battle forms','Battle forms'],key='mc_form')
        with st.expander('Stats, abilities and required moves'):
            a,b=st.columns(2)
            ability=a.selectbox('Ability',['Any',*sorted({a for p in pool for a in p['abilities'].values()})],key='mc_ability')
            required=b.multiselect('Must learn all selected moves',list(moves),format_func=lambda mid:moves[mid]['name'],max_selections=4,key='mc_required')
            cols=st.columns(3)
            minimums={stat:cols[i%3].number_input(f'Minimum {label}',0,255,key=f'mc_min_{stat}') for i,(stat,label) in enumerate(STATS.items())}
        result=[p for p in pool if (not query or query.casefold() in p['name'].casefold() or query.lstrip('0')==str(p['num']))
                and (kind=='All types' or kind in p['types'])
                and (form=='All forms' or (bool(p['battleOnly']) == (form=='Battle forms')))
                and (ability=='Any' or ability in p['abilities'].values())
                and all(p['baseStats'][stat]>=minimum for stat,minimum in minimums.items())]
        for mid in required:
            eligible={r['pokemon_id'] for r in tables['learnsets'] if r['move_id']==mid}
            result=[p for p in result if p['id'] in eligible]
        st.markdown(f'**{len(result)} Pokémon / forms**')
        pokemon_table(result,'mc_dex')
    elif view=='pokemon':
        if identifier not in by_id:
            st.info('This Pokémon is not in the M-C species pool.'); return
        p=by_id[identifier]
        a,b,c=st.columns([4,1,1])
        if a.button('← Back to Champions Pokédex'): go('dex')
        position = next(i for i, entry in enumerate(pool) if entry['id'] == identifier)
        if position > 0 and b.button('← Previous', help=pool[position-1]['name'], width='stretch'):
            go('pokemon', pool[position-1]['id'])
        if position < len(pool)-1 and c.button('Next →', help=pool[position+1]['name'], width='stretch'):
            go('pokemon', pool[position+1]['id'])
        picture,info,stats=st.columns([1.05,1.25,1.6],gap='large')
        with picture:
            st.image(sprite(p),width=160)
        with info:
            st.caption(f"NATIONAL #{p['num']:03d} · REGULATION M-C")
            st.title(p['name']); badges(p['types'])
            st.markdown('**Abilities in Champions**')
            for name in dict.fromkeys(p['abilities'].values()):
                a=abilities[name]
                if st.button(name,key='mc_pokemon_ability_'+a['id']): go('ability',a['id'])
            with st.expander('Ability effects'):
                for name in dict.fromkeys(p['abilities'].values()):
                    st.markdown(f'**{name}**')
                    st.caption(abilities[name]['desc'])
            if st.button('Compare this Pokémon'):
                st.session_state['mc_compare']=[identifier]; go('compare')
            if p['battleOnly']:
                st.caption('Battle transformation: '+str(p['battleOnly']))
            if p['requiredItems']:
                st.caption('Required item: '+', '.join(p['requiredItems']))
        with stats:
            st.subheader('Base stats')
            markup=''.join(f'<div class="stat"><span>{label}</span><strong>{p["baseStats"][stat]}</strong><div class="track"><div class="fill" style="width:{p["baseStats"][stat]/255*100}%"></div></div></div>' for stat,label in STATS.items())
            st.markdown(markup,unsafe_allow_html=True)
            st.markdown(f'**Base stat total · {sum(p["baseStats"].values())}**')
        defense,learn,family=st.tabs(['Type defenses','Moves learned','Other forms'])
        with learn:
            query=st.text_input('Find a move',key='mc_learn_query')
            ids={r['move_id'] for r in tables['learnsets'] if r['pokemon_id']==identifier}
            entries=sorted([moves[mid] for mid in ids if mid in moves and query.casefold() in moves[mid]['name'].casefold()],key=lambda m:m['name'])
            st.caption(f'{len(entries)} moves · Individual source options, not complete moveset validation.')
            move_table(entries,'mc_learnset')
        with defense: defense_cards(defenses(p,tables['types']))
        with family:
            pokemon_table([other for other in pool if other['baseSpecies']==p['baseSpecies']],'mc_forms')
    elif view=='compare':
        st.title('Compare Pokémon')
        selected=st.multiselect('Choose up to four Pokémon',list(by_id),format_func=lambda pid:by_id[pid]['name'],max_selections=4,key='mc_compare')
        if not selected: st.info('Choose Pokémon above to start a comparison.'); return
        chosen=[by_id[pid] for pid in selected]
        for col,p in zip(st.columns(len(chosen)),chosen):
            with col:
                st.image(sprite(p),width=96)
                st.markdown(f"**[{p['name']}]({link('pokemon',p['id'])})**")
                badges(p['types'])
                st.caption(' / '.join(dict.fromkeys(p['abilities'].values())))
        base,defense=st.tabs(['Base stats','Type defenses'])
        with base:
            st.dataframe(pd.DataFrame({p['name']:[*(p['baseStats'][stat] for stat in STATS),sum(p['baseStats'].values())] for p in chosen},index=[*STATS.values(),'BST']),width='stretch')
        with defense: defense_table(chosen,tables['types'])
    elif view in ('abilities','items','ability','item'):
        is_ability=view.startswith('abil')
        plural='abilities' if is_ability else 'items'
        singular='ability' if is_ability else 'item'
        entries=tables[plural]
        if view==singular:
            entry=next((e for e in entries if e['id']==identifier),None)
            if not entry: st.info('Entry not found.'); return
            if st.button('← Back to '+plural): go(plural)
            if not is_ability:
                image_col, title_col = st.columns([1, 8], vertical_alignment='center')
                image_col.image(item_icon(entry['spritenum']), width=48)
                title_col.title(entry['name'])
            else:
                st.title(entry['name'])
            st.write(entry['desc'])
            if is_ability:
                st.subheader('Pokémon with this ability')
                pokemon_table([p for p in pool if entry['name'] in p['abilities'].values()],'mc_ability_pokemon')
        else:
            st.title(plural.title())
            query=st.text_input('Search '+plural,key='mc_'+plural+'_query')
            filtered=sorted([e for e in entries if query.casefold() in (e['name']+' '+e['desc']).casefold()],key=lambda e:e['name'])
            if not filtered: st.info('No matches.'); return
            name_col=singular.title()
            frame=pd.DataFrame([{**({'Icon':item_icon(e['spritenum'])} if not is_ability else {}), name_col:link(singular,e['id'])+'#'+e['name'],'Effect':e['desc']} for e in filtered])
            st.caption(f'{len(filtered)} {plural} · Source descriptions')
            st.dataframe(frame,hide_index=True,width='stretch',height=480,column_config={'Icon':st.column_config.ImageColumn('',width=45), name_col:st.column_config.LinkColumn(display_text=r'#(.*)$',width=170), 'Effect':st.column_config.TextColumn(width='large')})
    else:
        st.info('Page not found. Choose a section in the sidebar.')
