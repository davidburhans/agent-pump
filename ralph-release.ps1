#!/usr/bin/env pwsh

# Ralph Loop - Simple test-fix-repeat until green
# Usage: ./ralph-new.ps1 -MaxIterations 20 -TestCommand "cargo test" -IterateCommand "aidev fix"

param(
    [int]$MaxIterations = 600,
    [int]$TimeoutSeconds = 14400,
    # [int]$TimeoutSeconds = 3600,
    [string]$TestCommand = "exit 1",
    [string]$IterateCommand = @"
opencode run "Please review this project and make sure it is ready for a full production release. First impressions are everything.
As such, this code-base needs to be immaculate and the product a joy to use. Obviously we need it to be rock solid and fast too. Do the needful. 
You are on Windows. Use uv for interacting with the environment: 

uv run ruff check .
uv run pyright
uv run pytest tests/ -v
"
--agent build --model lmstudio/qwen/qwen3-coder-next
-f ./BEST_PRACTICES.md -f ./README.md
"@,
    [int]$ShowLines = 30,
    [switch]$Verbose = $false
)

function Run-JobWithMonitor {
    param(
        [string]$Command,
        [int]$TimeoutSeconds,
        [string]$Label,
        [int]$Iteration,
        [int]$MaxIterations,
        [int]$ShowLines
    )

    $startTime = Get-Date
    
    # Prepare environment for the job
    $safeCmd = $Command
    $currentPath = $Env:Path
    $workingDir = (Get-Location).Path

    $job = Start-Job -ScriptBlock {
        param($cmd, $p, $wd)
        $ErrorActionPreference = 'Continue'
        $Env:Path = $p
        Set-Location -Path $wd
        
        # Write to a temp file to execute reliably and stream better than IEX
        $tempScript = [System.IO.Path]::GetTempFileName() + ".ps1"
        # Sanitize command to single line to avoid parser errors with multiline arguments
        $cleanCmd = $cmd -replace "[\r\n]+", " "
        Set-Content -Path $tempScript -Value $cleanCmd
        
        # Execute
        & $tempScript 2>&1 | Out-String -Stream
        
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
        
        # Clean up
        Remove-Item $tempScript -ErrorAction SilentlyContinue
        
        Write-Output "RALPH_EXIT_CODE:$code"
    } -ArgumentList $safeCmd, $currentPath, $workingDir

    $fullOutputList = New-Object System.Collections.Generic.List[string]
    $exitCode = $null
    $timedOut = $false
    $spinner = @('|', '/', '-', '\')
    $spinIdx = 0

    while ($job.State -eq 'Running') {
        # Update Timer
        $elapsed = (Get-Date) - $startTime
        $timeStr = "{0:mm}:{0:ss}" -f $elapsed
        $spinChar = $spinner[$spinIdx % 4]
        $spinIdx++

        # Check Timeout
        if ($elapsed.TotalSeconds -gt $TimeoutSeconds) {
            $timedOut = $true
            Stop-Job -Job $job
            
            try { [Console]::CursorLeft = 0 } catch { }
            [Console]::Write("   [Iter $Iteration/$MaxIterations] [$timeStr] ❌ TIMEOUT exceeded ($TimeoutSeconds s)".PadRight(100))
            break
        }

        # Check for new output
        if ($job.HasMoreData) {
            $newOutput = Receive-Job -Job $job
            
            if ($newOutput) {
                foreach ($item in $newOutput) {
                    $str = "$item" # Force string
                    if ($str -match "RALPH_EXIT_CODE:(\d+)") {
                        $exitCode = [int]$matches[1]
                        continue
                    }
                    $fullOutputList.Add($str)
                    
                    if (-not [string]::IsNullOrWhiteSpace($str)) {
                         $lastLine = $str
                    }
                }
            }
        }
        
    $lastLines = New-Object System.Collections.Generic.List[string]
    $firstPass = $true
    
    # Pre-allocate lines on screen to avoid scroll-on-write issues at bottom
    # We write $ShowLines, so let's ensure we have space
    for ($i=0; $i -lt $ShowLines; $i++) { [Console]::WriteLine("") }
    # Move back up
    try { 
        $startTop = [Console]::CursorTop - $ShowLines
        if ($startTop -lt 0) { $startTop = 0 }
        [Console]::SetCursorPosition(0, $startTop)
    } catch {}

    while ($job.State -eq 'Running') {
        # Update Timer
        $elapsed = (Get-Date) - $startTime
        $timeStr = "{0:mm}:{0:ss}" -f $elapsed
        $spinChar = $spinner[$spinIdx % 4]
        $spinIdx++

        # Check Timeout
        if ($elapsed.TotalSeconds -gt $TimeoutSeconds) {
            $timedOut = $true
            Stop-Job -Job $job
            
            # Move to bottom
             try { 
                [Console]::SetCursorPosition(0, $startTop + $ShowLines)
            } catch { }
            
            [Console]::WriteLine("   [Iter $Iteration/$MaxIterations] [$timeStr] ❌ TIMEOUT exceeded ($TimeoutSeconds s)".PadRight(100))
            break
        }

        # Check for new output
        if ($job.HasMoreData) {
            $newOutput = Receive-Job -Job $job
            
            if ($newOutput) {
                foreach ($item in $newOutput) {
                    $str = "$item" # Force string
                    if ($str -match "RALPH_EXIT_CODE:(\d+)") {
                        $exitCode = [int]$matches[1]
                        continue
                    }
                    
                    # --- NATIVE COMMAND ERROR FILTERING ---
                    # 1. Check for the line containing the actual message
                    if ($str -match "^\s*\+\s+CategoryInfo\s+:\s+NotSpecified:\s+\((.*?)\)\s*\[\],\s*RemoteException") {
                        $str = $matches[1]
                        # Often has :String suffix
                        if ($str -match "^(.*):String$") { $str = $matches[1] }
                    }
                    # 2. Filter out other error wrapper noise
                    elseif ($str -match "^\s*At .+:\d+ char:\d+") { continue }
                    elseif ($str -match "^\s*\+\s+FullyQualifiedErrorId\s+:") { continue }
                    elseif ($str -match "^\s*\+\s+") { continue } # Other source context lines
                    # -------------------------------------

                    $fullOutputList.Add($str)
                    
                    if (-not [string]::IsNullOrWhiteSpace($str)) {
                         $lastLines.Add($str)
                         if ($lastLines.Count -gt $ShowLines) { $lastLines.RemoveAt(0) }
                    }
                }
            }
        }
        
        # Update Display
        try { [Console]::CursorVisible = $false } catch {}
        $width = [Math]::Max(80, [Console]::WindowWidth)
        $prefix = "   [Iter $Iteration/$MaxIterations] [$timeStr] $spinChar "
        
        # Always return to start
        try { [Console]::SetCursorPosition(0, $startTop) } catch {}
        
        # Prepare lines to write
        $linesToWrite = @()
        if ($lastLines.Count -eq 0) {
             $linesToWrite += "${Label}..."
             while ($linesToWrite.Count -lt $ShowLines) { $linesToWrite += "" }
        } else {
             foreach ($l in $lastLines) { $linesToWrite += $l }
             while ($linesToWrite.Count -lt $ShowLines) { $linesToWrite += "" }
        }
        
        for ($i=0; $i -lt $linesToWrite.Count; $i++) {
            $line = $linesToWrite[$i]
            # Basic clean
            $displayLine = $line -replace "`t", " " -replace "[`r`n]", ""
            
            if ($i -eq 0) {
                $p = $prefix
            } else {
                $p = " " * $prefix.Length
            }

            $avail = $width - $p.Length - 1 
            if ($avail -gt 3 -and $displayLine.Length -gt $avail) { 
                $displayLine = $displayLine.Substring(0, $avail - 3) + "..." 
            }
            
            $msg = $p + $displayLine
            if ($msg.Length -ge $width) { $msg = $msg.Substring(0, $width - 1) }
            
            [Console]::Write($msg.PadRight($width - 1))
            # Only write newline if not the last line
            if ($i -lt $linesToWrite.Count - 1) {
                [Console]::Write("`n")
            }
        }
        try { [Console]::CursorVisible = $true } catch {}
        
        Start-Sleep -Milliseconds 100
    }

    # Final cleanup 
    try { 
        [Console]::SetCursorPosition(0, $startTop + $ShowLines)
        [Console]::CursorVisible = $true 
    } catch { }

    
    if (-not $timedOut) {
        # Get remaining
        $remaining = Receive-Job -Job $job
        if ($remaining) {
            foreach ($item in $remaining) {
                $str = "$item"
                if ($str -match "RALPH_EXIT_CODE:(\d+)") {
                    $exitCode = [int]$matches[1]
                } else {
                    $fullOutputList.Add($str)
                }
            }
        }
    }
    
    Remove-Job -Job $job
    
    if ($timedOut) {
        return @{ Output = $fullOutputList; ExitCode = 124; TimedOut = $true }
    }
    
    # Fallback exit code
    if ($null -eq $exitCode) { $exitCode = 1 }

    return @{ Output = $fullOutputList; ExitCode = $exitCode; TimedOut = $false }
    }
}

Write-Host "🚀 Ralph Loop - RRS-2 Build Agent" -ForegroundColor Green
Write-Host "   Testing with: $TestCommand" -ForegroundColor Cyan
if ($IterateCommand) {
    Write-Host "   Iterating with: $IterateCommand" -ForegroundColor Cyan
}
Write-Host "   Max iterations: $MaxIterations" -ForegroundColor Cyan
Write-Host "   Timeout: ${TimeoutSeconds}s" -ForegroundColor Cyan
Write-Host ""

$iteration = 0
$lastErrorCount = -1

while ($iteration -lt $MaxIterations) {
    $iteration++
    Write-Host "🔄 Iteration $iteration/$MaxIterations" -ForegroundColor Yellow
    
    # ---------------------------------------------------------
    # 1. RUN TESTS
    # ---------------------------------------------------------
    Write-Host "   Running tests..." -ForegroundColor Gray
    
    $testResult = Run-JobWithMonitor -Command $TestCommand `
                                     -TimeoutSeconds 600 `
                                     -Label "Testing" `
                                     -Iteration $iteration `
                                     -MaxIterations $MaxIterations `
                                     -ShowLines $ShowLines

    $outputString = $testResult.Output -join "`n"
    $testExitCode = $testResult.ExitCode
    
    # Count errors
    $errorCount = ($testResult.Output | Select-String "error\[|FAILED" | Measure-Object).Count
    Write-Host "   Errors detected: $errorCount" -ForegroundColor Red
    Write-Host "   Exit Code: $testExitCode" -ForegroundColor DarkGray
    
    if ($Verbose) {
        Write-Host "   Full Test Output:" -ForegroundColor Gray
        $testResult.Output | ForEach-Object { Write-Host "     $_" }
    }

    # Success Condition
    $successPattern = $outputString | Select-String "test result: ok"
    
    if ($testExitCode -eq 0 -or ($errorCount -eq 0 -and $successPattern)) {
        Write-Host "✅ Tests passed! Ralph Loop completed successfully." -ForegroundColor Green
        exit 0
    }

    # Stopping Conditions
    if ($lastErrorCount -ne -1 -and $errorCount -eq $lastErrorCount -and -not $IterateCommand) {
        Write-Host "⚠️  No progress and no iterate command. Stopping." -ForegroundColor Yellow
        exit 1
    }
    $lastErrorCount = $errorCount

    # ---------------------------------------------------------
    # 2. RUN ITERATION
    # ---------------------------------------------------------
    if ($IterateCommand) {
        Write-Host "   Running iteration command..." -ForegroundColor Blue
        $iterResult = Run-JobWithMonitor -Command $IterateCommand `
                                         -TimeoutSeconds $TimeoutSeconds `
                                         -Label "Iterating" `
                                         -Iteration $iteration `
                                         -MaxIterations $MaxIterations `
                                         -ShowLines $ShowLines
                                         
        if ($iterResult.TimedOut) {
             Write-Host "❌ Iteration command timed out." -ForegroundColor Red
        } elseif ($iterResult.ExitCode -ne 0) {
             Write-Host "⚠️  Iteration command failed with code $($iterResult.ExitCode)." -ForegroundColor Yellow
             Write-Host "   Output:" -ForegroundColor Gray
             $iterResult.Output | ForEach-Object { Write-Host "     $_" }
        }
    } else {
        Write-Host "   Waiting 2 seconds before retry..." -ForegroundColor Blue
        Start-Sleep 2
    }
}

Write-Host "❌ Ralph Loop exhausted without success" -ForegroundColor Red
exit 1
