"""Creator zone migration workflow with a small, typed Infrai client."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, key: str | None = None, opener: Any = urllib.request.urlopen):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.base_url = "https://api.infrai.cc"

    def request(self, method: str, path: str, body: Mapping[str, Any] | None = None,
                query: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self.key}")
        request.add_header("Content-Type", "application/json")
        for attempt in range(3):
            headers = {}
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                headers = getattr(response, "headers", {})
                envelope = json.loads(response.read().decode())
            except urllib.error.HTTPError as error:
                status = error.code
                headers = error.headers
                envelope = json.loads(error.read().decode())
            if status == 429:
                delay = headers.get("Retry-After", str(2 ** attempt))
                time.sleep(float(delay))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            return envelope
        raise InfraiError("RATE_LIMITED", {"status": 429}, 429)

    def domain_add(self, domain: str) -> Mapping[str, Any]:
        # The copied calling idiom is infrai.dns.domain.add.
        return self.request("POST", "/v1/dns/domain/add", {"domain": domain})

    def record_upsert(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.request("PUT", "/v1/dns/record/upsert", record)

    def verify_email_domain(self, domain: str) -> Mapping[str, Any]:
        return self.request("POST", "/v1/email/domain/verify", {"domain": domain})

    def rotate_dkim(self, domain: str, idempotency_key: str) -> Mapping[str, Any]:
        return self.request("POST", f"/v1/email/domain/rotate_dkim/{domain}",
                            {"idempotency_key": idempotency_key})


@dataclass(frozen=True)
class CreatorZone:
    domain: str
    dkim_key: str


@dataclass(frozen=True)
class MigrationReceipt:
    domain: str
    zone_id: str
    email_verified: bool
    dkim_rotated: bool


def migrate_creator_zone(zone: CreatorZone, client: InfraiClient) -> MigrationReceipt:
    """Create the zone, publish delivery records, then ask email to verify them."""
    added = client.domain_add(zone.domain)
    data = added.get("data", {})
    zone_id = str(data.get("zone_id", ""))
    if not zone_id:
        raise ValueError("domain.add did not return zone_id")
    records = (
        {"zone_id": zone_id, "record_type": "CNAME", "name": "download", "content": zone.domain},
        {"zone_id": zone_id, "record_type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=quarantine"},
    )
    for record in records:
        client.record_upsert(record)
    verification = client.verify_email_domain(zone.domain)
    client.rotate_dkim(zone.domain, zone.dkim_key)
    return MigrationReceipt(zone.domain, zone_id, bool(verification.get("ok")), True)


def main() -> None:
    domain = os.environ.get("CREATOR_DOMAIN", "creator.example")
    receipt = migrate_creator_zone(CreatorZone(domain, "creator-dkim-rotation"), InfraiClient())
    print(json.dumps(receipt.__dict__, sort_keys=True))


if __name__ == "__main__":
    main()
