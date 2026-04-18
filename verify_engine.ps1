param(
    [string]$EnvFile = ".env.local",
    [switch]$NonInteractive,
    [switch]$VerboseHttp
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Stage {
    param(
        [string]$Message
    )
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Write-HttpTrace {
    param([string]$Message)
    if ($VerboseHttp) {
        Write-Host "[HTTP] $Message" -ForegroundColor DarkYellow
    }
}

function Get-HttpErrorDetail {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    $msg = $ErrorRecord.Exception.Message
    try {
        $resp = $ErrorRecord.Exception.Response
        if ($null -ne $resp) {
            $statusCode = ""
            if ($resp.PSObject.Properties.Name -contains "StatusCode") {
                $statusCode = [string]$resp.StatusCode
            }

            $bodyText = ""
            try {
                $stream = $resp.GetResponseStream()
                if ($null -ne $stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $bodyText = $reader.ReadToEnd()
                    $reader.Close()
                }
            }
            catch {
                $bodyText = ""
            }

            if (-not [string]::IsNullOrWhiteSpace($bodyText)) {
                $preview = if ($bodyText.Length -gt 300) { $bodyText.Substring(0, 300) + "..." } else { $bodyText }
                if (-not [string]::IsNullOrWhiteSpace($statusCode)) {
                    return "HTTP $statusCode | $preview"
                }
                return $preview
            }

            if (-not [string]::IsNullOrWhiteSpace($statusCode)) {
                return "HTTP $statusCode | $msg"
            }
        }
    }
    catch {
        # Fall through to default message.
    }
    return $msg
}

function Read-EnvFile {
    param([string]$Path)

    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $map
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
        if ($trimmed.StartsWith("#")) { continue }
        if ($trimmed -notmatch "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") { continue }

        $key = $matches[1]
        $value = $matches[2].Trim()

        if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        } elseif ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $map[$key] = $value
    }

    return $map
}

function Resolve-ConfigValue {
    param(
        [string[]]$Keys,
        [hashtable]$EnvMap,
        [string]$PromptLabel,
        [switch]$Secret
    )

    foreach ($key in $Keys) {
        if ([string]::IsNullOrWhiteSpace($key)) { continue }

        $fromProcess = [Environment]::GetEnvironmentVariable($key)
        if (-not [string]::IsNullOrWhiteSpace($fromProcess)) {
            return $fromProcess.Trim()
        }

        if ($EnvMap.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace([string]$EnvMap[$key])) {
            return ([string]$EnvMap[$key]).Trim()
        }
    }

    if ($NonInteractive) {
        return ""
    }

    if ($Secret) {
        $secure = Read-Host -Prompt "$PromptLabel (hidden)" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }

    return (Read-Host -Prompt $PromptLabel).Trim()
}

function Extract-Products {
    param([object]$Payload)

    if ($null -eq $Payload) { return @() }
    if ($Payload -is [System.Array]) { return @($Payload) }

    $candidateKeys = @("products", "items", "data", "results", "result", "offers")
    foreach ($k in $candidateKeys) {
        if ($Payload.PSObject.Properties.Name -contains $k) {
            $v = $Payload.$k
            if ($v -is [System.Array]) { return @($v) }
        }
    }

    if ($Payload.PSObject.Properties.Name -contains "product") {
        return @($Payload.product)
    }

    return @()
}

function Get-FieldValue {
    param(
        [object]$Object,
        [string[]]$Keys
    )

    foreach ($k in $Keys) {
        if ($Object.PSObject.Properties.Name -contains $k) {
            $v = $Object.$k
            if ($null -ne $v -and -not [string]::IsNullOrWhiteSpace([string]$v)) {
                return [string]$v
            }
        }
    }
    return ""
}

$passed = 0
$failed = 0

Write-Host "My Narrative - External Integration Diagnostics" -ForegroundColor Magenta
Write-Host "Env source: $EnvFile" -ForegroundColor DarkGray

$envMap = Read-EnvFile -Path $EnvFile

