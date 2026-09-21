param([switch]$Elevated)

$ErrorActionPreference = 'Stop'
$ruleGroup = 'Shift AI Local Wi-Fi'
$rules = @(
    @{ Name = 'Shift AI API (LocalSubnet)'; Protocol = 'TCP'; Port = 8000 },
    @{ Name = 'Shift AI App (LocalSubnet)'; Protocol = 'TCP'; Port = 3100 },
    @{ Name = 'Shift AI Discovery (LocalSubnet)'; Protocol = 'UDP'; Port = 45831 }
)

function Test-ShiftRule($spec) {
    try {
        $rule = Get-NetFirewallRule -DisplayName $spec.Name -ErrorAction Stop |
            Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' } |
            Select-Object -First 1
        if (-not $rule) { return $false }
        $port = $rule | Get-NetFirewallPortFilter
        $address = $rule | Get-NetFirewallAddressFilter
        return [string]$rule.Profile -eq 'Any' -and
            $port.Protocol -eq $spec.Protocol -and
            [string]$port.LocalPort -eq [string]$spec.Port -and
            [string]$address.RemoteAddress -eq 'LocalSubnet'
    } catch {
        return $false
    }
}

if (($rules | Where-Object { -not (Test-ShiftRule $_) }).Count -eq 0) {
    Write-Host 'Shift AI LocalSubnet firewall rules are ready.'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdministrator) {
    if ($Elevated) {
        Write-Error 'Administrator access is required to configure the Shift AI LocalSubnet rules.'
        exit 1
    }
    Write-Host 'Windows will ask once for permission to add three LocalSubnet-only Shift AI rules.'
    try {
        $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Elevated'
        )
        exit $process.ExitCode
    } catch {
        Write-Error 'Firewall setup was cancelled. Shift AI cannot accept phone connections while inbound traffic is blocked.'
        exit 1
    }
}

# Replace the blanket Public-profile rules created by Node's Windows prompt.
# They allow every Node server/port from any remote address and are broader than
# this app needs. Application rules for other programs are left untouched.
Get-NetFirewallRule -DisplayName 'Node.js JavaScript Runtime' -ErrorAction SilentlyContinue |
    Where-Object { $_.Direction -eq 'Inbound' -and [string]$_.Profile -match 'Public|Any' } |
    ForEach-Object {
        $application = $_ | Get-NetFirewallApplicationFilter
        $port = $_ | Get-NetFirewallPortFilter
        $address = $_ | Get-NetFirewallAddressFilter
        if ($application.Program -like '*\node.exe' -and
            [string]$port.LocalPort -eq 'Any' -and
            [string]$address.RemoteAddress -eq 'Any') {
            $_ | Remove-NetFirewallRule
        }
    }

foreach ($spec in $rules) {
    Get-NetFirewallRule -DisplayName $spec.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $spec.Name -Group $ruleGroup -Direction Inbound -Action Allow `
        -Protocol $spec.Protocol -LocalPort $spec.Port -RemoteAddress LocalSubnet -Profile Any `
        -EdgeTraversalPolicy Block | Out-Null
}

if (($rules | Where-Object { -not (Test-ShiftRule $_) }).Count -ne 0) {
    Write-Error 'Shift AI firewall rules could not be verified.'
    exit 1
}

Write-Host 'Shift AI can now accept connections only from devices on the local network.'
exit 0
