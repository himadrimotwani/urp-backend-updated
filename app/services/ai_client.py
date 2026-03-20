"""
AI client initialization and access.
This module handles OpenAI and DeepSeek client setup.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
# Force-load .env and override any existing environment variables so changes take effect
load_dotenv(override=True)

# AI client for negotiation chat (Step 3)
# Supports both OpenAI and DeepSeek via OpenRouter
# Priority: OpenAI if OPENAI_API_KEY is set, otherwise DeepSeek via OpenRouter if OPENROUTER_API_KEY is set
openai_client = None
deepseek_client = None
# Default provider is none until we detect a valid key
ai_provider = None  # "openai" or "deepseek"

# Try DeepSeek/OpenRouter first if configured (prefer DeepSeek when present)
openrouter_key = os.getenv("OPENROUTER_API_KEY")
if openrouter_key and openrouter_key.strip() and not openrouter_key.startswith("sk-or-v1-your-"):
    if "your" in openrouter_key.lower() or "here" in openrouter_key.lower() or len(openrouter_key) < 20:
        print("WARNING: OPENROUTER_API_KEY appears to be a placeholder. Please set a real API key in .env file.")
    else:
        deepseek_client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1"
        )
        ai_provider = "deepseek"
        print("DeepSeek client initialized via OpenRouter for negotiation chat")
else:
    # Fallback to OpenAI if OpenRouter/DeepSeek isn't configured
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.strip() and not openai_key.startswith("sk-your-"):
        if "your" in openai_key.lower() or "here" in openai_key.lower() or len(openai_key) < 20:
            print("WARNING: OPENAI_API_KEY appears to be a placeholder. Please set a real API key in .env file.")
        else:
            openai_client = OpenAI(api_key=openai_key)
            ai_provider = "openai"
            print("OpenAI client initialized for negotiation chat")

if not openai_client and not deepseek_client:
    print("No AI provider configured. Negotiation chat will use fallback responses.")
    print("To configure: Set OPENAI_API_KEY or OPENROUTER_API_KEY in backend/.env file")

