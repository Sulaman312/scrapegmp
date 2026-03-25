# Deployment Guide for Koyeb

This guide will help you deploy the Google Maps Scraper application as a single service on Koyeb.

## Prerequisites

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
