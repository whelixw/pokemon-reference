"""Shared single-Pokémon defense presentation for both editions."""
from html import escape
import streamlit as st
from data_access import COLORS


def multiplier_label(value):
    return {0.5: '½×', 0.25: '¼×'}.get(float(value), f'{float(value):g}×')


def defense_cards(matchups):
    """Render attacking type -> multiplier, keeping neutral types collapsed."""
    st.subheader('Type defenses')
    st.caption('Incoming attack multipliers. Abilities, items and battle conditions are not applied.')

    def group(label, explanation, entries, accent, background):
        st.markdown(f'**{label}** · {explanation}')
        if not entries:
            st.caption('None')
            return
        cards = []
        for name, value in entries:
            color = COLORS[name.lower()]
            cards.append(
                f'<div style="display:flex;align-items:center;gap:12px;padding:7px 10px;'
                f'border:1px solid {accent};border-radius:8px;background:{background}">'
                f'<span class="type-pill" style="background:{color};margin:0;min-width:72px;text-align:center">{escape(name.title())}</span>'
                f'<strong style="color:{accent};font-size:20px;min-width:42px;text-align:right">{multiplier_label(value)}</strong></div>')
        st.markdown('<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 18px">' + ''.join(cards) + '</div>', unsafe_allow_html=True)

    entries = list(matchups.items())
    group('Weaknesses', 'takes more damage', sorted((e for e in entries if e[1] > 1), key=lambda e: -e[1]), '#a23d30', '#fff4ef')
    group('Resistances', 'takes less damage', sorted((e for e in entries if 0 < e[1] < 1), key=lambda e: e[1]), '#27694c', '#edf7ef')
    group('Immunities', 'takes no damage', [e for e in entries if e[1] == 0], '#585a83', '#f2f0fa')
    neutral = [e for e in entries if e[1] == 1]
    with st.expander(f'Neutral damage · {len(neutral)} types · 1×'):
        group('Neutral', 'takes normal damage', neutral, '#58685d', '#f4f6f2')
    st.caption('4× = quadruple damage · 2× = double · ½× = half · ¼× = quarter · 0× = no damage')
