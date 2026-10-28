from creator_migration import CreatorZone, MigrationReceipt, migrate_creator_zone


class FakeClient:
    def __init__(self):
        self.calls = []

    def domain_add(self, domain):
        self.calls.append(("domain_add", domain))
        return {"ok": True, "data": {"zone_id": "zone-7"}}

    def record_upsert(self, record):
        self.calls.append(("record_upsert", record))
        return {"ok": True, "data": {}}

    def verify_email_domain(self, domain):
        self.calls.append(("verify_email_domain", domain))
        return {"ok": True, "data": {"status": "verified"}}

    def rotate_dkim(self, domain, idempotency_key):
        self.calls.append(("rotate_dkim", domain, idempotency_key))
        return {"ok": True, "data": {}}


def test_migration_uses_zone_id_before_publishing_records():
    client = FakeClient()
    receipt = migrate_creator_zone(CreatorZone("studio.example", "rotation-1"), client)

    assert receipt == MigrationReceipt("studio.example", "zone-7", True, True)
    records = [call[1] for call in client.calls if call[0] == "record_upsert"]
    assert len(records) == 2
    assert {record["record_type"] for record in records} == {"CNAME", "TXT"}
    assert all(record["zone_id"] == "zone-7" for record in records)
    assert client.calls[-2:] == [
        ("verify_email_domain", "studio.example"),
        ("rotate_dkim", "studio.example", "rotation-1"),
    ]
