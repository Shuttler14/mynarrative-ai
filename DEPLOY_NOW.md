# 🚀 Deploy Virtual Try-On Fix

## What Was Fixed
- Updated IDM-VTON model version (removed outdated hash)
- Now using `cuuupid/idm-vton` which auto-fetches latest version

## Deploy to Vercel (2 minutes)

### Option 1: Vercel CLI (Fastest)
```bash
cd mynarrative-ai
vercel --prod
```

### Option 2: Vercel Dashboard
1. Go to https://vercel.com/dashboard
2. Find your `mynarrative-ai` project
3. Click "Deployments" tab
4. Click "Redeploy" on the latest deployment
5. Wait ~30 seconds for build to complete

### Option 3: Git Push (if connected to GitHub)
```bash
cd mynarrative-ai
git add api/virtual_try_on.py
git commit -m "Fix: Update IDM-VTON to latest version"
git push origin main
```
Vercel will auto-deploy.

## Verify Environment Variables

Before testing, make sure your Replicate API token is set:

1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Check that `REPLICATE_API_TOKEN` exists
3. If missing, add it:
   - Name: `REPLICATE_API_TOKEN`
   - Value: Your token from https://replicate.com/account/api-tokens
   - Environment: Production, Preview, Development (select all)

## Test After Deployment

### Quick Test (Browser Console)
```javascript
fetch('https://mynarrative-ai.vercel.app/api/virtual_try_on', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    mode: 'vton',
    user_image: 'https://replicate.delivery/pbxt/K9XuQE29RrLQFJQu6uGqZLqIvgPh9TjOFqiGqtFMBIGVLT0C/out.png',
    garment_image: 'https://replicate.delivery/pbxt/K9XuQE29RrLQFJQu6uGqZLqIvgPh9TjOFqiGqtFMBIGVLT0C/out.png',
    category: 'upper_body'
  })
})
.then(r => r.json())
.then(console.log)
```

### Full Test (Your Shopify Store)
1. Go to any product page
2. Click "Virtual Try-On" button
3. Upload a photo
4. Should work within 20-30 seconds

## Expected Results

✅ **Success Response:**
```json
{
  "success": true,
  "image": "https://replicate.delivery/pbxt/..."
}
```

❌ **If Still Failing:**
See `VTON_FIX_GUIDE.md` for alternative models and debugging steps.

## Monitor Logs
```bash
vercel logs --prod
```

## Rollback (if needed)
```bash
vercel rollback
```
