param(
    [int]$MockPort = 18765,
    [int]$PromptPort = 8989,
    [int]$SessionTimeoutSeconds = 6
)

$ErrorActionPreference = "Stop"

function Wait-Health {
    param(
        [string]$Url,
        [int]$Retry = 30
    )
    for ($i = 0; $i -lt $Retry; $i++) {
        try {
            $resp = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 2
            if ($resp.status -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }
    throw "Health check failed: $Url"
}

function New-MockSession {
    param([string]$Scenario)
    $body = @{ scenario = $Scenario } | ConvertTo-Json
    return Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$MockPort/mock/create" -ContentType "application/json" -Body $body
}

function Track-Session {
    param(
        [string]$SessionId,
        [string]$Title,
        [string]$Summary
    )
    $body = @{
        session_id = $SessionId
        risk_level = "high"
        display_title = $Title
        display_summary = $Summary
    } | ConvertTo-Json
    return Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$PromptPort/track" -ContentType "application/json" -Body $body
}

function Run-Case {
    param(
        [string]$Scenario,
        [string]$Title,
        [string]$Summary
    )
    Write-Host ""
    Write-Host "=== Case: $Scenario ===" -ForegroundColor Cyan
    $s = New-MockSession -Scenario $Scenario
    Write-Host "Mock session_id: $($s.session_id)"
    $r = Track-Session -SessionId $s.session_id -Title $Title -Summary $Summary
    Write-Host ("Track response: accepted={0}, session_id={1}, tracking_id={2}" -f $r.accepted, $r.session_id, $r.tracking_id)
}

$repoRoot = Split-Path -Path $PSScriptRoot -Parent

Write-Host "Starting mock sdk..." -ForegroundColor Yellow
$mock = Start-Process -FilePath "python" `
    -ArgumentList @("$repoRoot\tools\mock_sdk_server.py", "--port", "$MockPort") `
    -PassThru -WindowStyle Minimized

Write-Host "Starting desktop prompt..." -ForegroundColor Yellow
$prompt = Start-Process -FilePath "python" `
    -ArgumentList @("$repoRoot\app.py", "--sdk-base-url", "http://127.0.0.1:$MockPort", "--listen-port", "$PromptPort", "--session-timeout-seconds", "$SessionTimeoutSeconds") `
    -PassThru -WindowStyle Normal

try {
    Wait-Health -Url "http://127.0.0.1:$MockPort/health"
    Wait-Health -Url "http://127.0.0.1:$PromptPort/health"
    Write-Host "Services are ready." -ForegroundColor Green

    Run-Case -Scenario "success" -Title "高危命令授权" -Summary "rm -rf /important"
    Start-Sleep -Seconds 5

    Run-Case -Scenario "failed" -Title "高危命令授权" -Summary "删除关键配置文件"
    Start-Sleep -Seconds 4

    Run-Case -Scenario "timeout" -Title "高危命令授权" -Summary "等待用户按压拇指"
    Start-Sleep -Seconds ($SessionTimeoutSeconds + 2)

    Write-Host ""
    Write-Host "Demo completed. Check desktop popup history for all cases." -ForegroundColor Green
    Write-Host "Press Enter to stop services..."
    Read-Host | Out-Null
}
finally {
    foreach ($p in @($prompt, $mock)) {
        if ($null -ne $p) {
            try {
                if (-not $p.HasExited) {
                    Stop-Process -Id $p.Id -Force
                }
            } catch {
            }
        }
    }
}

