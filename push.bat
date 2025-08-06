# 1. Ensure credentials.json is deleted locally
if (Test-Path "credentials.json") { Remove-Item "credentials.json" }

# 2. Remove from git tracking completely
git rm --cached credentials.json 2>$null

# 3. Update .gitignore
@"
.env
credentials.json
__pycache__/
venv/
*.pyc
temp_receipt.jpg
"@ | Set-Content .gitignore

# 4. Commit the cleanup
git add .gitignore
git commit -m "Permanently remove credentials.json and update gitignore"

# 5. Use BFG tool for complete history cleanup (alternative to filter-branch)
# Download BFG: https://rtyley.github.io/bfg-repo-cleaner/
# java -jar bfg.jar --delete-files credentials.json .git
# git reflog expire --expire=now --all && git gc --prune=now --aggressive

# 6. Force push to completely overwrite GitHub history
git push origin main --force-with-lease
