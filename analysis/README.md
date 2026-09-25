# Analysis

This workspace is for exploratory data-quality analysis in Jupyter notebooks.
Keep reusable analysis helpers in `src/` and notebooks in `notebooks/`. Do not
put a virtual environment or generated notebook checkpoints under version
control.

## Setup

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
jupyter lab
```

The source Excel files remain in the repository-level `data/` directory.
