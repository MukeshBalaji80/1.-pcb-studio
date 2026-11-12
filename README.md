# PCB Studio

A KiCad companion for inspecting .kicad_pcb and .kicad_sch files, extracting component references, exporting a starter BOM, and invoking KiCad CLI checks.

## Windows setup
```powershell
py -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```
Open http://127.0.0.1:8001. Optional: install KiCad 7+ and add kicad-cli to PATH for DRC/ERC. The quick parser is not a replacement for KiCad validation. Files are processed in memory.