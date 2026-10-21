$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$tempRoot = Join-Path $projectRoot 'build\tmp'
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
& 'D:\myagent\python\python.exe' -m PyInstaller --noconfirm --clean --windowed --onedir --name TokenView --icon (Join-Path $projectRoot 'assets/TokenView.ico') --distpath release --workpath build/portable --specpath build --add-data "$(Join-Path $projectRoot 'assets/codex.png');assets" --add-data "$(Join-Path $projectRoot 'assets/antigravity.png');assets" --add-data "$(Join-Path $projectRoot 'assets/deepseek.ico');assets" (Join-Path $projectRoot 'main.py')
if ($LASTEXITCODE -ne 0) { throw 'Portable build failed' }
Copy-Item -LiteralPath 'docs/便携版说明.txt' -Destination 'release/TokenView/使用说明.txt'
