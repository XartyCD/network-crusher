# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


RULE_PREFIX = "TeamRadarStructure-ProcessNetBlock"
RULE_GROUP = "TeamRadarStructure Process Network Toggle"


class NetworkUiError(RuntimeError):
    pass


@dataclass(slots=True)
class RuleNames:
    outbound: str
    inbound: str


@dataclass(slots=True)
class BlockStatus:
    program_path: str
    is_blocked: bool
    outbound_name: str | None = None
    inbound_name: str | None = None


@dataclass(slots=True)
class ProcessEntry:
    process_name: str
    process_id: int
    path: str
    blocked: bool


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_python_executable() -> str:
    def _is_valid_python(candidate: str | None) -> bool:
        if not candidate:
            return False
        resolved = os.path.abspath(candidate)
        if not os.path.isfile(resolved):
            return False
        if "windowsapps" in resolved.lower():
            return False
        return True

    candidates = [
        sys.executable,
        getattr(sys, "_base_executable", None),
    ]

    for candidate in candidates:
        if _is_valid_python(candidate):
            return os.path.abspath(candidate)

    which_candidates = [
        shutil.which("python.exe"),
        shutil.which("pythonw.exe"),
        shutil.which("python"),
        shutil.which("python3.exe"),
        shutil.which("python3"),
    ]
    for candidate in which_candidates:
        if _is_valid_python(candidate):
            return os.path.abspath(candidate)

    raise NetworkUiError(
        "Не удалось определить реальный путь к python.exe. Запустите приложение из Python, установленного не через alias, или откройте терминал от администратора."
    )


