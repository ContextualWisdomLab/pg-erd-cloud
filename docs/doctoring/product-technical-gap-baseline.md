# Product and technical gap baseline: research traceability

This record supports `docs/product-technical-gap-baseline.md`. It records the
research basis for decisions without claiming that a citation alone closes an
implementation gap.

## Research-to-gap mapping

| Gap | Research basis | Applied decision |
|---|---|---|
| Relational core, 3NF, and functional dependency review | Codd (1970) | Keep ownership and membership relations decomposed; explicitly audit exceptions such as immutable snapshot payloads rather than calling JSON “3NF” by default. |
| Entity identity and relationship semantics | Chen (1976) | Preserve schema/table/column identity and relationship cardinality across reverse engineering, editing, and export. |
| Security and operational evidence | NIST (2022) | Treat exact-head checks, dependency scanning, secure workflow boundaries, remediation evidence, and release traceability as delivery requirements. |
| Recurring PR repair and merge control plane | ContextualWisdomLab/.github reusable scheduler, pinned at `aa8503f4383e8328d89104796bc3e9f7da810376` | Run the hourly PR queue loop through OpenCode review/fix automation while retaining normal protected-branch approvals and merge semantics. |
| Fuzzing and untrusted snapshot/DDL inputs | Manès et al. (2019) | Keep mutation/property tests at DSN, snapshot, DDL, export, and identifier trust boundaries. |
| Temporal lineage | Snodgrass (1999) | Treat snapshot timestamps as insufficient; design explicit valid-time/transaction-time lineage and retention before promising rollback. |

## References

Chen, P. P.-S. (1976). The entity-relationship model—Toward a unified view of data. *ACM Transactions on Database Systems, 1*(1), 9–36. https://doi.org/10.1145/320434.320440

Codd, E. F. (1970). A relational model of data for large shared data banks. *Communications of the ACM, 13*(6), 377–387. https://doi.org/10.1145/362384.362685

Manès, V. J. M., Han, H., Han, C., Cha, S. K., Egele, M., Schwartz, E. J., & Woo, M. (2019). The art, science, and engineering of fuzzing: A survey. *IEEE Transactions on Software Engineering, 47*(11), 2312–2331. https://doi.org/10.1109/TSE.2019.2946569

National Institute of Standards and Technology. (2022). *Secure software development framework (SSDF) version 1.1: Recommendations for mitigating the risk of software vulnerabilities* (NIST Special Publication 800-218). https://doi.org/10.6028/NIST.SP.800-218

Snodgrass, R. T. (1999). *Developing time-oriented database applications in SQL*. Morgan Kaufmann.
