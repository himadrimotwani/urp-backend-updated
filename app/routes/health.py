"""
Health and status check routes.
"""

from typing import Dict, Any
from fastapi import APIRouter

from app.services.ai_client import openai_client, deepseek_client, ai_provider

router = APIRouter()


@router.get("/")
def root() -> Dict[str, str]:
    """
    Root endpoint that provides basic API information.
    
    Inputs:
        None.
    
    What happens:
        Returns a simple message directing users to the health endpoint.
    
    Output:
        Returns a dictionary with a message pointing to the health endpoint.
    
    Context:
        Called when accessing the root URL of the API.
        Provides basic API discovery information.
    """
    return {"message": "Backend root. Try /health"}


@router.get("/health")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify the backend is running.
    
    Inputs:
        None.
    
    What happens:
        Returns a simple status message indicating the backend is operational.
    
    Output:
        Returns a dictionary with status, message, and version information.
    
    Context:
        Called by monitoring systems and frontend to check if backend is alive.
        Used for health checks and debugging connectivity issues.
    """
    return {
        "status": "ok",
        "message": "Backend running",
        "version": "0.1.0"
    }


@router.get("/ai/status")
def ai_status_check() -> Dict[str, Any]:
    """
    Checks the status and connectivity of AI providers (OpenAI and DeepSeek).
    
    Inputs:
        None (checks global AI client configuration).
    
    What happens:
        Checks if OpenAI client is configured and tests it with a simple API call.
        Checks if DeepSeek client is configured and tests it with a simple API call.
        Records whether each provider is working, has errors, or is not configured.
        Provides helpful error messages for common issues (invalid API keys, etc.).
    
    Output:
        Returns a dictionary with status information for both providers:
        - Configuration status (configured/not configured)
        - Test status (working/error/not_configured)
        - Error messages if applicable
        - Which provider is currently active
    
    Context:
        Called by the frontend to display AI provider status to instructors.
        Used for debugging AI integration issues.
        Helps users understand if AI features will work.
    """
    status = {
        "openai_configured": openai_client is not None,
        "deepseek_configured": deepseek_client is not None,
        "active_provider": ai_provider,
        "openai_status": "not_configured",
        "openai_message": "",
        "openai_test_successful": False,
        "deepseek_status": "not_configured",
        "deepseek_message": "",
        "deepseek_test_successful": False,
    }
    
    # Test OpenAI if configured
    if openai_client:
        status["openai_status"] = "testing"
        try:
            test_response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say OK if you can read this."}
                ],
                max_tokens=10,
            )
            
            test_message = test_response.choices[0].message.content
            if test_message:
                status["openai_status"] = "working"
                status["openai_message"] = "OpenAI is working correctly"
                status["openai_test_successful"] = True
            else:
                status["openai_status"] = "error"
                status["openai_message"] = "OpenAI returned empty response"
        except Exception as e:
            status["openai_status"] = "error"
            error_str = str(e)
            # Provide more helpful error messages
            if "invalid_api_key" in error_str or "401" in error_str or "Incorrect API key" in error_str:
                status["openai_message"] = "Invalid API key. Please check your OPENAI_API_KEY in .env file. Make sure it's a real key from https://platform.openai.com/api-keys"
            else:
                status["openai_message"] = f"OpenAI error: {error_str}"
    else:
        status["openai_message"] = "Not configured (set OPENAI_API_KEY)"
    
    # Test DeepSeek if configured
    if deepseek_client:
        status["deepseek_status"] = "testing"
        # Try multiple model names in case the free one is unavailable
        models_to_try = [
            "deepseek/deepseek-r1-0528:free",
            "deepseek/deepseek-chat:free",
            "deepseek/deepseek-chat",
        ]
        
        test_successful = False
        last_error = None
        
        for model_name in models_to_try:
            try:
                test_response = deepseek_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say OK if you can read this."}
                    ],
                    max_tokens=20,
                )
                
                # Check response structure
                if hasattr(test_response, 'choices') and len(test_response.choices) > 0:
                    message_obj = test_response.choices[0].message
                    test_message = message_obj.content if hasattr(message_obj, 'content') else None
                    
                    if test_message and test_message.strip():
                        status["deepseek_status"] = "working"
                        status["deepseek_message"] = f"DeepSeek is working correctly (using {model_name})"
                        status["deepseek_test_successful"] = True
                        test_successful = True
                        break
                    else:
                        # Empty response - try next model
                        last_error = f"Model {model_name} returned empty response"
                        print(f"DeepSeek: {last_error}")
                        continue
                else:
                    last_error = f"Model {model_name} returned no choices"
                    print(f"DeepSeek: {last_error}")
                    continue
                    
            except Exception as e:
                error_str = str(e)
                last_error = f"Model {model_name}: {error_str}"
                print(f"DeepSeek test error for {model_name}: {error_str}")
                
                # If it's a model not found error, try next model
                if "model" in error_str.lower() or "not found" in error_str.lower() or "404" in error_str:
                    continue
                # If it's auth error, don't try other models
                elif "invalid_api_key" in error_str or "401" in error_str or "Unauthorized" in error_str:
                    status["deepseek_status"] = "error"
                    status["deepseek_message"] = "Invalid API key. Please check your OPENROUTER_API_KEY in .env file. Get a key from https://openrouter.ai/keys"
                    return status
                # For other errors, try next model
                else:
                    continue
        
        if not test_successful:
            status["deepseek_status"] = "error"
            if last_error:
                status["deepseek_message"] = f"All DeepSeek models failed. Last error: {last_error}. Check backend logs for details."
            else:
                status["deepseek_message"] = "DeepSeek test failed. Check backend logs for details."
    else:
        status["deepseek_message"] = "Not configured (set OPENROUTER_API_KEY)"
    
    return status

