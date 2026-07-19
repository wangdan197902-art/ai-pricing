"""AI 工具主数据集（1000+ 工具）。

- 50+ AI 工具分类
- Top 50+ 真实工具（手工录入）
- 其余 950+ 工具通过程序化模板生成（每分类 20 个）
- 输出 data/ai_tools.json
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "ai_tools.json"

# 50+ 个 AI 工具分类
CATEGORIES: list[str] = [
    "chatbots", "code", "image", "video", "audio", "writing", "data", "research",
    "design", "marketing", "sales", "hr", "legal", "finance", "education",
    "healthcare", "productivity", "translation", "transcription", "summarization",
    "search", "analytics", "crm", "devops", "security", "testing", "monitoring",
    "database", "cloud", "ml-platform", "training", "inference", "fine-tuning",
    "dataset", "labeling", "visualization", "3d", "gaming", "robotics", "iot",
    "blockchain", "crypto", "metaverse", "ar", "vr", "voice", "speech",
    "avatar", "presentation", "automation",
]
assert len(CATEGORIES) >= 50, f"分类数不足 50: {len(CATEGORIES)}"

# 每分类下生成的工具数（程序化生成）
TOOLS_PER_CATEGORY = 20

# 各分类的英文复数名称（用于程序化生成工具名）
CATEGORY_LABELS: dict[str, str] = {
    "chatbots": "AI Chatbot", "code": "Code Assistant", "image": "Image Generator",
    "video": "Video Generator", "audio": "Audio Tool", "writing": "Writing Assistant",
    "data": "Data Tool", "research": "Research Assistant", "design": "Design Tool",
    "marketing": "Marketing Tool", "sales": "Sales Tool", "hr": "HR Tool",
    "legal": "Legal Tool", "finance": "Finance Tool", "education": "Education Tool",
    "healthcare": "Healthcare Tool", "productivity": "Productivity Tool",
    "translation": "Translation Tool", "transcription": "Transcription Tool",
    "summarization": "Summarization Tool", "search": "Search Tool",
    "analytics": "Analytics Tool", "crm": "CRM Tool", "devops": "DevOps Tool",
    "security": "Security Tool", "testing": "Testing Tool",
    "monitoring": "Monitoring Tool", "database": "Database Tool",
    "cloud": "Cloud Tool", "ml-platform": "ML Platform", "training": "Training Tool",
    "inference": "Inference Tool", "fine-tuning": "Fine-tuning Tool",
    "dataset": "Dataset Tool", "labeling": "Labeling Tool",
    "visualization": "Visualization Tool", "3d": "3D Tool", "gaming": "Gaming Tool",
    "robotics": "Robotics Tool", "iot": "IoT Tool", "blockchain": "Blockchain Tool",
    "crypto": "Crypto Tool", "metaverse": "Metaverse Tool", "ar": "AR Tool",
    "vr": "VR Tool", "voice": "Voice Tool", "speech": "Speech Tool",
    "avatar": "Avatar Tool", "presentation": "Presentation Tool",
    "automation": "Automation Tool",
}

# Top 50+ 真实 AI 工具（手工录入）
REAL_TOOLS: list[dict] = [
    {
        "id": "chatgpt-plus", "name": "ChatGPT Plus", "category": "chatbots",
        "vendor": "OpenAI", "url": "https://chat.openai.com/",
        "pricing_model": "subscription", "price_min": 20, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "OpenAI's flagship chatbot with GPT-4, DALL-E, and advanced reasoning. Plus tier unlocks faster response, plugins, and GPTs.",
        "features": ["GPT-4 access", "DALL-E 3 image generation", "Code interpretation", "Web browsing", "Custom GPTs", "File upload"],
        "alternatives": ["claude-pro", "gemini-advanced", "perplexity-pro"],
        "founded_year": 2022, "popularity_score": 99,
    },
    {
        "id": "chatgpt-free", "name": "ChatGPT Free", "category": "chatbots",
        "vendor": "OpenAI", "url": "https://chat.openai.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 0,
        "currency": "USD", "free_tier": True,
        "description_en": "Free tier of ChatGPT with GPT-3.5/4o-mini access. Limited messages per hour and no advanced features.",
        "features": ["GPT-3.5 access", "Limited GPT-4o-mini", "Basic chat"],
        "alternatives": ["claude-free", "gemini-free"],
        "founded_year": 2022, "popularity_score": 100,
    },
    {
        "id": "chatgpt-team", "name": "ChatGPT Team", "category": "chatbots",
        "vendor": "OpenAI", "url": "https://chat.openai.com/team",
        "pricing_model": "subscription", "price_min": 25, "price_max": 30,
        "currency": "USD", "free_tier": False,
        "description_en": "Team plan for collaborative use with shared workspace, higher message limits, and admin controls.",
        "features": ["Higher message limits", "Shared workspace", "Admin console", "GPT-4 access", "Custom GPTs sharing"],
        "alternatives": ["chatgpt-plus", "chatgpt-enterprise"],
        "founded_year": 2023, "popularity_score": 88,
    },
    {
        "id": "chatgpt-enterprise", "name": "ChatGPT Enterprise", "category": "chatbots",
        "vendor": "OpenAI", "url": "https://openai.com/enterprise/",
        "pricing_model": "subscription", "price_min": 60, "price_max": 90,
        "currency": "USD", "free_tier": False,
        "description_en": "Enterprise-grade ChatGPT with SOC 2 compliance, SSO, unlimited high-speed GPT-4, and extended context.",
        "features": ["SOC 2 Type 2", "SSO/SAML", "Unlimited GPT-4", "32k context", "Analytics dashboard", "Dedicated support"],
        "alternatives": ["chatgpt-team", "claude-team"],
        "founded_year": 2023, "popularity_score": 85,
    },
    {
        "id": "claude-pro", "name": "Claude Pro", "category": "chatbots",
        "vendor": "Anthropic", "url": "https://claude.ai/",
        "pricing_model": "subscription", "price_min": 20, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "Anthropic's Claude with extended context window (200k tokens), advanced reasoning, and document analysis.",
        "features": ["Claude 3.5 Sonnet", "200k context", "File upload", "Vision", "Artifacts"],
        "alternatives": ["chatgpt-plus", "gemini-advanced"],
        "founded_year": 2023, "popularity_score": 92,
    },
    {
        "id": "claude-free", "name": "Claude Free", "category": "chatbots",
        "vendor": "Anthropic", "url": "https://claude.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 0,
        "currency": "USD", "free_tier": True,
        "description_en": "Free tier of Claude with limited daily messages and access to Claude 3.5 Sonnet.",
        "features": ["Claude 3.5 Sonnet", "Limited daily messages"],
        "alternatives": ["chatgpt-free", "gemini-free"],
        "founded_year": 2023, "popularity_score": 90,
    },
    {
        "id": "claude-team", "name": "Claude Team", "category": "chatbots",
        "vendor": "Anthropic", "url": "https://www.anthropic.com/claude-team",
        "pricing_model": "subscription", "price_min": 30, "price_max": 30,
        "currency": "USD", "free_tier": False,
        "description_en": "Team plan with shared workspace, higher usage limits, admin tools, and collaboration features.",
        "features": ["Higher usage limits", "Shared workspace", "Admin console", "Priority access"],
        "alternatives": ["claude-pro", "chatgpt-team"],
        "founded_year": 2024, "popularity_score": 82,
    },
    {
        "id": "gemini-advanced", "name": "Gemini Advanced", "category": "chatbots",
        "vendor": "Google", "url": "https://gemini.google.com/",
        "pricing_model": "subscription", "price_min": 19.99, "price_max": 19.99,
        "currency": "USD", "free_tier": True,
        "description_en": "Google's Gemini Advanced with Gemini 1.5 Pro, 1M context window, and Google Workspace integration.",
        "features": ["Gemini 1.5 Pro", "1M context", "Google Workspace", "Deep Research", "Image generation"],
        "alternatives": ["chatgpt-plus", "claude-pro"],
        "founded_year": 2023, "popularity_score": 88,
    },
    {
        "id": "gemini-free", "name": "Gemini Free", "category": "chatbots",
        "vendor": "Google", "url": "https://gemini.google.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 0,
        "currency": "USD", "free_tier": True,
        "description_en": "Free tier of Gemini with Gemini Flash, limited context, and basic Google integration.",
        "features": ["Gemini Flash", "Basic chat", "Limited context"],
        "alternatives": ["chatgpt-free", "claude-free"],
        "founded_year": 2023, "popularity_score": 87,
    },
    {
        "id": "midjourney-basic", "name": "Midjourney Basic", "category": "image",
        "vendor": "Midjourney", "url": "https://www.midjourney.com/",
        "pricing_model": "subscription", "price_min": 10, "price_max": 10,
        "currency": "USD", "free_tier": False,
        "description_en": "Basic Midjourney plan with 200 image generations per month and Discord-based access.",
        "features": ["200 images/month", "Discord access", "Commercial use", "4 image quality modes"],
        "alternatives": ["dalle-3", "stable-diffusion", "leonardo-ai"],
        "founded_year": 2022, "popularity_score": 95,
    },
    {
        "id": "midjourney-standard", "name": "Midjourney Standard", "category": "image",
        "vendor": "Midjourney", "url": "https://www.midjourney.com/",
        "pricing_model": "subscription", "price_min": 30, "price_max": 30,
        "currency": "USD", "free_tier": False,
        "description_en": "Standard plan with 15h fast generations and unlimited relaxed generations.",
        "features": ["15h fast GPU", "Unlimited relaxed", "Discord access", "Commercial use"],
        "alternatives": ["midjourney-basic", "midjourney-pro"],
        "founded_year": 2022, "popularity_score": 90,
    },
    {
        "id": "midjourney-pro", "name": "Midjourney Pro", "category": "image",
        "vendor": "Midjourney", "url": "https://www.midjourney.com/",
        "pricing_model": "subscription", "price_min": 60, "price_max": 60,
        "currency": "USD", "free_tier": False,
        "description_en": "Pro plan with 30h fast generations, unlimited relaxed, and stealth mode for private generation.",
        "features": ["30h fast GPU", "Unlimited relaxed", "Stealth mode", "Commercial use"],
        "alternatives": ["midjourney-standard", "midjourney-mega"],
        "founded_year": 2022, "popularity_score": 86,
    },
    {
        "id": "midjourney-mega", "name": "Midjourney Mega", "category": "image",
        "vendor": "Midjourney", "url": "https://www.midjourney.com/",
        "pricing_model": "subscription", "price_min": 120, "price_max": 120,
        "currency": "USD", "free_tier": False,
        "description_en": "Mega plan with 60h fast generations, unlimited relaxed, and stealth mode. Best for power users.",
        "features": ["60h fast GPU", "Unlimited relaxed", "Stealth mode", "Commercial use"],
        "alternatives": ["midjourney-pro"],
        "founded_year": 2023, "popularity_score": 80,
    },
    {
        "id": "github-copilot-individual", "name": "GitHub Copilot Individual", "category": "code",
        "vendor": "GitHub", "url": "https://github.com/features/copilot",
        "pricing_model": "subscription", "price_min": 10, "price_max": 10,
        "currency": "USD", "free_tier": False,
        "description_en": "AI pair programmer integrated with VS Code, JetBrains, and Neovim. Code completion and chat.",
        "features": ["Code completion", "Copilot Chat", "Multi-IDE support", "2000 snippet completions/month"],
        "alternatives": ["cursor", "codeium", "tabnine"],
        "founded_year": 2021, "popularity_score": 95,
    },
    {
        "id": "github-copilot-business", "name": "GitHub Copilot Business", "category": "code",
        "vendor": "GitHub", "url": "https://github.com/features/copilot",
        "pricing_model": "subscription", "price_min": 19, "price_max": 19,
        "currency": "USD", "free_tier": False,
        "description_en": "Business plan with organization-level policy, IP indemnity, and corporate billing.",
        "features": ["All Individual features", "Org policy", "IP indemnity", "Corporate billing"],
        "alternatives": ["github-copilot-individual", "github-copilot-enterprise"],
        "founded_year": 2022, "popularity_score": 90,
    },
    {
        "id": "github-copilot-enterprise", "name": "GitHub Copilot Enterprise", "category": "code",
        "vendor": "GitHub", "url": "https://github.com/features/copilot",
        "pricing_model": "subscription", "price_min": 39, "price_max": 39,
        "currency": "USD", "free_tier": False,
        "description_en": "Enterprise plan with custom models, knowledge bases, and integration with GitHub Enterprise.",
        "features": ["Custom models", "Knowledge bases", "GitHub Enterprise integration", "Audit logs"],
        "alternatives": ["github-copilot-business"],
        "founded_year": 2023, "popularity_score": 85,
    },
    {
        "id": "notion-ai", "name": "Notion AI", "category": "productivity",
        "vendor": "Notion", "url": "https://www.notion.so/product/ai",
        "pricing_model": "subscription", "price_min": 10, "price_max": 10,
        "currency": "USD", "free_tier": False,
        "description_en": "AI assistant integrated with Notion workspace for writing, summarizing, and Q&A.",
        "features": ["AI writing", "Summarization", "Q&A", "Translation", "Table autofill"],
        "alternatives": ["coda-ai", "airtable-ai"],
        "founded_year": 2023, "popularity_score": 88,
    },
    {
        "id": "jasper", "name": "Jasper", "category": "writing",
        "vendor": "Jasper AI", "url": "https://www.jasper.ai/",
        "pricing_model": "subscription", "price_min": 39, "price_max": 69,
        "currency": "USD", "free_tier": False,
        "description_en": "Marketing-focused AI writing assistant with brand voice, templates, and team collaboration.",
        "features": ["Brand voice", "Marketing templates", "Team collaboration", "Browser extension"],
        "alternatives": ["copy-ai", "wordtune"],
        "founded_year": 2021, "popularity_score": 82,
    },
    {
        "id": "copy-ai", "name": "Copy.ai", "category": "writing",
        "vendor": "Copy.ai", "url": "https://www.copy.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 49,
        "currency": "USD", "free_tier": True,
        "description_en": "AI copywriting tool for marketing content with templates and workflows.",
        "features": ["2000 words/month free", "Marketing templates", "Brand voice", "Workflow automation"],
        "alternatives": ["jasper", "wordtune"],
        "founded_year": 2020, "popularity_score": 78,
    },
    {
        "id": "perplexity-pro", "name": "Perplexity Pro", "category": "search",
        "vendor": "Perplexity AI", "url": "https://www.perplexity.ai/",
        "pricing_model": "subscription", "price_min": 20, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "AI-powered search engine with cited answers, Pro search, and model choice (GPT-4, Claude, etc.).",
        "features": ["Pro search", "Model choice", "Image generation", "File upload", "API access"],
        "alternatives": ["chatgpt-plus", "gemini-advanced"],
        "founded_year": 2022, "popularity_score": 85,
    },
    {
        "id": "elevenlabs", "name": "ElevenLabs", "category": "audio",
        "vendor": "ElevenLabs", "url": "https://elevenlabs.io/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 99,
        "currency": "USD", "free_tier": True,
        "description_en": "AI voice generation and text-to-speech with realistic voices, voice cloning, and dubbing.",
        "features": ["10k chars/month free", "Voice cloning", "29 languages", "Sound effects", "API"],
        "alternatives": ["suno", "udio"],
        "founded_year": 2022, "popularity_score": 90,
    },
    {
        "id": "synthesia", "name": "Synthesia", "category": "video",
        "vendor": "Synthesia", "url": "https://www.synthesia.io/",
        "pricing_model": "subscription", "price_min": 22, "price_max": 89,
        "currency": "USD", "free_tier": False,
        "description_en": "AI video generation with avatars, voiceover, and multi-language support for marketing videos.",
        "features": ["140+ AI avatars", "120+ languages", "Custom avatars", "Templates", "Team collaboration"],
        "alternatives": ["runway", "pika"],
        "founded_year": 2017, "popularity_score": 85,
    },
    {
        "id": "runway", "name": "Runway", "category": "video",
        "vendor": "Runway ML", "url": "https://runwayml.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 95,
        "currency": "USD", "free_tier": True,
        "description_en": "AI video generation and editing with Gen-3 Alpha, motion brush, and video-to-video.",
        "features": ["Gen-3 Alpha", "125 credits free", "Motion brush", "Video-to-video", "Director mode"],
        "alternatives": ["synthesia", "pika"],
        "founded_year": 2018, "popularity_score": 88,
    },
    {
        "id": "pika", "name": "Pika", "category": "video",
        "vendor": "Pika Labs", "url": "https://pika.art/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 58,
        "currency": "USD", "free_tier": True,
        "description_en": "AI video generation with text-to-video, image-to-video, and Pikaffects (effects).",
        "features": ["30 initial credits", "Text-to-video", "Image-to-video", "Pikaffects", "Lipsync"],
        "alternatives": ["runway", "synthesia"],
        "founded_year": 2023, "popularity_score": 80,
    },
    {
        "id": "suno", "name": "Suno", "category": "audio",
        "vendor": "Suno", "url": "https://suno.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 24,
        "currency": "USD", "free_tier": True,
        "description_en": "AI music generation with full songs, lyrics, and various genres.",
        "features": ["50 credits/day free", "Full song generation", "Custom lyrics", "Multiple genres"],
        "alternatives": ["udio", "elevenlabs"],
        "founded_year": 2023, "popularity_score": 85,
    },
    {
        "id": "udio", "name": "Udio", "category": "audio",
        "vendor": "Udio", "url": "https://www.udio.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "AI music generation platform with high-quality audio and various styles.",
        "features": ["600 credits/month free", "High-quality audio", "Multiple styles", "Lyrics generation"],
        "alternatives": ["suno", "elevenlabs"],
        "founded_year": 2024, "popularity_score": 75,
    },
    {
        "id": "descript", "name": "Descript", "category": "audio",
        "vendor": "Descript", "url": "https://www.descript.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 24,
        "currency": "USD", "free_tier": True,
        "description_en": "Audio/video editing with transcript-based editing, voice cloning, and Overdub.",
        "features": ["1 hour transcription free", "Transcript editing", "Overdub voice cloning", "Screen recording"],
        "alternatives": ["otter-ai", "fireflies"],
        "founded_year": 2017, "popularity_score": 82,
    },
    {
        "id": "otter-ai", "name": "Otter.ai", "category": "transcription",
        "vendor": "Otter.ai", "url": "https://otter.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "AI meeting assistant with transcription, summary, and action items in real-time.",
        "features": ["300 min/month free", "Real-time transcription", "Speaker identification", "Meeting summary"],
        "alternatives": ["fireflies", "descript"],
        "founded_year": 2016, "popularity_score": 85,
    },
    {
        "id": "deepl", "name": "DeepL", "category": "translation",
        "vendor": "DeepL", "url": "https://www.deepl.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 25,
        "currency": "USD", "free_tier": True,
        "description_en": "High-quality AI translation with DeepL Pro for unlimited text and document translation.",
        "features": ["Free web translator", "30+ languages", "Document translation", "Glossary", "API"],
        "alternatives": ["google-translate", "chatgpt-plus"],
        "founded_year": 2017, "popularity_score": 90,
    },
    {
        "id": "grammarly", "name": "Grammarly", "category": "writing",
        "vendor": "Grammarly", "url": "https://www.grammarly.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "AI writing assistant for grammar, style, tone, and clarity across browsers and apps.",
        "features": ["Free grammar check", "Tone detection", "Plagiarism check", "Browser extension", "AI writing"],
        "alternatives": ["quillbot", "wordtune"],
        "founded_year": 2009, "popularity_score": 92,
    },
    {
        "id": "quillbot", "name": "Quillbot", "category": "writing",
        "vendor": "Quillbot", "url": "https://quillbot.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "AI paraphrasing and writing tool with summarizer, grammar checker, and citation generator.",
        "features": ["Paraphraser", "Summarizer", "Grammar checker", "Citation generator", "Browser extension"],
        "alternatives": ["grammarly", "wordtune"],
        "founded_year": 2017, "popularity_score": 85,
    },
    {
        "id": "wordtune", "name": "Wordtune", "category": "writing",
        "vendor": "AI21 Labs", "url": "https://www.wordtune.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 25,
        "currency": "USD", "free_tier": True,
        "description_en": "AI writing assistant for rewriting, summarizing, and expanding text in various tones.",
        "features": ["10 rewrites/day free", "Tone options", "Summarizer", "Browser extension"],
        "alternatives": ["grammarly", "quillbot"],
        "founded_year": 2020, "popularity_score": 78,
    },
    {
        "id": "dalle-3", "name": "DALL-E 3", "category": "image",
        "vendor": "OpenAI", "url": "https://openai.com/dall-e-3/",
        "pricing_model": "pay-per-use", "price_min": 0.04, "price_max": 0.12,
        "currency": "USD", "free_tier": True,
        "description_en": "OpenAI's image generation model with prompt adherence and text rendering. Available via ChatGPT or API.",
        "features": ["Available in ChatGPT", "API access", "Text rendering", "Various sizes"],
        "alternatives": ["midjourney-basic", "stable-diffusion"],
        "founded_year": 2023, "popularity_score": 90,
    },
    {
        "id": "stable-diffusion", "name": "Stable Diffusion", "category": "image",
        "vendor": "Stability AI", "url": "https://stability.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "Open-source image generation model with various checkpoints and ControlNet support.",
        "features": ["Open source", "Self-hostable", "ControlNet", "LoRA support", "Multiple checkpoints"],
        "alternatives": ["midjourney-basic", "dalle-3", "leonardo-ai"],
        "founded_year": 2022, "popularity_score": 92,
    },
    {
        "id": "leonardo-ai", "name": "Leonardo AI", "category": "image",
        "vendor": "Leonardo.AI", "url": "https://leonardo.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 48,
        "currency": "USD", "free_tier": True,
        "description_en": "AI image generation with custom models, Canvas editor, and various fine-tuned checkpoints.",
        "features": ["150 daily tokens free", "Custom models", "Canvas editor", "Real-time canvas", "Image guidance"],
        "alternatives": ["midjourney-basic", "stable-diffusion", "ideogram"],
        "founded_year": 2022, "popularity_score": 82,
    },
    {
        "id": "ideogram", "name": "Ideogram", "category": "image",
        "vendor": "Ideogram", "url": "https://ideogram.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 48,
        "currency": "USD", "free_tier": True,
        "description_en": "AI image generation specialized in text rendering and typography in images.",
        "features": ["25 prompts/day free", "Text rendering", "Magic prompt", "Style references"],
        "alternatives": ["midjourney-basic", "dalle-3"],
        "founded_year": 2022, "popularity_score": 75,
    },
    {
        "id": "adobe-firefly", "name": "Adobe Firefly", "category": "image",
        "vendor": "Adobe", "url": "https://www.adobe.com/products/firefly.html",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "Adobe's generative AI for images, text effects, and vector recoloring. Commercially safe.",
        "features": ["25 monthly credits free", "Generative fill", "Text effects", "Commercial use safe"],
        "alternatives": ["midjourney-basic", "dalle-3"],
        "founded_year": 2023, "popularity_score": 80,
    },
    {
        "id": "canva-ai", "name": "Canva AI", "category": "design",
        "vendor": "Canva", "url": "https://www.canva.com/ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 15,
        "currency": "USD", "free_tier": True,
        "description_en": "AI design tools integrated with Canva including Magic Write, Text to Image, and Magic Edit.",
        "features": ["Magic Write", "Text to Image", "Magic Edit", "Magic Eraser", "Magic Design"],
        "alternatives": ["figma-ai", "adobe-firefly"],
        "founded_year": 2023, "popularity_score": 85,
    },
    {
        "id": "figma-ai", "name": "Figma AI", "category": "design",
        "vendor": "Figma", "url": "https://www.figma.com/ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 15,
        "currency": "USD", "free_tier": True,
        "description_en": "AI features in Figma including Make Designs, Visual Search, and AI-powered suggestions.",
        "features": ["Make Designs", "Visual Search", "Rename Layers", "Text tools", "AI suggestions"],
        "alternatives": ["canva-ai", "adobe-firefly"],
        "founded_year": 2024, "popularity_score": 78,
    },
    {
        "id": "vercel-v0", "name": "Vercel v0", "category": "code",
        "vendor": "Vercel", "url": "https://v0.dev/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "AI-powered UI generation with React, Tailwind, and shadcn/ui integration.",
        "features": ["Text-to-UI", "React/Tailwind code", "shadcn/ui", "Live preview", "Vercel deployment"],
        "alternatives": ["cursor", "replit"],
        "founded_year": 2023, "popularity_score": 80,
    },
    {
        "id": "cursor", "name": "Cursor", "category": "code",
        "vendor": "Anysphere", "url": "https://cursor.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 20,
        "currency": "USD", "free_tier": True,
        "description_en": "AI-first code editor with codebase-aware chat, code generation, and tab completion.",
        "features": ["Codebase chat", "Code generation", "Tab completion", "Multi-model", "Privacy mode"],
        "alternatives": ["github-copilot-individual", "vercel-v0"],
        "founded_year": 2023, "popularity_score": 88,
    },
    {
        "id": "replit", "name": "Replit", "category": "code",
        "vendor": "Replit", "url": "https://replit.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 25,
        "currency": "USD", "free_tier": True,
        "description_en": "Cloud IDE with AI Agent for full-stack app development and deployment.",
        "features": ["AI Agent", "Cloud IDE", "Multi-language", "Hosting", "Database"],
        "alternatives": ["cursor", "codeium"],
        "founded_year": 2016, "popularity_score": 82,
    },
    {
        "id": "codeium", "name": "Codeium", "category": "code",
        "vendor": "Codeium", "url": "https://codeium.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 19,
        "currency": "USD", "free_tier": True,
        "description_en": "Free AI code completion with Pro tier for advanced features and unlimited usage.",
        "features": ["Free individual use", "70+ IDEs", "70+ languages", "Context awareness", "Chat"],
        "alternatives": ["github-copilot-individual", "cursor", "tabnine"],
        "founded_year": 2021, "popularity_score": 85,
    },
    {
        "id": "tabnine", "name": "Tabnine", "category": "code",
        "vendor": "Tabnine", "url": "https://www.tabnine.com/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 39,
        "currency": "USD", "free_tier": True,
        "description_en": "AI code completion with privacy-focused approach and self-hosted options.",
        "features": ["Basic completion free", "Privacy focused", "Self-hosted option", "Team learning"],
        "alternatives": ["github-copilot-individual", "codeium"],
        "founded_year": 2017, "popularity_score": 75,
    },
    {
        "id": "amazon-q", "name": "Amazon Q", "category": "productivity",
        "vendor": "AWS", "url": "https://aws.amazon.com/q/",
        "pricing_model": "subscription", "price_min": 20, "price_max": 25,
        "currency": "USD", "free_tier": True,
        "description_en": "AWS AI assistant for business and developer tasks, integrated with AWS services.",
        "features": ["Business assistant", "Code generation", "AWS integration", "Connectors"],
        "alternatives": ["microsoft-copilot", "google-workspace-ai"],
        "founded_year": 2023, "popularity_score": 75,
    },
    {
        "id": "microsoft-copilot", "name": "Microsoft Copilot", "category": "productivity",
        "vendor": "Microsoft", "url": "https://www.microsoft.com/microsoft-copilot",
        "pricing_model": "freemium", "price_min": 0, "price_max": 30,
        "currency": "USD", "free_tier": True,
        "description_en": "AI assistant integrated with Microsoft 365 apps for productivity enhancement.",
        "features": ["Free web version", "M365 integration", "Word/Excel/PowerPoint", "Teams", "Outlook"],
        "alternatives": ["google-workspace-ai", "amazon-q"],
        "founded_year": 2023, "popularity_score": 88,
    },
    {
        "id": "google-workspace-ai", "name": "Google Workspace AI", "category": "productivity",
        "vendor": "Google", "url": "https://workspace.google.com/",
        "pricing_model": "subscription", "price_min": 20, "price_max": 30,
        "currency": "USD", "free_tier": False,
        "description_en": "AI features in Google Workspace including Help me write, organize, and create.",
        "features": ["Help me write", "Gmail/Docs/Sheets", "Image generation", "Meeting notes"],
        "alternatives": ["microsoft-copilot", "notion-ai"],
        "founded_year": 2023, "popularity_score": 85,
    },
    {
        "id": "slack-ai", "name": "Slack AI", "category": "productivity",
        "vendor": "Slack", "url": "https://slack.com/features/ai",
        "pricing_model": "subscription", "price_min": 8, "price_max": 12,
        "currency": "USD", "free_tier": False,
        "description_en": "AI features in Slack including channel summaries, search, and thread recaps.",
        "features": ["Channel summaries", "Thread recaps", "AI search", "Huddle notes"],
        "alternatives": ["zoom-ai", "microsoft-copilot"],
        "founded_year": 2023, "popularity_score": 78,
    },
    {
        "id": "zoom-ai", "name": "Zoom AI", "category": "productivity",
        "vendor": "Zoom", "url": "https://www.zoom.com/en/ai-assistant/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 12,
        "currency": "USD", "free_tier": True,
        "description_en": "AI assistant in Zoom for meeting summaries, action items, and chat composition.",
        "features": ["Meeting summary", "Action items", "Chat compose", "Whiteboard content"],
        "alternatives": ["otter-ai", "fireflies"],
        "founded_year": 2023, "popularity_score": 80,
    },
    {
        "id": "fireflies", "name": "Fireflies", "category": "transcription",
        "vendor": "Fireflies.ai", "url": "https://fireflies.ai/",
        "pricing_model": "freemium", "price_min": 0, "price_max": 19,
        "currency": "USD", "free_tier": True,
        "description_en": "AI meeting assistant with transcription, summary, and search across meetings.",
        "features": ["800 min storage free", "Transcription", "AI search", "Collaboration", "Integrations"],
        "alternatives": ["otter-ai", "descript"],
        "founded_year": 2016, "popularity_score": 82,
    },
    {
        "id": "coda-ai", "name": "Coda AI", "category": "productivity",
        "vendor": "Coda", "url": "https://coda.io/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 36,
        "currency": "USD", "free_tier": True,
        "description_en": "AI assistant in Coda docs for content generation, summaries, and automation.",
        "features": ["AI blocks", "Content generation", "Summaries", "Formulas", "Automation"],
        "alternatives": ["notion-ai", "airtable-ai"],
        "founded_year": 2023, "popularity_score": 72,
    },
    {
        "id": "airtable-ai", "name": "Airtable AI", "category": "productivity",
        "vendor": "Airtable", "url": "https://www.airtable.com/product/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 24,
        "currency": "USD", "free_tier": True,
        "description_en": "AI features in Airtable for content generation, summarization, and categorization.",
        "features": ["AI fields", "Content generation", "Summarization", "Categorization", "Translation"],
        "alternatives": ["notion-ai", "coda-ai"],
        "founded_year": 2023, "popularity_score": 75,
    },
    {
        "id": "clickup-ai", "name": "ClickUp AI", "category": "productivity",
        "vendor": "ClickUp", "url": "https://clickup.com/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 19,
        "currency": "USD", "free_tier": True,
        "description_en": "AI assistant in ClickUp for task management, summaries, and content creation.",
        "features": ["AI writer", "Task summaries", "Subtask generation", "Project updates"],
        "alternatives": ["monday-ai", "asana-ai"],
        "founded_year": 2023, "popularity_score": 78,
    },
    {
        "id": "monday-ai", "name": "Monday AI", "category": "productivity",
        "vendor": "monday.com", "url": "https://monday.com/ai",
        "pricing_model": "subscription", "price_min": 9, "price_max": 19,
        "currency": "USD", "free_tier": False,
        "description_en": "AI features in monday.com for task automation, summaries, and code generation.",
        "features": ["AI blocks", "Task automation", "Summaries", "Code generation"],
        "alternatives": ["clickup-ai", "asana-ai"],
        "founded_year": 2023, "popularity_score": 70,
    },
    {
        "id": "asana-ai", "name": "Asana AI", "category": "productivity",
        "vendor": "Asana", "url": "https://asana.com/product/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 25,
        "currency": "USD", "free_tier": True,
        "description_en": "Smart fields and AI features in Asana for work intelligence and automation.",
        "features": ["Smart fields", "Smart status", "Smart goals", "Smart workflows"],
        "alternatives": ["clickup-ai", "monday-ai"],
        "founded_year": 2023, "popularity_score": 72,
    },
    {
        "id": "trello-ai", "name": "Trello AI", "category": "productivity",
        "vendor": "Atlassian", "url": "https://trello.com/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 17.50,
        "currency": "USD", "free_tier": True,
        "description_en": "AI features in Trello for card summaries, action items, and content generation.",
        "features": ["Card summaries", "Action items", "Content generation", "Atlassian Intelligence"],
        "alternatives": ["clickup-ai", "asana-ai"],
        "founded_year": 2023, "popularity_score": 70,
    },
    {
        "id": "todoist-ai", "name": "Todoist AI", "category": "productivity",
        "vendor": "Doist", "url": "https://todoist.com/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 8,
        "currency": "USD", "free_tier": True,
        "description_en": "AI assistant in Todoist for task suggestions, breakdowns, and filtering.",
        "features": ["AI task suggestions", "Task breakdown", "Filter assistance"],
        "alternatives": ["clickup-ai", "asana-ai"],
        "founded_year": 2023, "popularity_score": 65,
    },
    {
        "id": "linear-ai", "name": "Linear AI", "category": "productivity",
        "vendor": "Linear", "url": "https://linear.app/ai",
        "pricing_model": "freemium", "price_min": 0, "price_max": 14,
        "currency": "USD", "free_tier": True,
        "description_en": "AI features in Linear for issue summaries, similar issue detection, and project insights.",
        "features": ["Issue summaries", "Similar issues", "Project insights", "AI search"],
        "alternatives": ["clickup-ai", "asana-ai"],
        "founded_year": 2024, "popularity_score": 68,
    },
]

assert len(REAL_TOOLS) >= 50, f"真实工具数不足 50: {len(REAL_TOOLS)}"


def _hash_seed(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % (2**32)


def _generate_synthetic_tool(category: str, idx: int) -> dict:
    """程序化生成单个工具数据。

    使用确定性随机种子确保幂等性。
    """
    label = CATEGORY_LABELS.get(category, category.title())
    slug = f"{category}-tool-{idx:03d}"
    name = f"{label} {idx:03d}"
    seed = _hash_seed(slug)
    rng = random.Random(seed)

    # 价格模型分布
    pricing_model = rng.choices(
        ["freemium", "subscription", "pay-per-use", "one-time"],
        weights=[40, 40, 15, 5],
    )[0]

    if pricing_model == "freemium":
        price_min = 0
        price_max = rng.choice([9, 15, 19, 25, 29, 49, 99])
        free_tier = True
    elif pricing_model == "subscription":
        price_min = rng.choice([5, 9, 12, 15, 19, 20, 25, 29, 39, 49, 99])
        price_max = rng.choice([29, 49, 99, 199, 499, 999])
        free_tier = rng.random() < 0.3
    elif pricing_model == "pay-per-use":
        price_min = round(rng.uniform(0.001, 0.05), 4)
        price_max = round(rng.uniform(0.1, 5.0), 2)
        free_tier = rng.random() < 0.5
    else:  # one-time
        price_min = rng.choice([9, 19, 29, 49, 99, 199])
        price_max = price_min
        free_tier = rng.random() < 0.2

    # 厂商和 URL
    vendor_pool = [
        "AI Labs Inc", "NeuralWorks", "DeepTech AI", "SmartML Co", "FutureAI",
        "CogniTech", "NeuroSoft", "Intellico", "BrainWave AI", "SynapseLabs",
        "QuantumAI", "HyperLink AI", "Mindscape AI", "DataNova", "AutoBrain",
        "VoxAI", "Visionary AI", "PromptForge", "ModelHub", "InfernoAI",
    ]
    vendor = rng.choice(vendor_pool)
    url = f"https://{slug}.example-ai-tools.com/"

    # 人气分数（合成工具普遍较低）
    popularity_score = rng.randint(20, 65)

    # 成立年份
    founded_year = rng.choice(range(2018, 2025))

    # 描述（模板化）
    description_en = (
        f"{name} is an AI-powered {label.lower()} designed for {category} use cases. "
        f"It offers {rng.choice(['advanced', 'modern', 'innovative', 'smart', 'efficient'])} "
        f"features at {('a free tier with paid upgrades' if free_tier else 'a competitive price')}, "
        f"making it suitable for {rng.choice(['individuals', 'teams', 'enterprises', 'startups', 'developers'])}."
    )

    # 功能列表
    feature_pool = {
        "chatbots": ["Multi-turn conversation", "Custom prompts", "File upload", "Web search", "Plugins"],
        "code": ["Code completion", "Multi-language", "Code review", "Refactoring", "Documentation"],
        "image": ["Text-to-image", "Image-to-image", "Inpainting", "Style transfer", "Batch generation"],
        "video": ["Text-to-video", "Image-to-video", "Editing", "Transitions", "Multi-scene"],
        "audio": ["Text-to-speech", "Voice cloning", "Music generation", "Audio editing", "Multi-language"],
        "writing": ["Grammar check", "Style rewrite", "Summarization", "Templates", "Tone adjustment"],
        "data": ["Data cleaning", "Visualization", "Analysis", "ML models", "Reporting"],
        "research": ["Literature search", "Citation", "Summarization", "Fact check", "PDF parsing"],
        "design": ["Templates", "Brand kit", "Magic resize", "AI generation", "Collaboration"],
        "marketing": ["SEO optimization", "Content calendar", "Ad copy", "Social media", "Analytics"],
        "sales": ["Lead scoring", "Email outreach", "CRM sync", "Pipeline management", "Forecasting"],
        "hr": ["Resume screening", "Interview prep", "Onboarding", "Sentiment analysis", "Compliance"],
        "legal": ["Contract review", "Case search", "Document analysis", "Compliance", "E-discovery"],
        "finance": ["Receipt scanning", "Invoice processing", "Forecasting", "Risk analysis", "Reporting"],
        "education": ["Lesson planning", "Quiz generation", "Tutoring", "Progress tracking", "Grading"],
        "healthcare": ["Symptom check", "Medical imaging", "EHR", "Drug interaction", "Telemedicine"],
        "productivity": ["Task management", "Note taking", "Meeting summary", "Calendar", "Automation"],
        "translation": ["Multi-language", "Document translation", "Glossary", "API", "Real-time"],
        "transcription": ["Real-time", "Speaker ID", "Multi-language", "Export", "Integration"],
        "summarization": ["Long document", "Key points", "Custom length", "Multi-format", "Export"],
        "search": ["Web search", "Cited answers", "Real-time", "Custom sources", "API"],
        "analytics": ["Dashboards", "Predictive", "Anomaly detection", "Reports", "Alerts"],
        "crm": ["Contact management", "Pipeline", "Email tracking", "Reports", "Integrations"],
        "devops": ["CI/CD", "Monitoring", "Incident response", "Log analysis", "Automation"],
        "security": ["Threat detection", "Vulnerability scan", "Compliance", "Audit", "Response"],
        "testing": ["Test generation", "UI testing", "API testing", "Coverage", "Reports"],
        "monitoring": ["Real-time", "Alerts", "Dashboards", "Logs", "Traces"],
        "database": ["Query optimization", "Schema design", "Migration", "Backup", "Performance"],
        "cloud": ["Cost optimization", "Scaling", "Security", "Multi-cloud", "Automation"],
        "ml-platform": ["Model training", "Deployment", "Monitoring", "Pipelines", "Versioning"],
        "training": ["Distributed", "Hyperparameters", "Early stopping", "Tracking", "GPU"],
        "inference": ["Low latency", "Batching", "Quantization", "Scaling", "Caching"],
        "fine-tuning": ["LoRA", "QLoRA", "PEFT", "Custom datasets", "Evaluation"],
        "dataset": ["Generation", "Cleaning", "Labeling", "Versioning", "Streaming"],
        "labeling": ["Image", "Text", "Video", "Audio", "Quality control"],
        "visualization": ["Charts", "Dashboards", "Real-time", "Custom", "Export"],
        "3d": ["Text-to-3D", "Image-to-3D", "Rigging", "Animation", "Export"],
        "gaming": ["NPC AI", "Procedural", "Animation", "Testing", "Localization"],
        "robotics": ["Path planning", "Vision", "Control", "Simulation", "Learning"],
        "iot": ["Device management", "Analytics", "Edge", "Security", "Automation"],
        "blockchain": ["Smart contracts", "Audit", "Wallet", "DEX", "Analytics"],
        "crypto": ["Trading", "Portfolio", "Risk", "News", "Sentiment"],
        "metaverse": ["Avatar", "Scene", "Interaction", "Streaming", "SDK"],
        "ar": ["Tracking", "Recognition", "Scene", "Interaction", "SDK"],
        "vr": ["Scene", "Interaction", "Avatar", "Streaming", "SDK"],
        "voice": ["TTS", "STT", "Voice ID", "Conversion", "Cloning"],
        "speech": ["STT", "TTS", "Translation", "Diarization", "Sentiment"],
        "avatar": ["Realistic", "Animated", "Custom", "Lipsync", "Export"],
        "presentation": ["Auto layout", "Design", "Content", "Charts", "Export"],
        "automation": ["Workflow", "Triggers", "Actions", "Integrations", "Logs"],
    }
    features = rng.sample(feature_pool.get(category, ["Feature A", "Feature B", "Feature C"]), k=3)

    # 替代品（同分类其他工具 ID）
    alternatives_pool: list[str] = []
    # 真实工具中同分类的
    for t in REAL_TOOLS:
        if t["category"] == category and t["id"] != slug:
            alternatives_pool.append(t["id"])
    # 同分类其他合成工具
    for i in range(1, TOOLS_PER_CATEGORY + 1):
        if i != idx:
            alternatives_pool.append(f"{category}-tool-{i:03d}")
    alternatives = rng.sample(alternatives_pool, k=min(3, len(alternatives_pool)))

    return {
        "id": slug,
        "name": name,
        "category": category,
        "vendor": vendor,
        "url": url,
        "pricing_model": pricing_model,
        "price_min": price_min,
        "price_max": price_max,
        "currency": "USD",
        "free_tier": free_tier,
        "description_en": description_en,
        "features": features,
        "alternatives": alternatives,
        "founded_year": founded_year,
        "popularity_score": popularity_score,
        "synthetic": True,
    }


def generate_all_tools() -> list[dict]:
    """生成全部工具数据（真实 + 合成）。"""
    all_tools: list[dict] = []
    seen_ids: set[str] = set()

    # 真实工具
    for t in REAL_TOOLS:
        if t["id"] in seen_ids:
            raise ValueError(f"重复的工具 ID: {t['id']}")
        tool = {**t, "synthetic": False}
        all_tools.append(tool)
        seen_ids.add(tool["id"])

    # 合成工具
    for category in CATEGORIES:
        for idx in range(1, TOOLS_PER_CATEGORY + 1):
            tool = _generate_synthetic_tool(category, idx)
            if tool["id"] in seen_ids:
                raise ValueError(f"重复的工具 ID: {tool['id']}")
            all_tools.append(tool)
            seen_ids.add(tool["id"])

    return all_tools


def write_json(tools: list[dict] | None = None) -> Path:
    """写入 data/ai_tools.json。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if tools is None:
        tools = generate_all_tools()
    OUTPUT_FILE.write_text(
        json.dumps(tools, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return OUTPUT_FILE


def load_tools() -> list[dict]:
    """加载工具数据（若 json 不存在则生成）。"""
    if not OUTPUT_FILE.exists():
        write_json()
    return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))


def get_top_tools(n: int = 100) -> list[dict]:
    """按 popularity_score 取 Top N。"""
    tools = load_tools()
    return sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:n]


def get_tools_by_category(category: str) -> list[dict]:
    """按分类筛选。"""
    return [t for t in load_tools() if t["category"] == category]


def get_tool_by_id(tool_id: str) -> dict | None:
    """按 ID 查找。"""
    for t in load_tools():
        if t["id"] == tool_id:
            return t
    return None


if __name__ == "__main__":
    tools = generate_all_tools()
    path = write_json(tools)
    real_count = sum(1 for t in tools if not t.get("synthetic"))
    synth_count = sum(1 for t in tools if t.get("synthetic"))
    print(f"✅ 已写入 {path}")
    print(f"   - 总工具数: {len(tools)}")
    print(f"   - 真实工具: {real_count}")
    print(f"   - 合成工具: {synth_count}")
    print(f"   - 分类数: {len(CATEGORIES)}")
    # 抽样展示
    print(f"   - 前 3 个真实工具: {[t['id'] for t in tools[:3]]}")
    print(f"   - 前 3 个合成工具: {[t['id'] for t in tools[real_count:real_count+3]]}")
