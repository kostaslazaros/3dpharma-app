# Deployment Guide for Render

This guide will help you deploy the Drug Compatibility App to Render.

## Prerequisites

1. A GitHub account
2. A Render account (sign up at https://render.com)
3. An OpenAI API key (optional, for AI features)

## Step 1: Push to GitHub

1. Initialize a git repository in the `drug_compatibility_app_deploy` directory:
```bash
cd drug_compatibility_app_deploy
git init
git add .
git commit -m "Initial commit - Drug Compatibility App"
```

2. (Optional but recommended) Generate the compact drug database to reduce RAM usage:
```bash
python scripts/compact_database.py
```
This writes `comprehensive_drug_database_compact.json`, which the app prefers automatically.

3. Create a new repository on GitHub (don't initialize with README)

4. Push your code:
```bash
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Render

### Option A: Using render.yaml (Recommended)

1. Go to https://dashboard.render.com
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect the `render.yaml` file and use those settings
5. Add your OpenAI API key in the Environment Variables section (optional)

### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: drug-compatibility-app (or your preferred name)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
5. Add Environment Variable:
   - **Key**: `OPENAI_API_KEY`
   - **Value**: Your OpenAI API key (optional, only needed for AI features)
6. (Optional) Add Environment Variable for memory savings:
   - **Key**: `ENABLE_OPENFDA_DATA`
   - **Value**: `false` (skip the large OpenFDA dataset on low-memory plans; leave `true` for full data)
7. (Optional) Override the database file if you keep multiple copies:
   - **Key**: `DRUG_DB_FILE`
   - **Value**: `comprehensive_drug_database_compact.json`
8. Click "Create Web Service"

## Step 3: Wait for Deployment

Render will:
1. Install dependencies from `requirements.txt`
2. Build your application
3. Start the Streamlit server
4. Provide you with a public URL

## Step 4: Access Your App

Once deployed, you'll get a URL like: `https://drug-compatibility-app.onrender.com`

## Important Notes

### File Size Limits

- The `comprehensive_drug_database.json` and `OpenFDAfull.json` files may be large
- Render free tier has limits on file sizes
- If you encounter issues, consider:
  - Using a paid Render plan
  - Compressing the JSON files
  - Using external storage (S3, etc.)
  - Disabling the OpenFDA dataset via `ENABLE_OPENFDA_DATA=false`
  - Generating `comprehensive_drug_database_compact.json` with `python scripts/compact_database.py`

### Environment Variables

- `OPENAI_API_KEY`: Required only for the AI Drug Agent tab
- `ENABLE_OPENFDA_DATA`: Toggle to `false` if the OpenFDA dataset pushes the app over memory limits
- `DRUG_DB_FILE`: Use this to point to `comprehensive_drug_database_compact.json` or any other curated dataset
- Without it, all other features will work normally

### Performance

- First load may be slow as the database loads
- Consider using Streamlit's caching (already implemented)
- For production, consider upgrading to a paid Render plan

## Troubleshooting

### App won't start
- Check the build logs in Render dashboard
- Verify all files are in the repository
- Ensure `requirements.txt` is correct

### Database not loading
- Verify `comprehensive_drug_database.json` is in the root directory
- Check file permissions
- Review error logs in Render dashboard

### AI features not working
- Verify `OPENAI_API_KEY` is set correctly
- Check OpenAI API key is valid and has credits
- Review error messages in the app

## Updating Your App

1. Make changes to your code
2. Commit and push to GitHub:
```bash
git add .
git commit -m "Update description"
git push
```
3. Render will automatically redeploy

## Cost Considerations

- **Free Tier**: Limited resources, may have slower performance
- **Starter Plan**: Better performance, recommended for production
- **Pro Plan**: Best performance, multiple instances

For more information, visit: https://render.com/docs

