[CmdletBinding()]
param(
  [ValidateSet("block", "unblock", "status")]
  [string]$Action = "status",

  [string]$ProgramPath,

  [string]$ProcessName,

  [int]$ProcessId,

  [int]$DurationSeconds = 0
)

. "$PSScriptRoot/process-network-common.ps1"

if (-not (Test-IsAdministrator)) {
  throw "Запустите PowerShell от имени администратора. Для управления правилами Windows Firewall нужны права администратора."
}

$resolvedProgramPath = Resolve-ProgramPath -InputPath $ProgramPath -InputProcessName $ProcessName -InputProcessId $ProcessId

switch ($Action) {
  "block" {
    Ensure-BlockRules -ResolvedProgramPath $resolvedProgramPath | Out-Null
    Write-Host "Сеть для процесса заблокирована:" -ForegroundColor Green
    Write-Host $resolvedProgramPath

    if ($DurationSeconds -gt 0) {
      Write-Host "Авторазблокировка через $DurationSeconds сек." -ForegroundColor Yellow
      Start-Sleep -Seconds $DurationSeconds
      Remove-BlockRules -ResolvedProgramPath $resolvedProgramPath | Out-Null
      Write-Host "Сеть для процесса разблокирована." -ForegroundColor Green
    }
  }

  "unblock" {
    Remove-BlockRules -ResolvedProgramPath $resolvedProgramPath | Out-Null
    Write-Host "Сеть для процесса разблокирована:" -ForegroundColor Green
    Write-Host $resolvedProgramPath
  }

  "status" {
    $status = Get-ProgramBlockStatus -ResolvedProgramPath $resolvedProgramPath
    Write-Host ""
    Write-Host "Program: $($status.ProgramPath)"
    Write-Host "Blocked: $($status.IsBlocked)"
    if ($status.Outbound) {
      Write-Host "Outbound rule: $($status.Outbound.DisplayName)"
    }
    if ($status.Inbound) {
      Write-Host "Inbound rule:  $($status.Inbound.DisplayName)"
    }
  }
}
