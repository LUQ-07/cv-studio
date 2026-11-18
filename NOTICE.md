# Third-party notices (technical inventory – not legal advice)

| Component | Use | Licence | Obligation |
|---|---|---|---|
| Qt for Python (PySide6 / Qt 6) | GUI, PDF preview | LGPL-3.0 (or commercial Qt licence) | Ship LGPL text, keep Qt DLLs dynamically linked & replaceable (PyInstaller one-folder does this), state that Qt is used. Review LGPL requirements for a **paid** Store app before release; a commercial Qt licence removes them. |
| ReportLab (open-source) | PDF | BSD-style | Keep copyright notice |
| python-docx / lxml | DOCX | MIT / BSD | Keep notice |
| Pillow | images | MIT-CMU (HPND) | Keep notice |
| PyInstaller | packaging only | GPL-2.0 + bootloader exception | Allowed for commercial apps; confirm current terms |
| Carlito, Caladea | bundled fonts | SIL OFL 1.1 | Licence texts in `cvstudio/assets/fonts/licenses/`; do not sell the fonts alone |
| DejaVu Sans Mono | bundled font | Bitstream Vera / DejaVu free licence | Licence text included |

Templates and the icon are original works made for this project; no Canva or other third-party artwork is used.
Before each release: generate an SBOM for the exact build (`pip-licenses --with-urls --format=markdown`) and include required licence files in the package.
