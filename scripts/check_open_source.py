"""Run with python scripts/check_open_source.py (no network or dependencies)."""

from unittest.mock import patch
from xml.etree import ElementTree as ET

import update_open_source as card


def pr(number, state="closed", merged=True, draft=False, owner="example"):
    return {"html_url": f"https://github.com/{owner}/repo/pull/{number}",
            "created_at": "2026-10-24T00:00:00Z", "state": state, "draft": draft,
            "pull_request": {"merged_at": "2026-10-24T01:00:00Z" if merged else None}}


prs = [pr(i) for i in range(13)] + [pr(14, "open", False), pr(15, merged=False),
                                     pr(16, "open", False, True)]
assert [card.status(p) for p in prs[-3:]] == ["open", "closed", "draft"]
groups = card.group_prs(prs + [pr(99, owner=card.USER)])
assert len(groups["example/repo"]) == 16 and len(groups) == 1
groups["example/<repo>&"] = [pr(20)]
for dark in (False, True):
    xml = ET.fromstring(card.render(groups, {name: 1234 for name in groups}, dark))
    labels = " ".join(xml.itertext())
    assert "17 public PRs" in labels and "+4" in labels
    assert "example/<repo>&" in labels and "OCT 2026" in labels
    assert len(xml.findall(".//{*}g/{*}circle")) == 13
assert "No public external PRs" in card.render({}, {})

# Check multi-page totals and refuse incomplete searches rather than undercounting.
with patch.object(card, "github", side_effect=[
    {"incomplete_results": False, "total_count": 2, "items": [pr(1)]},
    {"incomplete_results": False, "total_count": 2, "items": [pr(2)]},
]) as api:
    assert len(card.fetch_prs()) == 2 and api.call_args.kwargs["page"] == 2
with patch.object(card, "github", return_value={"incomplete_results": True, "total_count": 2}):
    try:
        card.fetch_prs()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Incomplete search must not replace valid cards")
print("Open Source card checks passed")
