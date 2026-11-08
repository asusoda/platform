"""The guide tool: the skills in skills/ for agents that use Platform MCP."""

import re

import pytest
import yaml

from modules.mcp import layers

from .test_layers import _call, _listed


@pytest.fixture
def token_for(client, officer_headers, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")

    def issue(*scopes):
        body = {"name": "test-agent", "kind": "agent", "scopes": list(scopes)}
        response = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers)
        assert response.status_code == 201, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    return issue


SKILLS = sorted(path.parent.name for path in layers.GUIDES.glob(f"*/{layers.SKILL_FILE}"))


def test_each_skill_has_frontmatter_and_is_in_the_index():
    index = (layers.GUIDES / "README.md").read_text()
    assert "platform-mcp" in SKILLS
    for name in SKILLS:
        text = (layers.GUIDES / name / layers.SKILL_FILE).read_text()
        front = yaml.safe_load(text.split("---", 2)[1])
        assert front["name"] == name
        assert 20 <= len(front["description"]) <= 300
        assert f"]({name}/SKILL.md)" in index
        assert len(text) < layers.MAX_SKILL


def test_skills_name_tools_that_exist():
    from core.tools import TOOLS
    from modules.mcp import runtime

    known = set(TOOLS) | set(runtime.GATEWAYS) | {runtime.BATCH, runtime.GUIDE}
    for name in SKILLS:
        text = (layers.GUIDES / name / layers.SKILL_FILE).read_text()
        for tool in re.findall(r"`([a-z]+\.[a-z_]+)`", text):
            assert tool in known, f"{name} names {tool}"


def test_every_token_sees_guide(client, token_for):
    assert "guide" in _listed(client, token_for("org:read"))


def test_guide_lists_and_returns_skills(client, token_for):
    headers = token_for("org:read")
    listed = _call(client, headers, "guide").get_json()["result"]
    assert [s["name"] for s in listed["skills"]] == SKILLS
    assert all(s["description"] for s in listed["skills"])
    one = _call(client, headers, "guide", name="platform-mcp").get_json()["result"]
    assert one["name"] == "platform-mcp" and one["skill"].startswith("---\nname: platform-mcp")


@pytest.mark.parametrize("name", ["nothing", "../modules", "README.md"])
def test_guide_refuses_unknown_names(client, token_for, name):
    response = _call(client, token_for("org:read"), "guide", name=name)
    assert response.status_code == 404


def test_the_gateway_does_not_run_guide(client, token_for):
    headers = token_for("org:read", "points:read")
    assert _call(client, headers, "modules.call", tool="guide").status_code == 400
