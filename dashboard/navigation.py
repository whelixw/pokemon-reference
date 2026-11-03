"""Shared ability explanations and current-tab link navigation."""
from pathlib import Path
import streamlit as st


def install_navigation():
    # Static, first-party script only; no dataset values are executed as code.
    st.html(Path(__file__).with_name('navigation.html'), unsafe_allow_javascript=True)


def ability_box(name, description, on_pokemon, key):
    with st.popover(name, key=key):
        st.markdown(f'**{name}**')
        st.write(description)
        if st.button('Pokémon with this ability →', key=key+'_pokemon', type='primary'):
            on_pokemon()
