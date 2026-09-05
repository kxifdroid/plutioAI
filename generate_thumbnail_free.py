import os
import sys
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image

# Load environment variables from .env file
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

def sanitize_thumbnail_prompt(raw_prompt: str) -> str:
    """Clean the prompt for visual image generation.
    
    Removes confusing instructions like URLs ('HTTPS://WWW'), UI buttons ('WATCH NOW!'),
    and paragraphs of text descriptions that cause diffusion models to generate
    scrambled text and creepy distorted faces.
    """
    prompt = raw_prompt
    
    # Remove URLs and domain fragments
    prompt = re.sub(r'https?://\S+', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'https?://[a-zA-Z0-9_\.]+', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'HTTPS://WWW\S*', '', prompt, flags=re.IGNORECASE)
    
    # Remove UI/Button instructions
    prompt = re.sub(r'A red \'?WATCH NOW!\'? button with play arrow[^\.]*\.?', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'Small text \'[^\']+\' at the bottom[^\.]*\.?', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'Below that, even larger impactful text reading \'[^\']+\'[^\.]*\.?', '', prompt, flags=re.IGNORECASE)
    
    # Simplify text overlay instructions to focus on core visual topic
    prompt = re.sub(r'reading \'[^\']+\'', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'Large bold 3D text[^\.]*\.?', 'Bold modern graphic typography style.', prompt, flags=re.IGNORECASE)
    
    # Normalize whitespace
    clean = " ".join(prompt.replace("\n", " ").split())
    
    # Add strong visual quality tokens
    quality_tokens = (
        "masterpiece, ultra-realistic portrait, cinematic studio lighting, "
        "8k resolution, photorealistic, sharp focus, professional color grading, clean background"
    )
    return f"{clean}, {quality_tokens}"

def generate_with_huggingface(prompt: str, width: int, height: int, token: str) -> None:
    """Generate image using official Hugging Face Inference API."""
    from huggingface_hub import InferenceClient
    
    client = InferenceClient(token=token)
    models_to_try = [
        "black-forest-labs/FLUX.1-schnell",
        "stabilityai/stable-diffusion-xl-base-1.0",
    ]
    
    last_error = None
    for model in models_to_try:
        try:
            print(f"Generating thumbnail using Hugging Face model: {model}...", file=sys.stderr)
            img = client.text_to_image(prompt, model=model)
            if img:
                img_resized = img.resize((width, height), Image.Resampling.LANCZOS)
                img_resized.save("thumbnail.png", format="PNG")
                print("Thumbnail successfully generated and saved.", file=sys.stderr)
                return
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}", file=sys.stderr)
            continue
            
    # If all models failed, explain the exact error
    error_msg = str(last_error) if last_error else "Unknown error"
    if "403" in error_msg or "permissions" in error_msg.lower():
        sys.exit(
            "Hugging Face API Error: 403 Forbidden.\n"
            "Your Hugging Face token lacks 'Inference Providers' permission.\n"
            "Fix: Go to https://huggingface.co/settings/tokens, create a new token with 'Make calls to Inference Providers' (or 'Write' role) and update HUGGINGFACE_API_KEY in .env."
        )
    else:
        sys.exit(f"Hugging Face Generation failed: {error_msg}")

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python generate_thumbnail_free.py '<json_payload>'")

    raw_arg = sys.argv[1].strip()
    try:
        payload = json.loads(raw_arg)
    except Exception:
        try:
            payload = json.loads(raw_arg.replace("'", '"'))
        except Exception:
            payload = {"prompt": raw_arg}

    raw_prompt = payload.get("prompt", "Professional YouTube thumbnail graphic")
    aspect_ratio = payload.get("aspect_ratio", "16:9")

    # Target dimensions
    if aspect_ratio == "16:9":
        width, height = 1280, 720
    elif aspect_ratio == "9:16":
        width, height = 720, 1280
    else:
        width, height = 1024, 1024

    sanitized_prompt = sanitize_thumbnail_prompt(raw_prompt)
    print(f"Sanitized Prompt for generator:\n{sanitized_prompt}\n", file=sys.stderr)

    hf_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
    if not hf_token or not hf_token.strip():
        sys.exit(
            "Missing Hugging Face Token.\n"
            "Please set HUGGINGFACE_API_KEY=hf_... in your .env file.\n"
            "Get a free token at: https://huggingface.co/settings/tokens"
        )

    generate_with_huggingface(sanitized_prompt, width, height, hf_token.strip())

if __name__ == "__main__":
    main()