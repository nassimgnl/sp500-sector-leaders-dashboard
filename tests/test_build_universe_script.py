import pytest

from scripts.build_universe import README_END, README_START, replace_universe_section


def test_replace_universe_section_swaps_only_the_marked_block():
    readme = f"intro\n{README_START}\nold table\n{README_END}\noutro\n"

    updated = replace_universe_section(readme, "new table")

    assert updated == f"intro\n{README_START}\nnew table\n{README_END}\noutro\n"


def test_replace_universe_section_requires_markers():
    with pytest.raises(ValueError, match="markers"):
        replace_universe_section("no markers here", "new table")
