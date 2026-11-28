"""The GPU types that RunPod offers, with stock and price, for the create pod form."""

from core import hosting
from core.cache import cache
from modules.godfather import base
from modules.godfather.pod_spec import CLOUD_TYPES

STOCK = ("HIGH", "MEDIUM", "LOW", "NONE")
GPU_TYPES_SECONDS = 60


def gpu_types(db, org_id: int, cloud: str, client: hosting.HostingClient | None = None) -> list[dict]:
    """RunPod GPU types offered on cloud, with stock and price for one GPU. In stock first, then cheapest first.

    Results are cached for GPU_TYPES_SECONDS by org and cloud.
    """
    if cloud not in CLOUD_TYPES:
        raise base.GodfatherError(f"cloud must be one of {', '.join(CLOUD_TYPES)}", 400)
    runpod = client or base.get_client(db, org_id, "runpod")
    read = getattr(runpod, "gpu_types", None)
    if read is None:
        return []

    def fetch() -> list[dict]:
        side = cloud.lower()
        found = []
        for gpu in base.call(read, cloud):
            if not gpu.get(side) or gpu.get("manufacturer") == "UNKNOWN":
                continue
            stock = str(gpu.get("availability") or "NONE").upper()
            found.append(
                {
                    "id": gpu.get("id"),
                    "name": gpu.get("name") or gpu.get("id"),
                    "memory": gpu.get("memory"),
                    "price": (gpu.get("price") or {}).get(side),
                    "availability": stock if stock in STOCK else "NONE",
                }
            )
        return sorted(found, key=lambda g: (STOCK.index(g["availability"]), g["price"] or 0, str(g["name"])))

    return cache.get_or_compute(("godfather.gpu_types", org_id, cloud), GPU_TYPES_SECONDS, fetch)
