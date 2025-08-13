# PowerShell deployment script for Rock Pi
# Run this on your Windows machine to deploy to Rock Pi

param(
    [Parameter(Mandatory=$true)]
    [string]$RockPiUser,
    
    [Parameter(Mandatory=$true)]
    [string]$RockPiIP,
    
    [string]$RemotePath = "/home/$RockPiUser/patco-schedules"
)

Write-Host "Deploying PATCO Schedule Processing to Rock Pi..." -ForegroundColor Green

# Check if ssh is available
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: SSH not found. Please install OpenSSH or use WSL." -ForegroundColor Red
    exit 1
}

# Check if scp is available
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: SCP not found. Please install OpenSSH or use WSL." -ForegroundColor Red
    exit 1
}

try {
    # Create remote directory
    Write-Host "Creating remote directory..." -ForegroundColor Yellow
    ssh "$RockPiUser@$RockPiIP" "mkdir -p $RemotePath"

    # Copy files to Rock Pi (excluding git and Python cache files)
    Write-Host "Copying files to Rock Pi..." -ForegroundColor Yellow
    
    # Use robocopy to copy files, then scp to transfer
    $tempDir = Join-Path $env:TEMP "patco-deploy"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    
    # Copy rockpi directory to temp, excluding unwanted files
    robocopy "rockpi" $tempDir /E /XD ".git" "__pycache__" /XF "*.pyc" "*.pyo" /NP /NDL /NJH /NJS
    
    # Compress for faster transfer
    $zipFile = Join-Path $env:TEMP "patco-deploy.zip"
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipFile -Force
    
    # Transfer zip file
    scp $zipFile "$RockPiUser@${RockPiIP}:/tmp/patco-deploy.zip"
    
    # Extract on remote
    ssh "$RockPiUser@$RockPiIP" "mkdir -p $RemotePath; cd $RemotePath; unzip -o /tmp/patco-deploy.zip; rm /tmp/patco-deploy.zip"
    
    # Clean up local temp files
    Remove-Item $tempDir -Recurse -Force
    Remove-Item $zipFile -Force

    # Run setup script on Rock Pi
    Write-Host "Running setup script on Rock Pi..." -ForegroundColor Yellow
    ssh "$RockPiUser@$RockPiIP" "cd $RemotePath; chmod +x setup.sh; ./setup.sh"

    Write-Host ""
    Write-Host "SUCCESS: Deployment complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. SSH into your Rock Pi: ssh $RockPiUser@$RockPiIP"
    Write-Host "2. Configure AWS credentials:"
    Write-Host "   cd $RemotePath"
    Write-Host "   aws configure"
    Write-Host "3. Edit config.json if needed"
    Write-Host "4. Test the setup:"
    Write-Host "   cd $RemotePath"
    Write-Host "   ./run_daily_check.sh"
    Write-Host ""
    Write-Host "The service will run automatically every day."
}
catch {
    Write-Host "ERROR: Deployment failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
