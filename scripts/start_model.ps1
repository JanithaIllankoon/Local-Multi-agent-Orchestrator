# scripts/start_model.ps1
#
# Starts one llama-server for a given role on port 8001 (the single endpoint
# the orchestrator uses in MVP mode). Handles the space in the project path
# for you, so you don't have to remember to quote it.
#
# Usage (from the project folder):
#   powershell -ExecutionPolicy Bypass -File scripts/start_model.ps1 reasoner
#
# Roles map to the model files you downloaded. Edit LLAMA_EXE if your llama.cpp
# folder is somewhere else.

param(
    [ValidateSet("supervisor","strong_coder","reasoner","uncensored","vision")]
    [string]$role = "reasoner"
)

$LLAMA_EXE = "C:\llama\llama-b9810-bin-win-cuda-13.3-x64\llama-server.exe"
$MODELS = "C:\Local Multi-agent Orchestrator\models"

# Pick the model file and any extra flags for the requested role.
switch ($role) {
    "supervisor"   { $model = "$MODELS\Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"; $extra = "-ngl 99 --n-cpu-moe 28" }
    "strong_coder" { $model = "$MODELS\Qwen3.6-27B-Q3_K_S.gguf";                   $extra = "-ngl 35" }
    "reasoner"     { $model = "$MODELS\DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf";     $extra = "-ngl 99" }
    "uncensored"   { $model = "$MODELS\Qwen3-8B-abliterated-q3_k_m.gguf";          $extra = "-ngl 99" }
    "vision"       { $model = "$MODELS\Qwen3-VL-8B-Thinking-abliterated-v1.Q4_K_M.gguf"; $extra = "-ngl 99" }
}

if (-not (Test-Path $model)) { Write-Host "Model file not found: $model" -ForegroundColor Red; exit 1 }

Write-Host "Starting '$role' on http://127.0.0.1:8001 ..." -ForegroundColor Green
Write-Host "(big models take a while to load; the port opens only when ready)"

# Quote the model path because the project folder name contains spaces.
$cmd = "-m `"$model`" --host 127.0.0.1 --port 8001 --jinja -c 8192 $extra"
Start-Process -FilePath $LLAMA_EXE -ArgumentList $cmd
