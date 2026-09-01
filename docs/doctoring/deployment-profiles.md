# GA deployment profiles

Status: **in progress** — first increment (typed profile model + honesty
validator) landed. Tracks issue
[#950](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/950)
("[Enterprise Gap] Define GA deployment profiles, tenant isolation, SSO, and
lifecycle provisioning").

## Why

Project membership, OIDC token verification, API keys, encrypted DSNs, and
share links are necessary controls, but they do not by themselves prove a
shared hosted service is multi-tenant safe. The product must make a
**truthful** deployment claim and must never imply multi-tenancy merely
because projects have members.

## Decision — two explicit profiles + a validator (this increment)

`app/deploy/profile.py` — pure model + `validate_profile(profile) -> list[str]`
(returns problems; never blesses a profile). No infrastructure, no `Settings`
wiring, no migration.

### Profile A — `single_tenant_managed`

One customer organization per deployment/database; Keyverse or external OIDC
with organization binding; project RBAC within that organization;
Compose/Podman + production ingress; customer-owned backup / restore / secret
/ network policies; **no cross-customer claim**. This is the minimum viable
GA profile *if proven end to end*.

The validator flags a `single_tenant_managed` profile that: uses
`local_dev` identity while claiming `ga_ready`; does not enforce organization
binding while GA; does not document customer-owned backup ownership while GA;
uses an isolation mode other than `single_org_per_database`; or makes a
cross-customer claim.

### Profile B — `multi_tenant_saas`

A shared hosted service. Isolation is `shared_db_tenant_scoped_rows`. The
validator **rejects `ga_ready = True`** until *all* of these are in place:

1. the normalized tenant-authority tables (`tenant_account`, `tenant_domain`,
   `tenant_membership`, `tenant_role_assignment`, `identity_link_record`,
   `provisioning_request`, `provisioning_receipt`, `data_residency_policy`,
   `tenant_audit_event`);
2. every authority-bearing object carries or derives one immutable
   `tenant_account_uuid` — `AUTHORITY_BEARING_OBJECTS` enumerates them:
   project spaces, memberships, connections, snapshots, snapshot data, jobs,
   diagram views, annotations, share links, API keys, migration plans/runs,
   connector artifacts, audit events, caches, object-storage keys, metrics
   labels, and queue signals;
3. tenant provisioning lifecycle (create / suspend / offboard) with receipts;
4. a per-tenant data-residency policy.

`local_dev` identity is never valid for `multi_tenant_saas`.

## Compliance context

CSAP and SOC 2 both require an accurate description of the isolation boundary
and its enforcement. This validator exists so a claimed profile cannot drift
from what is actually enforced. PII masking is **not** relied on for tenant
isolation — a compliant non-masking control (enforced tenant ownership on
every persisted and cached object) is the boundary.

## Deferred (later increments on #950)

- The `tenant_account` authority tables + Alembic migration.
- A repository/query layer that derives `tenant_account_uuid` on every
  authority-bearing read and write, plus a test that asserts no
  authority-bearing table lacks the column.
- SSO / SCIM identity-link + provisioning-request/receipt flows.
- `data_residency_policy` enforcement and per-tenant object-storage prefixes.
- `Settings`-selected active profile + a startup self-check that runs
  `validate_profile` and fails closed on a dishonest claim.

## References (APA 7th)

Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust
architecture* (NIST Special Publication 800-207). National Institute of
Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207

Open Worldwide Application Security Project. (2021). *OWASP application
security verification standard 4.0.3*.
https://owasp.org/www-project-application-security-verification-standard/
