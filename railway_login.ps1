$output = & railway login --browserless 2>&1 | Out-String
$output > railway_login_url.txt
Write-Output $output
