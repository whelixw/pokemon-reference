"""Small original SVG symbols, embedded locally so tables need no icon CDN."""
import base64
from html import escape
from data_access import COLORS

TYPE_PATHS = {
    'fairy': '<path d="M16 4l4 8 8 4-8 4-4 8-4-8-8-4 8-4z"/>',
    'stellar': '<path d="M16 3l3 9 10 4-10 3-3 10-3-10-10-3 10-4z"/>',
    'normal': '<circle cx="16" cy="16" r="7"/><circle cx="16" cy="16" r="2" fill="white"/>',
    'fire': '<path d="M17 5c2 6-3 7-1 11 2-1 3-3 3-5 7 9 4 16-3 16S5 19 10 13c0 4 2 4 2 4-1-5 4-7 5-12z" fill="white" stroke="none"/>',
    'water': '<path d="M16 5C13 11 8 15 8 20a8 8 0 0016 0c0-5-5-9-8-15z"/><path d="M12 21c0 3 2 3 3 3"/>',
    'electric': '<path d="M18 4L8 18h7l-1 10 11-15h-8z" fill="white" stroke="none"/>',
    'grass': '<path d="M25 6C8 5 5 15 10 22S26 25 25 6z"/><path d="M7 27L22 11m-7 8v-6m1 5h6"/>',
    'ice': '<path d="M16 5v22M6 10l20 12M6 22l20-12M12 7l4 4 4-4M12 25l4-4 4 4"/>',
    'fighting': '<path d="M10 26l-4-9 2-2 4 4V8a2 2 0 014 0v7-9a2 2 0 014 0v9-7a2 2 0 014 0v9-5a2 2 0 014 0v11l-5 6z"/>',
    'poison': '<circle cx="16" cy="13" r="8"/><circle cx="13" cy="12" r="1.5" fill="white"/><circle cx="19" cy="12" r="1.5" fill="white"/><path d="M12 20v5h8v-5m-4 1v4"/>',
    'ground': '<path d="M5 25h22L21 9l-5 8-4-4z"/><path d="M8 28h16"/>',
    'flying': '<path d="M27 6C11 5 5 15 6 26c7 0 16-5 21-20zM7 25L23 10m-10 9l-1-6m5 2h6"/>',
    'psychic': '<path d="M26 17c0-14-21-15-21-2 0 13 20 16 20 4 0-11-15-12-15-3 0 7 10 9 10 2 0-4-5-5-5-1"/>',
    'bug': '<ellipse cx="16" cy="19" rx="7" ry="9"/><path d="M16 11v16M11 11L8 6m13 5l3-5M9 17H5m18 0h4M9 23l-4 3m18-3l4 3"/>',
    'rock': '<path d="M5 23L9 9l10-4 8 14-7 8zM9 9l7 8 11 2M16 17l4 10"/>',
    'ghost': '<path d="M7 25V14a9 9 0 0118 0v12l-5-3-4 4-4-4z"/><circle cx="13" cy="15" r="1.5" fill="white"/><circle cx="20" cy="15" r="1.5" fill="white"/>',
    'dragon': '<path d="M7 26V15L17 6v6l7-2 3 9-7 4-6-3-2 6z"/><path d="M19 16h1M10 13L6 9"/>',
    'dark': '<path d="M21 5a12 12 0 100 22A13 13 0 0121 5z" fill="white" stroke="none"/>',
    'steel': '<path d="M10 5h12l6 11-6 11H10L4 16z"/><circle cx="16" cy="16" r="5"/>',
    'unknown': '<path d="M11 11c0-7 12-7 12 0 0 4-7 4-7 9"/><circle cx="16" cy="25" r="1"/>',
}
CATEGORY_PATHS = {
    'physical': '<path d="M16 4l3 7 8-3-4 8 5 5-9-1-3 9-3-8-9 3 5-8-5-5 9 1z" fill="white" stroke="none"/>',
    'special': '<circle cx="16" cy="16" r="11"/><circle cx="16" cy="16" r="7"/><circle cx="16" cy="16" r="3"/>',
    'status': '<path d="M16 5a11 11 0 000 22c7 0 7-11 0-11S9 5 16 5z" fill="white" stroke="none"/><circle cx="16" cy="10" r="1.5"/><circle cx="16" cy="22" r="1.5"/>',
}


def svg(kind, name):
    if kind == 'type':
        color, paths = COLORS[name], TYPE_PATHS[name]
    else:
        color = {'physical': '#be6546', 'special': '#5076a2', 'status': '#79838c'}[name]
        paths = CATEGORY_PATHS[name]
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><title>{escape(name.title())}</title><rect width="32" height="32" rx="7" fill="{color}"/><g fill="none" stroke="white" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round">{paths}</g></svg>'


def icon_uri(kind, name):
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg(kind, name).encode()).decode()
