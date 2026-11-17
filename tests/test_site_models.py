"""models.html: every model card is rendered, headed by its registry score, and cross-links stay on the site."""
from src.pipeline import site, site_models


def test_every_card_is_on_the_page_with_its_registry_score(tmp_path):
    (tmp_path / "d_model_registry.csv").write_text(
        "model,task,method,baseline,training_window,metric,model_score,baseline_score,beats_baseline,decision,shown_as,model_card\n"
        "Spending forecast,t,m,Naive,w,Mean MASE,2.09,2.15,True,Adopted,Calculator,docs/models/forecast.md\n")
    out = site_models.body(tmp_path, site.md_to_html)
    for f in site_models.CARDS.glob("*.md"):
        assert f'id="{f.stem}"' in out
    assert "Model <b>2.09</b>" in out and "Beats its baseline" in out


def test_markdown_lists_and_card_links():
    out = site.md_to_html("Intro\n- one\n- two [x](challenger.md)\n\n1. a\n2. b")
    assert "<ul><li>one</li><li>two <a href=\"models.html#challenger\">x</a></li></ul>" in out and "<ol><li>a</li><li>b</li></ol>" in out
