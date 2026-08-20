# Product and technical gap baseline: research and standards traceability

This record supports `docs/product-technical-gap-baseline.md` and issues #946–#953. It records why a requirement exists, which product decision it informs, and the claim boundary. A citation does not prove that implementation, certification, conformance, or release evidence exists.

## Traceability rules

Every material product requirement should be traceable through:

```text
source or standard
→ buyer problem
→ product decision
→ owning issue/PR
→ architecture/API/data contract
→ implementation
→ test and operational evidence
→ known limitation or release claim
```

Primary standards, official specifications, and primary research are preferred. Redistribution-restricted standards are referenced but not copied. Generated or inferred requirements must remain distinguishable from normative source text.

## Research-to-gap mapping

| Requirement or gap | Research/standard basis | Applied product decision | Owning work |
|---|---|---|---|
| Relational identity and relationship semantics | Chen (1976); Codd (1970) | Preserve stable schema/table/column identity, keys, cardinality, and relationship evidence across introspection, editing, diff, and export. | Core product; active exporter/introspection PRs |
| Normalization and functional-dependency claims | Codd (1970); Fagin (1977) | Do not call JSON evidence envelopes “3NF” by default; classify observed/declared/inferred dependencies and support reviewed waivers. | #947 |
| Partition and hot-key decisions | PostgreSQL Global Development Group (2026a) | Recommend partitioning only from workload/capacity evidence; verify pruning, uniqueness, planning, and retention effects on real PostgreSQL. | #947, #951 |
| Temporal snapshot lifecycle | Snodgrass (1999); W3C (2013) | Separate capture/availability/valid/system time; use typed derivation and promotion history; metadata recovery must not be misrepresented as live DB rollback. | #948 |
| Architecture description and authority boundaries | ISO/IEC/IEEE (2022) | Keep product, identity, document, LLM, PIM, and central-governance responsibilities explicit; maintain concern/viewpoint/model traceability. | ADR-0002, #950, #952, #953 |
| Secure software delivery | NIST (2022) | Current-head review/checks, migration proof, dependency/security evidence, remediation, and release traceability are delivery requirements. | #953; protected ruleset; PR #943 |
| Cryptographic key and secret lifecycle | Barker (2020); OWASP (n.d.) | Treat environment/file injection as explicit bootstrap transport, add credential authority, metadata, least privilege, rotation, revocation, and DSN re-encryption. | #946 |
| Zero-trust and continuous access | Rose et al. (2020); IETF (2015); OpenID Foundation (2025) | Select a truthful deployment profile, bind issuer/audience/organization/tenant, support lifecycle provisioning, and re-evaluate access after revocation. | #950 |
| Generative-AI risk and grounding | NIST (2024) | Route LLM work through contextual-orchestrator; preserve evidence/model/prompt metadata; verify grounding; do not auto-publish or grant migration authority. | #952 |
| Provenance exchange | W3C (2013); CNCF (n.d.) | Keep normalized authoritative records and optionally project PROV/CloudEvents-compatible evidence/receipts with idempotency and source hashes. | #948, #952, #953 |
| Accessible UI and design-system evidence | W3C (2023) | Require keyboard/focus/contrast/zoom/forced-colors/reduced-motion evidence, Storybook states, exact-value alternatives, and Figma ↔ code/test mapping. | PR #944; #899; #928; #953 |
| Relationship-aware layout | Gansner et al. (1993) | Use deterministic relationship-aware layout with cycles/disconnected components and bounded fallback; treat layout coordinates as presentation, not semantic distance. | PR #856; #951 |
| Fuzzing untrusted boundaries | Manès et al. (2019) | Maintain mutation/property tests at DSN, identifier, snapshot, DBML/DDL, import/export, connector, and migration-plan boundaries. | #949, #951, #952, #953 |
| Supply-chain provenance | SLSA Community (2025) | Produce source/build provenance, artifact hashes, pinned/reviewed build inputs, SBOMs, and signed release evidence. | #953 |
| Recurring protected PR loop | Central `.github` reusable scheduler and canonical Strix repair #1153 | Run review/fix automation hourly without treating provider latency as completion and without bypassing protected approvals/checks; refresh immutable pins after central repair. | PR #943; central #1153; #953 |

## Claim boundaries