# ---------------------------------------------------------------------------
# TEST 1: Rakuten OAuth Handshake
# ---------------------------------------------------------------------------
Write-Stage "Test 1 - Rakuten OAuth Handshake"

$rakutenAppId = Resolve-ConfigValue -Keys @("RAKUTEN_APP_ID", "RAKUTEN_CLIENT_ID") -EnvMap $envMap -PromptLabel "Enter RAKUTEN_APP_ID (or RAKUTEN_CLIENT_ID)"
$rakutenSecret = Resolve-ConfigValue -Keys @("RAKUTEN_TOKEN", "RAKUTEN_CLIENT_SECRET") -EnvMap $envMap -PromptLabel "Enter RAKUTEN_TOKEN (or RAKUTEN_CLIENT_SECRET)" -Secret
$rakutenTokenUrl = Resolve-ConfigValue -Keys @("RAKUTEN_TOKEN_URL") -EnvMap $envMap -PromptLabel "Enter Rakuten token URL (or press Enter for default)"
if ([string]::IsNullOrWhiteSpace($rakutenTokenUrl)) {
    $rakutenTokenUrl = "https://api.rakutenmarketing.com/token"
}

$bearerToken = ""

try {
    if ([string]::IsNullOrWhiteSpace($rakutenAppId) -or [string]::IsNullOrWhiteSpace($rakutenSecret)) {
        throw "Missing Rakuten credentials (RAKUTEN_APP_ID/RAKUTEN_TOKEN or RAKUTEN_CLIENT_ID/RAKUTEN_CLIENT_SECRET)."
    }

    $pair = "{0}:{1}" -f $rakutenAppId, $rakutenSecret
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($pair)
    $basic = [Convert]::ToBase64String($bytes)

    $tokenBody = @{
        grant_type = "client_credentials"
    }

    $rakutenScope = Resolve-ConfigValue -Keys @("RAKUTEN_SCOPE") -EnvMap $envMap -PromptLabel "Enter RAKUTEN_SCOPE (optional)"
    if (-not [string]::IsNullOrWhiteSpace($rakutenScope)) {
        $tokenBody["scope"] = $rakutenScope
    }

    $tokenResponse = Invoke-RestMethod -Method Post -Uri $rakutenTokenUrl -Headers @{
        Authorization = "Basic $basic"
        Accept = "application/json"
    } -Body $tokenBody -ContentType "application/x-www-form-urlencoded" -TimeoutSec 30
    Write-HttpTrace ("POST {0}" -f $rakutenTokenUrl)
    Write-HttpTrace ("Headers: Authorization=Basic <base64:{0} chars>, Content-Type=application/x-www-form-urlencoded, Accept=application/json" -f $basic.Length)

    $bearerToken = [string]$tokenResponse.access_token
    if ([string]::IsNullOrWhiteSpace($bearerToken)) {
        throw "Token endpoint returned no access_token."
    }

    $tokenPreview = if ($bearerToken.Length -gt 20) { $bearerToken.Substring(0, 20) + "..." } else { $bearerToken }
    Write-Success ("Rakuten OAuth token issued. access_token: {0}" -f $tokenPreview)
    $passed++
}
catch {
    Write-Fail ("Rakuten OAuth handshake failed: {0}" -f (Get-HttpErrorDetail -ErrorRecord $_))
    $failed++
}

# ---------------------------------------------------------------------------
# TEST 2: Rakuten Catalog Pulse
# ---------------------------------------------------------------------------
Write-Stage "Test 2 - Rakuten Catalog Pulse"

