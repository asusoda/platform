"""RunPodClient calls against a fake requests.request."""

import requests

from core.integrations import runpod


class Answer:
    status_code = 200
    content = b"{}"

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_gpu_types_reads_pod_stock_for_one_cloud(monkeypatch):
    seen = {}

    def fake(method, url, **kwargs):
        seen.update(method=method, url=url, auth=kwargs["headers"]["Authorization"])
        return Answer({"gpus": [{"id": "NVIDIA L4", "availability": "HIGH"}]})

    monkeypatch.setattr(requests, "request", fake)
    gpus = runpod.RunPodClient("key").gpu_types("SECURE")
    assert gpus == [{"id": "NVIDIA L4", "availability": "HIGH"}]
    assert seen["method"] == "GET"
    assert seen["url"] == (
        "https://api.runpod.io/v2/catalog/gpus?include=AVAILABILITY&product=POD&count=1&cloud=SECURE"
    )
    assert seen["auth"] == "Bearer key"
