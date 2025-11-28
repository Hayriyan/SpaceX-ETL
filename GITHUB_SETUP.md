# GitHub Setup Instructions

## Quick Push Commands

After creating a repository on GitHub, run these commands:

```bash
# Add the remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/SpaceX-ETL.git

# Or if you prefer SSH (if you have SSH keys set up):
# git remote add origin git@github.com:YOUR_USERNAME/SpaceX-ETL.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Step-by-Step Guide

1. **Create GitHub Repository:**
   - Go to https://github.com/new
   - Name: `SpaceX-ETL` (or your preferred name)
   - Choose Public or Private
   - **Don't** check "Initialize with README"
   - Click "Create repository"

2. **Copy the repository URL** from GitHub (HTTPS or SSH)

3. **Run these commands in your terminal:**
   ```bash
   cd "/Users/hayriyan/Desktop/Code/AI 2.2/SpaceX"
   
   # Add remote (replace URL with your actual repo URL)
   git remote add origin https://github.com/YOUR_USERNAME/SpaceX-ETL.git
   
   # Ensure you're on main branch
   git branch -M main
   
   # Push to GitHub
   git push -u origin main
   ```

4. **If prompted for credentials:**
   - Use a Personal Access Token (not your password)
   - Generate one at: https://github.com/settings/tokens
   - Select scope: `repo` (full control of private repositories)

## Future Updates

After making changes, push updates with:
```bash
git add .
git commit -m "Your commit message"
git push
```

