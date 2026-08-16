$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CandidatePath = Join-Path $ProjectRoot "02_output\university_journal_candidate.tmp"
$RequestPath = Join-Path $ProjectRoot "02_output\university_journal_request.tmp"
$HelperPath = Join-Path $PSScriptRoot "supplement_university_journal.py"
$RepositoryApiPath = "repos/ponponponkichi/kobe-higher-education-news/contents/02_output/public_news.json"

Set-Location -LiteralPath $ProjectRoot

Write-Host ""
Write-Host "University Journal supplement for the public site"
Write-Host "-------------------------------------------------"
Write-Host "1. Read the latest public JSON from GitHub"
Write-Host "2. Fetch only the University Journal RSS from this PC"
Write-Host "3. Show the articles that would be added"
Write-Host "4. Run syntax checks and unit tests"
Write-Host "5. Publish only after you type PUBLISH"
Write-Host ""
Write-Host "No article body or RSS summary will be newly published."
Write-Host "If any step fails, the GitHub public JSON will not be updated."
Write-Host ""

$StartAnswer = Read-Host "Continue to the preview? Type Y"
if ($StartAnswer -cne "Y") {
    Write-Host "Cancelled. GitHub was not changed."
    exit 0
}

try {
    $null = Get-Command python -ErrorAction Stop
    $null = Get-Command gh -ErrorAction Stop

    & python $HelperPath --candidate $CandidatePath --request $RequestPath
    if ($LASTEXITCODE -ne 0) {
        throw "The preview could not be prepared."
    }

    Write-Host ""
    $PublishAnswer = Read-Host "Publish this candidate? Type PUBLISH"
    if ($PublishAnswer -cne "PUBLISH") {
        Write-Host "Cancelled. GitHub was not changed."
        exit 0
    }

    Write-Host ""
    Write-Host "Running syntax checks..."
    & python -m compileall -q (Join-Path $ProjectRoot "03_scripts")
    if ($LASTEXITCODE -ne 0) {
        throw "The syntax check failed."
    }

    Write-Host "Running unit tests..."
    $env:PYTHONPATH = (Resolve-Path (Join-Path $ProjectRoot "03_scripts")).Path
    & python -m unittest discover -s (Join-Path $ProjectRoot "03_scripts\tests") -v
    if ($LASTEXITCODE -ne 0) {
        throw "The unit tests failed."
    }

    Write-Host "Checking for a newer GitHub update..."
    & python $HelperPath --candidate $CandidatePath --request $RequestPath --verify-only
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub changed after the preview. Run this file again."
    }

    Write-Host "Publishing the prepared JSON to GitHub..."
    & gh api --method PUT $RepositoryApiPath --input $RequestPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub rejected the update."
    }

    Write-Host ""
    Write-Host "Completed. Streamlit will read the updated GitHub JSON shortly."
    Write-Host "https://kobe-higher-education-news.streamlit.app"
}
catch {
    Write-Host ""
    Write-Error $_
    Write-Host "The GitHub public JSON was not updated by the failed step."
    exit 1
}
finally {
    if (Test-Path -LiteralPath $CandidatePath) {
        Remove-Item -LiteralPath $CandidatePath -Force
    }
    if (Test-Path -LiteralPath $RequestPath) {
        Remove-Item -LiteralPath $RequestPath -Force
    }
}
