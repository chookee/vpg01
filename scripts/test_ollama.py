#!/usr/bin/env python3
"""Test direct connection to Ollama."""

import asyncio
import aiohttp


async def test_ollama():
    """Test Ollama API directly."""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen3.5:4b",
        "prompt": "Say hello in one word",
        "stream": False
    }
    
    print(f"Connecting to {url}...")
    print(f"Model: qwen3.5:4b")
    print(f"Prompt: {payload['prompt']}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            print("Sending request...")
            async with session.post(url, json=payload) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Response: {data.get('response', 'N/A')[:200]}")
                else:
                    error = await response.text()
                    print(f"Error: {error}")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_ollama())
