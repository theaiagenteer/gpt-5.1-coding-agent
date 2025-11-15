# GPT-5.1 Coding Agent Template

<div align="center">

**Deploy your own AI coding agent in just a few clicks!**

[🚀 Deploy on Agencii.ai](https://agencii.ai)

_Production-ready coding agent powered by GPT-5.1 with OpenAI's new Apply Patch and Shell tools_

</div>

---

## 🎯 Overview

This is a ready-to-use template for building your own AI coding agent similar to Lovable, Codex, or Cursor. Built on GPT-5.1, this agent leverages OpenAI's newly released developer tools to write code, execute commands, generate images, and build complete applications autonomously.

**What makes this special?** OpenAI fine-tuned GPT-5.1 specifically for these tools, making it significantly more capable at coding tasks than previous models. This is the same technology powering Codex CLI.

---

## ✨ What's Included

- **GPT-5.1 Coding Agent** with adaptive reasoning and conversational output
- **OpenAI's Apply Patch Tool** for precise code modifications
- **Shell Execution Tool** for running commands and testing code
- **Image Generation Tool** for creating web assets and graphics
- **Web Search Tool** for finding documentation and solutions
- **Plan Management** for complex multi-step tasks
- **Production-ready deployment** configuration for Agencii.ai

---

## 🚀 Quick Start (Local)

### Prerequisites

- Python 3.10+
- OpenAI API key with GPT-5.1 access

### Setup

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd gpt-5.1-coding-agent
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   cp .env.template .env
   ```

   Add your OpenAI API key to `.env`:

   ```
   OPENAI_API_KEY=your_key_here
   ```

5. **Run the agent**

   ```bash
   python agency.py
   ```

6. **Test it out!**
   Try prompts like:
   - "Build a simple snake game"
   - "Create a portfolio website with Next.js"
   - "Build a to-do app with React and Tailwind"

---

## ☁️ Deploy on Agencii.ai (Production)

### Step 1: Prepare Your Repository

1. Commit your changes to GitHub:
   ```bash
   git add .
   git commit -m "Initial setup"
   git push origin main
   ```

### Step 2: Deploy to Agencii.ai

1. Go to [Agencii.ai](https://agencii.ai)
2. Click **"New Agency"**
3. Select your GitHub repository
4. Click on the repository name to deploy

### Step 3: Enable Persistent Storage ⚠️

**IMPORTANT:** For this coding agent to work properly, you must enable persistent storage:

1. Go to your agency settings on Agencii.ai
2. Navigate to the **"Advanced"** tab
3. Enable **"Persistent Storage"**

This ensures that files created by your agent (code, websites, applications) are saved and accessible between sessions.

### Step 4: Deploy as Web App or Custom GPT

1. Select your deployed agency
2. Go to **"Appearance"** settings
3. Click **"Deploy"**
4. Share your custom coding agent with others!

### 🎉 Coming Soon

**Better support for coding agents on the Agencii.ai platform is launching next week!** This includes:

- Enhanced event handling for real-time code execution
- Improved file persistence and workspace management
- Better debugging and logging capabilities
- Optimized streaming for tool outputs

---

## 🛠️ Customization Guide

### Modify Agent Instructions

Edit `coding_agent/instructions.md` to customize your agent's behavior:

```markdown
# Your Custom Instructions

You are a [your specialty] coding agent...

## Your Custom Workflow

1. Step one...
2. Step two...
```

You can base your instructions on system prompts from popular AI coding tools:

- [Codex CLI](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Emergent) - OpenAI's official coding agent (this template already uses these instructions)
- [Cursor](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Cursor%20Prompts) - IDE integration focused
- [Lovable](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Lovable) - Web development focused
- [Windsurf](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Windsurf) - Cascade AI flow
- [Replit](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Replit) - Cloud development focused
- [v0](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/v0%20Prompts%20and%20Tools) - Vercel's UI generation agent
- [Devin](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools/tree/main/Devin%20AI) - Autonomous software engineer
- [Browse all system prompts](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools) - 30,000+ lines of AI tool prompts

### Add Custom Tools

Tell cursor / claude code:

```
Create a new tool that [describe the tool actions and requirements] for the coding agent.
```

---

## 📖 Example Use Cases

### Build a Complete Web Application

```
"Create a modern portfolio website with Next.js and Tailwind CSS.
Include a hero section, projects grid, about section, and contact form.
Generate appropriate images for the design."
```

### Create a Game

```
"Build a snake game in JavaScript with HTML5 canvas.
Include score tracking, speed increases, and game over screen."
```

### Refactor Existing Code

```
"Refactor the authentication module to use JWT tokens instead of sessions.
Update all related endpoints and add proper error handling."
```

### Debug and Fix Issues

```
"The checkout flow is broken. Debug the issue, fix it, and add tests
to prevent similar bugs in the future."
```

---

## 🏗️ Architecture

```
├── coding_agent/
│   ├── coding_agent.py          # Agent configuration
│   ├── instructions.md          # Agent system prompt (customizable)
│   └── tools/
│       ├── apply_patch.py       # OpenAI's apply_patch tool
│       ├── shell.py             # Command execution tool
│       ├── OpenAIImageGenerationTool.py
│       └── UpdatePlan.py        # Plan management
├── agency.py                    # Agency setup and entry point
├── shared_instructions.md       # Shared context for all agents
└── requirements.txt             # Python dependencies
```

---

## 🤝 Contributing

This template is open source and contributions are welcome! Feel free to:

- Add new tools
- Improve instructions
- Share your custom configurations
- Report issues or bugs

---

## 📺 Video Tutorial

Watch the full video tutorial on YouTube to see this agent in action and learn how to customize it for your needs.

---

## 📝 License

MIT License - feel free to use this template for your own projects!

---

## 🔗 Links

- [Agencii.ai Platform](https://agencii.ai) - Deploy your agent in production
- [Agency Swarm Documentation](https://agency-swarm.ai) - Framework documentation
- [Join the Community](https://skool.com/agency-ai) - School community for workshops and support

---

<div align="center">

**Built with ❤️ using Agency Swarm and GPT-5.1**

</div>
