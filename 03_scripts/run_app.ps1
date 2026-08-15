$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python -m streamlit run (Join-Path $scriptDir 'app.py')
