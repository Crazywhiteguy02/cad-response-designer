from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cadence_brand_name_and_palette():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'page_title="CADence v0.8.0"' in app
    assert 'class="brand-title">CADence<' in app
    assert "--brand-navy: #011340;" in app
    assert "--action-blue: #0162E8;" in app
    assert "--accent-cyan: #00D9FC;" in app
    assert "--neutral-gray: #C0C0C2;" in app
    assert "--charcoal: #24262A;" in app
    assert "#F7F9FC" in app
    assert "--surface: #FFFFFF;" in app


def test_cadence_palette_roles_are_applied():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "background: linear-gradient(180deg, #011340" in app
    assert "background: linear-gradient(135deg, var(--action-blue)" in app
    assert "--accent-cyan: #00D9FC;" in app
    assert "color: var(--charcoal);" in app
