[CmdletBinding()]
param(
    [string]$ProjectId = $env:GCP_PROJECT_ID,
    [string]$Region = $(if ($env:GCP_REGION) { $env:GCP_REGION } else { "europe-west1" }),
    [string]$Repository = $(if ($env:REPO) { $env:REPO } else { "habits-bot" }),
    [string]$ServiceName = $(if ($env:SERVICE_NAME) { $env:SERVICE_NAME } else { "habits-diary-bot" }),
    [string]$ImageTag = $env:IMAGE_TAG,
    [string]$ServiceAccount = $env:SERVICE_ACCOUNT,
    [switch]$SetTelegramWebhook
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Invoke-GCloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: gcloud $($Arguments -join ' ')"
    }
}

Import-DotEnv (Join-Path $RepoRoot ".env")

if (-not $ProjectId) {
    $ProjectId = $env:GCP_PROJECT_ID
}
if (-not $ProjectId) {
    throw "GCP project is required. Pass -ProjectId or set GCP_PROJECT_ID."
}
if (-not $ServiceAccount) {
    $ServiceAccount = "tg-habits-bot@$ProjectId.iam.gserviceaccount.com"
}

$QueueName = if ($env:TRANSCRIPTION_QUEUE_NAME) {
    $env:TRANSCRIPTION_QUEUE_NAME
} else {
    "transcriptions"
}
$GitStatus = & git -C $RepoRoot status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect Git worktree."
}
if ($GitStatus) {
    throw "Production deployment requires a clean Git worktree. Commit or remove changes first."
}
$GitSha = (& git -C $RepoRoot rev-parse HEAD).Trim()
if (-not $GitSha) {
    throw "Unable to resolve Git commit SHA."
}
$ImageTag = $GitSha
$Image = "${Region}-docker.pkg.dev/${ProjectId}/${Repository}/${ServiceName}:${ImageTag}"

Write-Host "Project: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Image: $Image"

Push-Location $RepoRoot
try {
    Invoke-GCloud services enable cloudtasks.googleapis.com secretmanager.googleapis.com `
        "--project=$ProjectId"

    & gcloud tasks queues describe $QueueName "--location=$Region" "--project=$ProjectId" *> $null
    if ($LASTEXITCODE -eq 0) {
        Invoke-GCloud tasks queues update $QueueName "--location=$Region" `
            "--max-concurrent-dispatches=2" "--max-dispatches-per-second=1" `
            "--max-attempts=5" "--project=$ProjectId"
    } else {
        Invoke-GCloud tasks queues create $QueueName "--location=$Region" `
            "--max-concurrent-dispatches=2" "--max-dispatches-per-second=1" `
            "--max-attempts=5" "--project=$ProjectId"
    }

    Invoke-GCloud builds submit . "--tag=$Image" "--project=$ProjectId"

    $existingServiceUrl = (& gcloud run services describe $ServiceName `
        "--region=$Region" "--project=$ProjectId" "--format=value(status.url)" 2>$null)
    if (-not $env:TRANSCRIPTION_DISPATCH_URL -and $existingServiceUrl) {
        $env:TRANSCRIPTION_DISPATCH_URL = $existingServiceUrl.Trim()
    }

    $environmentValues = @{
        GCP_PROJECT_ID = $ProjectId
        GCP_REGION = $Region
        TRANSCRIPTION_QUEUE_NAME = $QueueName
        APP_COMMIT_SHA = $GitSha
    }
    foreach ($name in @(
        "FIRESTORE_COLLECTION_TEXT_ENTRY_COLLECTIONS",
        "TEXT_ENTRY_MAX_UTF16_UNITS"
    )) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($value) {
            $environmentValues[$name] = $value
        }
    }
    if ($env:TRANSCRIPTION_DISPATCH_URL) {
        $environmentValues.TRANSCRIPTION_DISPATCH_URL = $env:TRANSCRIPTION_DISPATCH_URL
    }
    $environmentArgument = ($environmentValues.GetEnumerator() | ForEach-Object {
        "$($_.Key)=$($_.Value)"
    }) -join ","

    $secretNames = @(
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN_DEBUG",
        "TELEGRAM_WEBHOOK_SECRET",
        "REMINDERS_DISPATCH_SECRET",
        "TRANSCRIPTION_DISPATCH_SECRET",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY"
    )
    $secretBindings = @()
    foreach ($secretName in $secretNames) {
        & gcloud secrets describe $secretName "--project=$ProjectId" *> $null
        if ($LASTEXITCODE -eq 0) {
            $secretBindings += "${secretName}=${secretName}:latest"
        }
    }
    if (-not ($secretBindings -match "^TRANSCRIPTION_DISPATCH_SECRET=")) {
        throw "Secret Manager secret TRANSCRIPTION_DISPATCH_SECRET was not found."
    }

    $deployArguments = @(
        "run", "deploy", $ServiceName,
        "--image=$Image",
        "--region=$Region",
        "--project=$ProjectId",
        "--platform=managed",
        "--allow-unauthenticated",
        "--service-account=$ServiceAccount",
        "--port=8080",
        "--min-instances=0",
        "--max-instances=1",
        "--timeout=1800",
        "--labels=app-commit-sha=$GitSha",
        "--update-env-vars=$environmentArgument",
        "--update-secrets=$($secretBindings -join ',')"
    )
    Invoke-GCloud @deployArguments

    $serviceUrl = (& gcloud run services describe $ServiceName `
        "--region=$Region" "--project=$ProjectId" "--format=value(status.url)").Trim()
    if (-not $serviceUrl) {
        throw "Cloud Run service URL was not returned after deployment."
    }

    if (-not $env:TRANSCRIPTION_DISPATCH_URL) {
        Invoke-GCloud run services update $ServiceName "--region=$Region" `
            "--project=$ProjectId" `
            "--update-env-vars=TRANSCRIPTION_DISPATCH_URL=$serviceUrl"
    }

    if ($SetTelegramWebhook) {
        $token = $env:TELEGRAM_BOT_TOKEN
        if (-not $token) {
            $token = (& gcloud secrets versions access latest `
                "--secret=TELEGRAM_BOT_TOKEN" "--project=$ProjectId")
        }
        $webhookUrl = "$($serviceUrl.TrimEnd('/'))/telegram/webhook"
        $body = @{ url = $webhookUrl }
        $webhookSecret = $env:TELEGRAM_WEBHOOK_SECRET
        if (-not $webhookSecret -and ($secretBindings -match "^TELEGRAM_WEBHOOK_SECRET=")) {
            $webhookSecret = (& gcloud secrets versions access latest `
                "--secret=TELEGRAM_WEBHOOK_SECRET" "--project=$ProjectId")
        }
        if ($webhookSecret) {
            $body.secret_token = $webhookSecret
        }
        Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/setWebhook" `
            -Body $body | Out-Null
        Write-Host "Telegram webhook set to $webhookUrl"
    }

    Write-Host "Deployment complete: $serviceUrl"
    Write-Host "Commit: $GitSha"
    Write-Host "Health check: $serviceUrl/health"
} finally {
    Pop-Location
}
