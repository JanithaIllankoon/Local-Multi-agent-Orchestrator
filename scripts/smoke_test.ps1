# scripts/smoke_test.ps1
#
# Step 0 of the build: prove llama.cpp serves an OpenAI-style endpoint BEFORE
# writing any orchestrator code. Run llama-server first (see README), then:
#
#   powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1
#
# Expect a JSON reply with choices[0].message.content. If this works, the rest
# of the project is just Python over HTTP.

$body = @{
    model    = "local"
    messages = @(
        @{ role = "system"; content = "You are a terse assistant." },
        @{ role = "user";   content = "Reply with exactly: hello orchestrator" }
    )
    temperature = 0.1
    max_tokens  = 32
} | ConvertTo-Json -Depth 5

try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8001/v1/chat/completions" `
        -Method Post -ContentType "application/json" -Body $body
    Write-Host "OK - model replied:" -ForegroundColor Green
    Write-Host $resp.choices[0].message.content
} catch {
    Write-Host "FAILED to reach llama-server on 127.0.0.1:8001" -ForegroundColor Red
    Write-Host "Is llama-server running? See README 'Smoke test' section."
    Write-Host $_.Exception.Message
}
