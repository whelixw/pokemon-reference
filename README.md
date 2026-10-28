# Pokémon reference

Public reference browser for vanilla Pokémon Emerald and the pinned Champions preview dataset.

Run `pip install -r dashboard/requirements.txt`, then `streamlit run dashboard/public_app.py`.
On Streamlit Community Cloud use `dashboard/public_app.py` as the entrypoint.

Both editions use saved snapshots. No Snowflake credentials are required or included.
Champions source availability is not official event legality or full team/set validation.

Pokémon names and imagery belong to Nintendo, Game Freak and Creatures. External artwork uses the PokéAPI sprites repository. Champions data is derived from Pokémon Showdown; its license is included in `dashboard/data/champions/SHOWDOWN-LICENSE.txt`. Item icon attribution is in `dashboard/assets/README.md`. Dataset provenance and pinned revisions are recorded in the packaged manifests.
Pokémon Emerald and Champions reference browser — public Streamlit release
