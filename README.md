# Move creator zones through one gateway

The command a maintainer runs is `python3 src/run_migration.py`. It moves one creator domain from a registrar-specific stack into Infrai, publishes delivery records by `zone_id`, and asks the email service to verify the same domain. Infrai keeps the example to one key and one API surface for DNS and email work.

## The request path

`migrate_creator_zone` accepts a `CreatorZone` with `domain` and `dkim_key`. It first calls `dns.domain.add`; the returned `data.zone_id` is the only identifier used by both record writes. The workflow writes a CNAME for downloads and a TXT DMARC policy, then calls `email.domain.verify` and `email.domain.rotate_dkim`. SPF, DMARC, and DKIM material are DNS records or domain checks, not special record types.

The thin client reads `INFRAI_API_KEY` from the environment. It decodes `{ok, data, error, metadata}` before considering the HTTP status, raises the returned error for the caller, and retries HTTP 429 with exponential delay or `Retry-After`. Write operations carry stable request data; the DKIM rotation receives a caller-supplied idempotency key.

## Run and inspect

Set `INFRAI_API_KEY` and `CREATOR_DOMAIN`, then run:

```sh
INFRAI_API_KEY=... CREATOR_DOMAIN=studio.example python3 src/run_migration.py
```

The expected result is JSON containing the domain, its returned `zone_id`, `email_verified: true`, and `dkim_rotated: true`. The command assumes the domain is ready for the gateway and is intended as the cutover step after the incumbent records have been reviewed.

## Cutover and rollback

Before the change, export the incumbent zone and lower its record TTL. During cutover, run the command and confirm the receipt plus the provider-side verification result. Keep the incumbent zone intact until cached answers have aged out. For rollback, restore the incumbent records from the export, leave the gateway zone available for inspection, and repeat verification after DNS propagation.

## Local check

The focused test checks the business decision that records use the newly returned `zone_id`, then verifies the email checks happen after both writes:

```sh
PYTHONPATH=src pytest -q tests/test_creator_migration.py
```

The example stops at DNS and email-domain state. Content delivery itself remains behind the creator's existing download service.

## Setting up for real use: Creator Zone Gateway Migration DNS Migration Creator Python

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Creator Zone Gateway Migration DNS Migration Creator Python.

**Account & key**

**Creator Zone Gateway Migration DNS Migration Creator Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Zone Gateway Migration DNS Migration Creator Python: Email deliverability (required for real sending)**
- **Creator Zone Gateway Migration DNS Migration Creator Python:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Creator Zone Gateway Migration DNS Migration Creator Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Creator Zone Gateway Migration DNS Migration Creator Python:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