try {
    if ([string]::IsNullOrWhiteSpace($bearerToken)) {
        throw "No bearer token available from Test 1."
    }

    $rakutenApiBase = Resolve-ConfigValue -Keys @("RAKUTEN_API_BASE") -EnvMap $envMap -PromptLabel "Enter Rakuten API base URL (or press Enter for default)"
    if ([string]::IsNullOrWhiteSpace($rakutenApiBase)) {
        $rakutenApiBase = "https://api.rakutenmarketing.com"
    }
    $rakutenApiBase = $rakutenApiBase.TrimEnd("/")

    $catalogUri = "{0}/products?query=jacket&limit=1" -f $rakutenApiBase
    $catalogHeaders = @{
        Authorization = "Bearer $bearerToken"
        Accept = "application/json"
    }
    if (-not [string]::IsNullOrWhiteSpace($rakutenAppId)) {
        $catalogHeaders["X-Application-Id"] = $rakutenAppId
    }
    Write-HttpTrace ("GET {0}" -f $catalogUri)
    Write-HttpTrace ("Headers: Authorization=Bearer <redacted>, X-Application-Id={0}, Accept=application/json" -f ($(if ($rakutenAppId) { "set" } else { "not-set" })))

    $catalogPayload = Invoke-RestMethod -Method Get -Uri $catalogUri -Headers $catalogHeaders -TimeoutSec 30
    $products = Extract-Products -Payload $catalogPayload
    Write-HttpTrace ("Response: products_count={0}" -f $products.Count)
    if ($products.Count -lt 1) {
        throw "Product API returned zero items."
    }

    $first = $products[0]
    $title = Get-FieldValue -Object $first -Keys @("title", "productName", "name", "product_name")
    $price = Get-FieldValue -Object $first -Keys @("price", "salePrice", "priceValue", "amount", "current_price")
    if ([string]::IsNullOrWhiteSpace($title)) { $title = "<missing-title>" }
    if ([string]::IsNullOrWhiteSpace($price)) { $price = "<missing-price>" }

    Write-Success ("Catalog access confirmed. Product: {0} | Price: {1}" -f $title, $price)
    $passed++
}
catch {
    Write-Fail ("Rakuten catalog pulse failed: {0}" -f (Get-HttpErrorDetail -ErrorRecord $_))
    $failed++
}

# ---------------------------------------------------------------------------
# TEST 3: Supabase Vector Database Ping
# ---------------------------------------------------------------------------
Write-Stage "Test 3 - Supabase Vector Database Ping"

try {
    $supabaseUrl = Resolve-ConfigValue -Keys @("SUPABASE_URL") -EnvMap $envMap -PromptLabel "Enter SUPABASE_URL"
    $supabaseKey = Resolve-ConfigValue -Keys @("SUPABASE_KEY") -EnvMap $envMap -PromptLabel "Enter SUPABASE_KEY" -Secret
    if ([string]::IsNullOrWhiteSpace($supabaseUrl) -or [string]::IsNullOrWhiteSpace($supabaseKey)) {
        throw "Missing SUPABASE_URL and/or SUPABASE_KEY."
    }

    $supabaseUrl = $supabaseUrl.TrimEnd("/")
    $uri = "{0}/rest/v1/global_inventory?select=id&limit=1" -f $supabaseUrl
    $headers = @{
        apikey = $supabaseKey
        Authorization = "Bearer $supabaseKey"
        Accept = "application/json"
    }
    Write-HttpTrace ("GET {0}" -f $uri)
    Write-HttpTrace ("Headers: apikey=<redacted>, Authorization=Bearer <redacted>, Accept=application/json")

    $resp = Invoke-WebRequest -Method Get -Uri $uri -Headers $headers -TimeoutSec 30
    Write-HttpTrace ("Response: HTTP {0}" -f $resp.StatusCode)
    if ($resp.StatusCode -ne 200) {
        throw "Expected HTTP 200, got HTTP $($resp.StatusCode)."
    }

    Write-Success ("Supabase ping returned HTTP {0}." -f $resp.StatusCode)
    $passed++
}
catch {
    Write-Fail ("Supabase ping failed: {0}" -f (Get-HttpErrorDetail -ErrorRecord $_))
    $failed++
}

Write-Host ""
Write-Host "------------------------- FINAL REPORT -------------------------" -ForegroundColor DarkGray
if ($failed -eq 0) {
    Write-Host ("PASS: {0} / FAIL: {1}" -f $passed, $failed) -ForegroundColor Green
} else {
    Write-Host ("PASS: {0} / FAIL: {1}" -f $passed, $failed) -ForegroundColor Yellow
}

if ($failed -gt 0) {
    exit 1
}
exit 0