- **Standards alignment is not certification.** CSAP, SOC 2, ISO, WCAG, SCIM, SLSA, or NIST references create engineering requirements and evidence maps; they do not establish an external audit result.
- **Observed is not inferred.** Catalog introspection and executed tests may create observed evidence; model/LLM heuristics remain inferred or proposed until reviewed.
- **A historical check is not current evidence.** Review and check success belongs to one exact commit SHA.
- **A timestamp is not a temporal model.** Capture time, availability, valid time, system time, and knowledge cutoff have different semantics.
- **A dry run is not apply authority.** Persistent target mutation remains non-GA until #949's approval, execution, convergence, and recovery gates close.
- **Projects are not tenants.** Multi-tenant SaaS is not claimed until #950 proves authority and isolation at every storage/queue/cache/connector boundary.
- **Masking is not the only privacy control.** Authorized work requires usable schema metadata; protection relies on access purpose, least privilege, encryption, broadcast minimization, retention, and audit.
- **Rust is not a quality claim by itself.** #951 requires measured leverage, parity, fuzzing, packaging, cancellation, observability, and rollback before any hotspot moves.

## APA 7th references

Barker, E. (2020). *Recommendation for key management: Part 1—General* (NIST Special Publication 800-57 Part 1 Revision 5). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-57pt1r5

Chen, P. P.-S. (1976). The entity-relationship model—Toward a unified view of data. *ACM Transactions on Database Systems, 1*(1), 9–36. https://doi.org/10.1145/320434.320440

Cloud Native Computing Foundation. (n.d.). *CloudEvents specification*. https://github.com/cloudevents/spec

Codd, E. F. (1970). A relational model of data for large shared data banks. *Communications of the ACM, 13*(6), 377–387. https://doi.org/10.1145/362384.362685

Fagin, R. (1977). Multivalued dependencies and a new normal form for relational databases. *ACM Transactions on Database Systems, 2*(3), 262–278. https://doi.org/10.1145/320557.320571

Gansner, E. R., Koutsofios, E., North, S. C., & Vo, K.-P. (1993). A technique for drawing directed graphs. *IEEE Transactions on Software Engineering, 19*(3), 214–230. https://doi.org/10.1109/32.221135

Internet Engineering Task Force. (2015). *System for Cross-domain Identity Management: Protocol* (RFC 7644). https://www.rfc-editor.org/rfc/rfc7644

International Organization for Standardization, International Electrotechnical Commission, & Institute of Electrical and Electronics Engineers. (2022). *Software, systems and enterprise—Architecture description* (ISO/IEC/IEEE 42010:2022). https://www.iso.org/standard/74393.html

Manès, V. J. M., Han, H., Han, C., Cha, S. K., Egele, M., Schwartz, E. J., & Woo, M. (2019). The art, science, and engineering of fuzzing: A survey. *IEEE Transactions on Software Engineering, 47*(11), 2312–2331. https://doi.org/10.1109/TSE.2019.2946569

National Institute of Standards and Technology. (2022). *Secure software development framework (SSDF) version 1.1: Recommendations for mitigating the risk of software vulnerabilities* (NIST Special Publication 800-218). https://doi.org/10.6028/NIST.SP.800-218

National Institute of Standards and Technology. (2024). *Artificial intelligence risk management framework: Generative artificial intelligence profile* (NIST AI 600-1). https://doi.org/10.6028/NIST.AI.600-1

Open Worldwide Application Security Project. (n.d.). *Secrets management cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

OpenID Foundation. (2025). *OpenID Continuous Access Evaluation Profile 1.0 final specification*. https://openid.net/specs/openid-caep-1_0-final.html

PostgreSQL Global Development Group. (2026a). *PostgreSQL 18 documentation: Table partitioning*. https://www.postgresql.org/docs/18/ddl-partitioning.html

PostgreSQL Global Development Group. (2026b). *PostgreSQL 18 documentation: Data definition*. https://www.postgresql.org/docs/18/ddl.html

Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust architecture* (NIST Special Publication 800-207). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207

SLSA Community. (2025). *Supply-chain levels for software artifacts specification, version 1.2*. https://slsa.dev/spec/v1.2/

Snodgrass, R. T. (1999). *Developing time-oriented database applications in SQL*. Morgan Kaufmann.

World Wide Web Consortium. (2013). *PROV-O: The PROV ontology*. https://www.w3.org/TR/prov-o/

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/