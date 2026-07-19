# AI Tools Pricing

> AI Tools Pricing Comparison and Money Saving

## Deployment

- **Production URL**: https://ai-pricing-9sf.pages.dev/
- **GitHub Repo**: https://github.com/wangdan197902-art/ai-pricing
- **Cloudflare Project**: ai-pricing

## Local Development

```bash
# Install Hugo (macOS)
brew install hugo

# Run dev server
hugo server -D

# Build for production
hugo --minify --baseURL "https://ai-pricing-9sf.pages.dev/"
```

## Auto Deploy

Push to `main` branch → GitHub Actions auto-deploys to Cloudflare Pages.

## Project Structure

```
├── content/           # Markdown content
├── layouts/           # Hugo templates
├── static/            # Static assets (images, CSS)
├── data/              # JSON data files
├── hugo.toml          # Hugo config
├── wrangler.toml      # Cloudflare Pages config
└── .github/workflows/ # CI/CD
```
