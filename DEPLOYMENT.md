# Deployment Guide

This guide will help you deploy the Google Maps Scraper application with wildcard domain support.

## Platform Recommendations

- **Render.com** (Recommended) - Native wildcard domain support, easy setup
- **Koyeb** (Alternative) - Good for basic deployments without wildcard domains

---

## Deploying to Render (Recommended for Wildcard Domains)

Render supports wildcard domains natively, making it perfect for this application where:
- Admin panel is at `admin.yourdomain.com`
- Business websites are at `businessname.yourdomain.com`

### Prerequisites for Render

1. A Render account (sign up at https://render.com)
2. GitHub account (to push your code)
3. OpenAI API key
4. A custom domain (e.g., yourdomain.com)

### Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Add wildcard domain support for Render"
git push origin main
```

### Step 2: Create Web Service on Render

1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `gmp-admin` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Environment**: `Docker`
   - **Instance Type**: Start with "Starter" ($7/month), upgrade if needed

### Step 3: Configure Environment Variables

Add these environment variables in Render:

```
OPENAI_API_KEY=your-openai-api-key
PORT=5051
BASE_DOMAIN=yourdomain.com
USE_HTTPS=true
SECRET_KEY=your-secret-key-here

# Email configuration (for contact forms)
CONTACT_TO_EMAIL=your-email@domain.com
CONTACT_FROM_EMAIL=noreply@yourdomain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-app-password
```

**Important**: Generate a strong `SECRET_KEY`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 4: Configure Custom Domain with Wildcard Support

1. In Render Dashboard, go to your web service
2. Click "Settings" → "Custom Domain"
3. Add your domains:
   - `admin.yourdomain.com` (for admin panel)
   - `*.yourdomain.com` (wildcard for business sites)

### Step 5: Configure DNS Records

In your domain registrar's DNS settings, add these records:

```
Type    Name    Value                           TTL
------------------------------------------------------
CNAME   admin   your-app.onrender.com           3600
CNAME   *       your-app.onrender.com           3600
```

**Note**: Replace `your-app` with your actual Render service name.

### Step 6: Deploy

1. Click "Manual Deploy" → "Deploy latest commit"
2. Wait for build to complete (5-10 minutes for first deploy)
3. Render will automatically provision SSL certificates for your wildcard domain

### Step 7: Verify Deployment

1. Visit `https://admin.yourdomain.com` - should show admin panel login
2. After adding a business, visit `https://businessname.yourdomain.com` - should show the business website

### Important Notes for Render

**Persistent Storage**:
- Render's free tier doesn't include persistent storage
- For production, use Render's paid plan with persistent disk ($0.25/GB/month)
- Or integrate with external storage (S3, Cloudflare R2, etc.)

**Performance**:
- Starter instance ($7/month) is sufficient for light usage
- Upgrade to Standard ($25/month) or Pro ($85/month) for heavy scraping

**Build Time**:
- First build takes 5-10 minutes (Playwright installation)
- Subsequent builds are faster due to Docker layer caching

**Auto-Deploy**:
- Render auto-deploys on every git push to main branch
- You can disable this in Settings if preferred

---

## Deploying to Koyeb (Legacy/Fallback)

**Note**: Koyeb deployment uses the old `/site/businessname` URL structure instead of wildcard subdomains.

### Prerequisites

1. A Koyeb account (sign up at https://koyeb.com)
2. GitHub account (to push your code)
3. OpenAI API key

## Deployment Steps

### Option 1: Deploy via GitHub (Recommended)

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Create a new service on Koyeb**
   - Go to https://app.koyeb.com
   - Click "Create Service"
   - Select "GitHub" as the deployment method
   - Connect your GitHub repository
   - Select the repository containing this code

3. **Configure the service**
   - **Builder**: Docker
   - **Dockerfile path**: `Dockerfile`
   - **Port**: 5051
   - **Instance type**: Nano or Small (depending on your needs)

4. **Set environment variables**
   Add the following environment variable:
   - `OPENAI_API_KEY`: Your OpenAI API key

   *Note: The API key is already hardcoded in the code as a fallback, but it's better to use environment variables for security.*

5. **Deploy**
   - Click "Deploy"
   - Wait for the build to complete (this may take 5-10 minutes due to Playwright installation)

### Option 2: Deploy via Docker Hub

1. **Build and push Docker image**
   ```bash
   docker build -t your-dockerhub-username/gmp-scraper:latest .
   docker push your-dockerhub-username/gmp-scraper:latest
   ```

2. **Create service on Koyeb**
   - Select "Docker" as deployment method
   - Enter your Docker image: `your-dockerhub-username/gmp-scraper:latest`
   - Set port to 5051
   - Add environment variables

## Important Notes

### Browser Automation on Koyeb

The scraper uses Playwright with Chromium in headless mode. Koyeb's Docker container supports this, but:

1. **Performance**: Scraping is resource-intensive. Consider using a Small or Medium instance.
2. **Timeouts**: Large scraping jobs may timeout. The default timeout is set appropriately in the code.
3. **Headless mode**: The scraper runs in headless mode in production (non-Windows environments).

### Data Persistence

Koyeb instances are ephemeral, meaning scraped data will be lost on restart. For production:

1. **Option A**: Use Koyeb's persistent storage (if available)
2. **Option B**: Integrate with S3-compatible storage (recommended)
3. **Option C**: Use a database to store business data

To add S3 persistence, you would need to modify the storage code to upload to S3 instead of local disk.

### Environment Variables

Recommended environment variables for production:

- `OPENAI_API_KEY`: Your OpenAI API key
- `PORT`: Port number (default: 5051, Koyeb will set this automatically)
- `FLASK_ENV`: Set to `production`

## Testing Locally with Docker

Before deploying, test the Docker image locally:

```bash
# Build the image
docker build -t gmp-scraper .

# Run the container
docker run -p 5051:5051 \
  -e OPENAI_API_KEY=your-api-key \
  gmp-scraper

# Access the app at http://localhost:5051
```

## Usage After Deployment

1. Navigate to your Koyeb service URL
2. Click the dropdown in the header
3. Click "+ Add Business" at the bottom of the dropdown
4. Enter a Google Maps URL (e.g., `https://www.google.com/maps/place/YourBusiness/...`)
5. Wait for scraping and AI enrichment to complete (may take 1-3 minutes)
6. Edit the business details in the admin panel
7. Click "Generate Website" to create the final site
8. Click "Open Site" to view the published website

## Troubleshooting

### Build fails
- Check that all dependencies are in `requirements.txt`
- Ensure Dockerfile is in the root directory

### Scraper times out
- Increase instance size
- Check that the Google Maps URL is valid
- Ensure Chromium installed correctly (check build logs)

### OpenAI enrichment fails
- Verify your API key is valid
- Check OpenAI account has credits
- Review application logs in Koyeb dashboard

### Data not persisting
- Koyeb instances are stateless
- Implement S3 storage for production
- Or use Koyeb's persistent volumes if available

## Cost Estimation

- **Nano instance**: ~$5/month (suitable for testing)
- **Small instance**: ~$10/month (recommended for light usage)
- **Medium instance**: ~$20/month (for heavy scraping workloads)

Plus OpenAI API costs (gpt-4o-mini is very affordable, ~$0.01 per enrichment)

## Support

For issues or questions, check the application logs in the Koyeb dashboard.
