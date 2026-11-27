<#
.SYNOPSIS
  Creates the "ECIT Admin Console" app registration in YOUR tenant and grants admin consent.

.DESCRIPTION
  Single-tenant, public client (desktop) app with redirect URI http://localhost and these
  Microsoft Graph DELEGATED permissions:
    User.Read, User.Read.All, User.EnableDisableAccount.All,
    User-PasswordProfile.ReadWrite.All, User.RevokeSessions.All,
    UserAuthenticationMethod.ReadWrite.All
  No secret or certificate is created. Run once per tenant, signed in as a Global Administrator.
  Prints the Application (client) ID and Directory (tenant) ID to paste into the app
  (Connections... -> Save).

.EXAMPLE
  .\create-app-registration.ps1 -TenantId contoso.onmicrosoft.com

.NOTES
  Requires: Install-Module Microsoft.Graph.Applications, Microsoft.Graph.Identity.SignIns -Scope CurrentUser
  Free tool by ECIT IT Services - info@ecit.co.il - ecit.co.il
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TenantId,
    [string]$DisplayName = "ECIT Admin Console"
)

$ErrorActionPreference = "Stop"
$GraphAppId = "00000003-0000-0000-c000-000000000000"   # Microsoft Graph
$Scopes = @(
    "User.Read",
    "User.Read.All",
    "User.EnableDisableAccount.All",
    "User-PasswordProfile.ReadWrite.All",
    "User.RevokeSessions.All",
    "UserAuthenticationMethod.ReadWrite.All"
)

Import-Module Microsoft.Graph.Applications
Import-Module Microsoft.Graph.Identity.SignIns

Write-Host "Signing in to $TenantId (use a Global Administrator account)..." -ForegroundColor Cyan
Connect-MgGraph -TenantId $TenantId -NoWelcome -Scopes @(
    "Application.ReadWrite.All",
    "DelegatedPermissionGrant.ReadWrite.All"
)
$tenant = (Get-MgContext).TenantId

$existing = Get-MgApplication -Filter "displayName eq '$DisplayName'" -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warning "An app registration named '$DisplayName' already exists (client ID $($existing[0].AppId))."
    Write-Warning "Use that one, or delete it first / run with -DisplayName 'Another name'."
    return
}

# Look up the permission IDs by name instead of hard-coding them.
$graphSp = Get-MgServicePrincipal -Filter "appId eq '$GraphAppId'"
$access = foreach ($s in $Scopes) {
    $perm = $graphSp.Oauth2PermissionScopes | Where-Object { $_.Value -eq $s }
    if (-not $perm) { throw "Microsoft Graph permission '$s' was not found." }
    @{ Id = $perm.Id; Type = "Scope" }
}

Write-Host "Creating app registration '$DisplayName'..." -ForegroundColor Cyan
$app = New-MgApplication -DisplayName $DisplayName `
    -SignInAudience "AzureADMyOrg" `
    -IsFallbackPublicClient `
    -PublicClient @{ RedirectUris = @("http://localhost") } `
    -RequiredResourceAccess @(@{ ResourceAppId = $GraphAppId; ResourceAccess = @($access) }) `
    -Web @{ HomePageUrl = "https://ecit.co.il" }

$sp = New-MgServicePrincipal -AppId $app.AppId

Write-Host "Granting admin consent for the $($Scopes.Count) delegated permissions..." -ForegroundColor Cyan
New-MgOauth2PermissionGrant -ClientId $sp.Id -ConsentType "AllPrincipals" `
    -ResourceId $graphSp.Id -Scope ($Scopes -join " ") | Out-Null

Write-Host ""
Write-Host "Done. In ECIT Admin Console click Connections... and enter:" -ForegroundColor Green
Write-Host "  Tenant:                   $tenant"
Write-Host "  Application (client) ID:  $($app.AppId)"
Write-Host ""
Write-Host "To remove access later: Entra admin center -> App registrations -> $DisplayName -> Delete."

Disconnect-MgGraph | Out-Null
