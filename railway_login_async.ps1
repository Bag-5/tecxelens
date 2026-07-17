$proc = Start-Process -NoNewWindow -PassThru -FilePath "railway" -ArgumentList "login --browserless" -RedirectStandardOutput railway_login_url.txt -WorkingDirectory "C:\Users\Bag-5\Desktop\tecxelens"
Start-Sleep -Seconds 5
Get-Content railway_login_url.txt -ErrorAction SilentlyContinue
