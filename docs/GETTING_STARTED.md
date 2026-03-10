# Getting Started — What You Need Before Building

This checklist is for Travis (non-developer). Claude Code will handle all the actual coding, but you need these accounts and tools set up first.

## Accounts to Create

### 1. Twilio (SMS Platform)
- Go to twilio.com and create a paid account (not free trial — A2P requires paid)
- Budget: ~$20/month to start + per-message costs (~$0.0079/segment + carrier surcharges)
- You'll need: Account SID, Auth Token, a 10DLC phone number, and a Messaging Service
- Claude Code can walk you through the Twilio console setup

### 2. Anthropic (AI Engine)
- Go to console.anthropic.com and create an API account
- Add a payment method and set a usage limit (start with $20/month)
- Generate an API key — you'll paste this into your .env file
- This powers the coaching engine that generates responses to worker texts

### 3. GitHub (Code Storage)
- Go to github.com and create a free account (if you don't have one)
- Claude Code will initialize the git repository and push code here
- This is your backup and version control

### 4. Railway or Render (Hosting)
- Railway (railway.app) or Render (render.com) — both have free tiers to start
- This is where your website and backend will live on the internet
- Claude Code will handle deployment configuration

### 5. Domain Registration
- Register safetyasacontact.com (and textsafe.co if budget allows)
- Namecheap, Google Domains, or Cloudflare Registrar all work
- Point DNS to your hosting provider (Claude Code will guide you)

## Software to Install on Your Computer

### Required
- **Claude Code**: Your AI developer — install from claude.com/claude-code
- **Git**: Version control — Claude Code needs this. Download from git-scm.com
- **Node.js** (v18+): For the frontend. Download from nodejs.org
- **Python** (3.11+): For the backend. Download from python.org
- **PostgreSQL**: The database. Download from postgresql.org

### Optional but Helpful
- **VS Code**: Code editor with Claude Code extension. Download from code.visualstudio.com
- **Postman**: For testing API endpoints. Download from postman.com

## First Claude Code Session

When you open Claude Code in the project directory for the first time:

1. It will read CLAUDE.md automatically
2. Tell it: "Read the development plan and start Phase 1"
3. It will walk you through everything step by step
4. If it asks for environment variables, copy .env.example to .env and fill in your keys

## Budget Estimate (Month 1)

| Item | Cost |
|------|------|
| Twilio account + 10DLC number | ~$22/month |
| Twilio A2P registration fee | $15 one-time |
| Anthropic API (development usage) | ~$10-20/month |
| Railway hosting (Starter) | $5/month |
| Domain (safetyasacontact.com) | ~$12/year |
| **Total Month 1** | **~$55-75** |

## Important Notes

- Never share your API keys or .env file with anyone
- The .env file is gitignored — it stays on your machine only
- If Claude Code asks to install something, say yes — it knows what it needs
- Save this project folder somewhere safe and back it up regularly
- When in doubt, ask Claude Code to explain what it's doing
