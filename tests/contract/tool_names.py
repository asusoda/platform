"""Every tool a token can call, found the way an agent finds them: the tool list, then the modules gateway."""


def _call(client, headers, name, arguments):
    response = client.post(f"/api/tools/{name}", json=arguments, headers=headers)
    return response.get_json()["result"] if response.status_code == 200 else None


def every_tool(client, headers) -> list[dict]:
    """The listed tools, minus the gateway, plus the tools of each module."""
    listed = client.get("/api/tools", headers=headers).get_json()["tools"]
    names = {t["name"] for t in listed}
    found = [t for t in listed if t["name"] not in ("modules.list", "modules.skill", "modules.tools", "modules.call")]
    if "modules.list" in names:
        for module in _call(client, headers, "modules.list", {})["modules"]:
            found += _call(client, headers, "modules.tools", {"name": module["name"]})["tools"]
    if {t["name"] for t in found} <= {"batch", "guide"}:
        # Only the tools every token sees: nothing else to call
        return []
    return sorted(found, key=lambda t: t["name"])


def every_name(client, headers) -> list[str]:
    return [t["name"] for t in every_tool(client, headers)]
