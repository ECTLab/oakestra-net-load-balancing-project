HALO LaTeX reference snapshot
Snapshot date: 2026-11-25

This is a byte-for-byte copy of the latest working LaTeX sources at delivery time,
matching the existing AUTthesis-revised-v11.pdf build. AUTthesis.pdf is the matching
compiled reference, not a new rendering. Source-manifest hashes identify this copy.

Main file: AUTthesis.tex
Algorithm chapter: chapter3.tex, which includes system-model.tex, method-cluster.tex,
method-root.tex, method-integration.tex, and method-example.tex.

The original Persian source text is preserved. The surrounding implementation guides
are English and are the implementation specification for their respective repositories.
The same complete reference snapshot is supplied to both repositories for citation;
this does not assign both implementations to either repository.

Build with Python 3 and XeLaTeX: python build_thesis.py
Install the TeX packages required by commands.tex/AUTthesis.cls, including xepersian.
The source expects B Nazanin, Times New Roman, and IranNastaliq fonts. Font files and
TeX distributions are not bundled. The supplied PDF can be read without those fonts
being installed. The builder uses an isolated _build directory for generated files.

No old PDF revisions, auxiliary build files, backups, or unrelated working documents
are included. sha256_original records original bytes; sha256_lf allows verification of
text files after Git line-ending conversion. Binary files must match original hashes.
