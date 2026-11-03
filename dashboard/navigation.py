"""Shared ability explanations and current-tab link navigation."""
from pathlib import Path
import streamlit as st


def install_navigation():
    # Tell the hosting wrapper which route loaded after a same-frame link.
    # This keeps the address bar/share URL in sync with the displayed page.
    st.query_params.from_dict(st.query_params.to_dict())
    # Static, first-party script only; no dataset values are executed as code.
    st.html(Path(__file__).with_name('navigation.html'), unsafe_allow_javascript=True)


def ability_box(name, description, on_pokemon, key):
    with st.popover(name, key=key):
        st.markdown(f'**{name}**')
        st.write(description)
        if st.button('Pokémon with this ability →', key=key+'_pokemon', type='primary'):
            on_pokemon()
