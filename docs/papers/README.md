# Papers

Background reading for the fuzzing setup in `backend/fuzz/`.

- Manès, Han, Han, Cha, Egele, Schwartz, Woo, *"The Art, Science, and
  Engineering of Fuzzing: A Survey"* ([arXiv:1812.00140](https://arxiv.org/abs/1812.00140),
  open access). A taxonomy of fuzzing, including the coverage-guided /
  feedback-directed model (AFL, libFuzzer) that
  [Atheris](https://github.com/google/atheris) implements for Python, and the
  seed-corpus + mutation loop our harnesses rely on. It frames why we target
  untrusted-input surfaces (snapshot parsers, DSN/error redaction, DDL
  rendering) and assert crash-freedom + security invariants rather than only
  example-based tests.