def relaunch_as_admin() -> bool:
    script_path = os.path.abspath(sys.argv[0])
    params = subprocess.list2cmdline([script_path, *sys.argv[1:]])
    executable = get_python_executable()
    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        params,
        os.getcwd(),
        1,
    )
    return rc > 32


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_powershell(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message = stderr or stdout or f"PowerShell exited with code {result.returncode}"
        raise NetworkUiError(message)
    return result.stdout


def _json_literal(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def get_rule_names(program_path: str) -> RuleNames:
    normalized = os.path.abspath(program_path).lower().encode("utf-8")
    digest = hashlib.sha1(normalized).hexdigest().upper()
    return RuleNames(
        outbound=f"{RULE_PREFIX}-Out-{digest}",
        inbound=f"{RULE_PREFIX}-In-{digest}",
    )


def resolve_program_path(
    *,
    program_path: str | None = None,
    process_name: str | None = None,
    process_id: int | None = None,
) -> str:
    if program_path:
        return os.path.abspath(program_path)

    payload = {
        "processName": process_name,
        "processId": process_id,
    }
    script = f"""
$payload = @'
{_json_literal(payload)}
'@ | ConvertFrom-Json

$process = $null
if ($payload.processId) {{
  $process = Get-Process -Id ([int]$payload.processId) -ErrorAction Stop
}} elseif ($payload.processName) {{
  $matches = @(Get-Process -Name $payload.processName -ErrorAction Stop)
  if ($matches.Count -lt 1) {{
    throw "Процесс не найден."
  }}
  $process = $matches[0]
}}

if (-not $process) {{
  throw "Укажите путь к .exe, имя процесса или PID."
}}

$path = $null
try {{
  $path = $process.Path
}} catch {{}}

if (-not $path) {{
  try {{
    $path = $process.MainModule.FileName
  }} catch {{
    throw "Не удалось определить путь к процессу."
  }}
}}

if (-not $path) {{
  throw "Не удалось определить путь к процессу."
}}

$path
"""
    return run_powershell(script).strip()


def get_block_status(program_path: str) -> BlockStatus:
    program_path = os.path.abspath(program_path)
    rules = get_rule_names(program_path)
    payload = {
        "programPath": program_path,
        "outbound": rules.outbound,
        "inbound": rules.inbound,
    }
    script = f"""
$payload = @'
{_json_literal(payload)}
'@ | ConvertFrom-Json

$outbound = Get-NetFirewallRule -DisplayName $payload.outbound -ErrorAction SilentlyContinue
$inbound = Get-NetFirewallRule -DisplayName $payload.inbound -ErrorAction SilentlyContinue

[PSCustomObject]@{{
  programPath = $payload.programPath
  isBlocked = [bool]($outbound -or $inbound)
  outboundName = if ($outbound) {{ $outbound.DisplayName }} else {{ $null }}
  inboundName = if ($inbound) {{ $inbound.DisplayName }} else {{ $null }}
}} | ConvertTo-Json -Compress
"""
    data = json.loads(run_powershell(script))
    return BlockStatus(
        program_path=data["programPath"],
        is_blocked=bool(data["isBlocked"]),
        outbound_name=data.get("outboundName"),
        inbound_name=data.get("inboundName"),
    )


def block_program(program_path: str) -> BlockStatus:
    program_path = os.path.abspath(program_path)
    rules = get_rule_names(program_path)
    payload = {
        "programPath": program_path,
        "outbound": rules.outbound,
        "inbound": rules.inbound,
        "group": RULE_GROUP,
    }
    script = f"""
$payload = @'
{_json_literal(payload)}
'@ | ConvertFrom-Json

Get-NetFirewallRule -DisplayName $payload.outbound -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null
Get-NetFirewallRule -DisplayName $payload.inbound -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null

New-NetFirewallRule `
  -DisplayName $payload.outbound `
  -Group $payload.group `
  -Program $payload.programPath `
  -Direction Outbound `
  -Action Block `
  -Profile Any `
  -Enabled True | Out-Null

New-NetFirewallRule `
  -DisplayName $payload.inbound `
  -Group $payload.group `
  -Program $payload.programPath `
  -Direction Inbound `
  -Action Block `
  -Profile Any `
  -Enabled True | Out-Null
"""
    run_powershell(script)
    return get_block_status(program_path)


def unblock_program(program_path: str) -> BlockStatus:
    program_path = os.path.abspath(program_path)
    rules = get_rule_names(program_path)
    payload = {
        "outbound": rules.outbound,
        "inbound": rules.inbound,
        "programPath": program_path,
    }
    script = f"""
$payload = @'
{_json_literal(payload)}
'@ | ConvertFrom-Json

Get-NetFirewallRule -DisplayName $payload.outbound -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null
Get-NetFirewallRule -DisplayName $payload.inbound -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null
"""
    run_powershell(script)
    return get_block_status(program_path)


def _normalize_json_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def list_processes(filter_text: str = "") -> list[ProcessEntry]:
    payload = {"group": RULE_GROUP}
    script = """
$payload = @'
__PAYLOAD_JSON__
'@ | ConvertFrom-Json

$ruleNames = @(Get-NetFirewallRule -Group $payload.group -ErrorAction SilentlyContinue | Select-Object -ExpandProperty DisplayName)

$rows = Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath } |
  Select-Object `
    @{Name='ProcessName';Expression={$_.Name}},
    @{Name='ProcessId';Expression={[int]$_.ProcessId}},
    @{Name='Path';Expression={$_.ExecutablePath}}

[PSCustomObject]@{
  processes = $rows
  ruleNames = $ruleNames
} | ConvertTo-Json -Compress -Depth 4
""".replace("__PAYLOAD_JSON__", _json_literal(payload))
    raw = run_powershell(script).strip()
    data = json.loads(raw) if raw else {}
    rows = _normalize_json_rows(data.get("processes"))
    rule_names = {str(item) for item in (data.get("ruleNames") or [])}
    normalized_filter = (filter_text or "").strip().lower()

    results: list[ProcessEntry] = []

    for row in rows:
        path = row.get("Path")
        name = row.get("ProcessName")
        pid = row.get("ProcessId")
        if not path or not name or pid is None:
            continue

        haystack = f"{name} {pid} {path}".lower()
        if normalized_filter and normalized_filter not in haystack:
            continue

        rules = get_rule_names(str(path))
        is_blocked = rules.outbound in rule_names or rules.inbound in rule_names

        results.append(
            ProcessEntry(
                process_name=str(name),
                process_id=int(pid),
                path=str(path),
                blocked=is_blocked,
            )
        )

    results.sort(key=lambda item: (item.process_name.lower(), item.process_id))
    return results
