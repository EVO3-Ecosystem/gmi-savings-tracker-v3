"""The opt-in portfolio palette and embed mode of the dashboard (?palette=portfolio, ?embed=1): contrast and wiring."""
from src.pipeline import preview


def _lum(hexcolor):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


P = preview._PORTFOLIO


def test_portfolio_text_meets_aa_on_both_surfaces():
    for fg in ("color-fg", "color-fg-muted", "color-link", "color-ok", "color-warn", "color-bad", "cds-text-secondary"):
        for bg in ("color-bg", "color-panel"):
            assert _ratio(P[fg], P[bg]) >= 4.5, (fg, bg, _ratio(P[fg], P[bg]))


def test_portfolio_series_marks_are_visible_on_the_panel():
    for i in range(1, 9):
        assert _ratio(P[f"series-{i}"], P["color-panel"]) >= 3.0, (i, _ratio(P[f"series-{i}"], P["color-panel"]))
    assert len(set(preview.SERIES_PORTFOLIO)) == 8  # eight distinct colours, as in the default palettes


def test_portfolio_has_every_token_the_default_look_has():
    assert set(P) == set(preview._LIGHT) == set(preview._DARK)


def test_palette_and_embed_are_opt_in_and_only_known_values():
    look = preview.LOOK
    assert 'data-palette="portfolio"' in look and "data-embed" in look
    assert "q.get('palette')==='portfolio'" in look and "q.get('embed')==='1'" in look  # no other value is applied
    assert look.index(':root[data-palette="portfolio"]') > look.index(':root[data-theme="dark"]')  # later, so it wins
