# UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location $PSScriptRoot

Write-Host "=== 1. Git init ===" -ForegroundColor Cyan
if (-not (Test-Path .git)) {
    git init
    Write-Host "OK: repo created" -ForegroundColor Green
} else {
    Write-Host "OK: repo already exists" -ForegroundColor Green
}

Write-Host "`n=== 2. git add . ===" -ForegroundColor Cyan
git add .
Write-Host "OK" -ForegroundColor Green

Write-Host "`n=== 3. git commit ===" -ForegroundColor Cyan
git commit -m "Initial commit: tenderbot"
if ($LASTEXITCODE -eq 0) { Write-Host "OK" -ForegroundColor Green } else { Write-Host "Commit done or nothing to commit" -ForegroundColor Yellow }

Write-Host "`n=== 4. Next: add GitHub remote and push ===" -ForegroundColor Cyan
Write-Host "1) Create new repo at https://github.com/new (e.g. name: tenderbot, no README)"
Write-Host "2) Run (replace YOUR_USERNAME with your GitHub login):"
Write-Host ""
Write-Host '  git remote add origin https://github.com/YOUR_USERNAME/tenderbot.git' -ForegroundColor White
Write-Host '  git branch -M main' -ForegroundColor White
Write-Host '  git push -u origin main' -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
