& "C:\Program Files\KiCad\10.0\bin\python.exe" "$PSScriptRoot\awg_testbench.py"
if ($LASTEXITCODE -eq 0) {
    Start-Process "$PSScriptRoot\awg_sim_results.png"
}
