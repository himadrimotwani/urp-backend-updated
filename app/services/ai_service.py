"""
AI service for generating chat responses and detecting agreement in negotiations.
"""

from typing import Any
import json
import re
import statistics

from simulation.core import Contract, GameState, get_current_params, get_current_history
from app.services.ai_client import openai_client, deepseek_client, ai_provider
from app.services.config_service import load_negotiation_config

def generate_chat_response(
    chat_history: list[dict[str, str]],
    current_draft_contract: Contract | None,
    game_state: GameState | None = None,
    initial_contract_type: str | None = None,
) -> dict[str, Any]:
    """
    Generates an AI response for negotiation chat using OpenAI or DeepSeek.
    
    Inputs:
        chat_history: List of previous chat messages with role and content.
        current_draft_contract: Existing draft contract if one was already proposed, None otherwise.
        game_state: Current game state for context (demand history, rounds played, etc.).
        initial_contract_type: The contract type from initial proposal (cannot be changed).
    
    What happens:
        Determines which AI client to use (OpenAI or DeepSeek).
        Builds a system prompt with game context, demand history, and negotiation constraints.
        Checks if student's message might indicate agreement.
        If agreement likely, adds explicit agreement check question to prompt.
        Sends conversation history and prompt to AI.
        Parses AI response to extract message and any JSON contract.
        Removes technical markers (NEGOTIATION_COMPLETE, CONTRACT_JSON) from message.
        Cleans the message (removes markdown, emojis).
        Detects agreement and extracts contract terms if present.
        Creates draft contract if agreement detected.
    
    Output:
        Returns a dictionary with:
        - message: Cleaned AI response message (without technical markers)
        - draft_contract: Contract object if agreement detected, None otherwise
    
    Context:
        Called by negotiation_chat endpoint to generate AI supplier responses.
        Provides educational, conversational negotiation experience.
        Can detect when student agrees and create draft contracts automatically.
    """
    # Determine which client to use
    client = None
    model_name = "deepseek"
    
    if ai_provider == "openai" and openai_client:
        client = openai_client
        model_name = "gpt-4o-mini"  # Using cost-effective model
    elif ai_provider == "deepseek" and deepseek_client:
        client = deepseek_client
        # Use free model - will fallback in error handling if needed
        model_name = "deepseek/deepseek-r1-0528:free"  # Free DeepSeek model via OpenRouter
    
    if not client:
        # Fallback to simple responses if no AI provider is configured
        return {
            "message": "I'm open to discussing contract terms. What would you like to adjust?",
            "draft_contract": None
        }
    
    # Build system prompt with game context
    params = get_current_params()
    history = get_current_history()
    
    # Calculate demand statistics
    if history:
        demand_min = min(history)
        demand_max = max(history)
        demand_avg = statistics.mean(history)
        demand_count = len(history)
    else:
        demand_min = demand_max = demand_avg = 0
        demand_count = 0
    
    # Get game progress info if available
    game_context = ""
    if game_state:
        rounds_played = max(0, game_state.round_number - 1)
        game_context = f"""
Current Game Status:
- Rounds played: {rounds_played} / {game_state.total_rounds}
- Current round: {game_state.round_number}
"""
    
    # Get negotiation config
    neg_config = load_negotiation_config()
    
    # Get the fixed contract type (cannot be changed)
    fixed_contract_type = initial_contract_type or "buyback"
    
    # Build system prompt from template
    recent_history_str = ', '.join(map(str, history[-10:])) if history else "0"
    
    # Format contract types list for prompt
    contract_types_str = ', '.join(neg_config.contract_types_available)
    
    system_prompt = neg_config.system_prompt_template.format(
        contract_type=fixed_contract_type,
        retail_price=params.retail_price,
        supplier_cost=params.supplier_cost,
        buyer_salvage_value=params.buyer_salvage_value,
        supplier_salvage_value=params.supplier_salvage_value,
        return_shipping_buyer=params.return_shipping_buyer,
        return_handling_supplier=params.return_handling_supplier,
        demand_count=demand_count,
        demand_avg=demand_avg,
        demand_min=demand_min,
        demand_max=demand_max,
        recent_history=recent_history_str,
        game_context=game_context,
        length_min=neg_config.length_min,
        length_max=neg_config.length_max,
        cap_value_min=neg_config.cap_value_min,
        cap_value_max=neg_config.cap_value_max,
        revenue_share_min=neg_config.revenue_share_min,
        revenue_share_max=neg_config.revenue_share_max,
        contract_types_available=contract_types_str,
        cap_type_allowed=neg_config.cap_type_allowed,
    )
    
    # Check if student's last message might indicate agreement
    # This helps us decide whether to ask AI to explicitly check for agreement
    last_student_msg = None
    for msg in reversed(chat_history):  # Look backwards through history
        if msg.get("role") == "student":
            last_student_msg = msg.get("content", "").lower()
            break
    
    # List of phrases that might indicate student agrees to terms
    agreement_indicators = [
        "sounds good", "that works", "yes", "yeah", "ok", "okay", "sure",
        "lock in", "lock it in", "accept", "deal", "agreed", "let's proceed"
    ]
    might_be_agreement = last_student_msg and any(phrase in last_student_msg for phrase in agreement_indicators)
    
    # Build conversation history for AI (only last 10 messages to stay within token limits)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history[-10:]:  # Last 10 messages for context
        role = "user" if msg["role"] == "student" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    
    # If student might have agreed, add explicit agreement check question to the prompt
    # This bundles everything into one API call instead of making a second call
    # Only add if we don't already have a draft contract (to avoid redundant checks)
    if might_be_agreement and not current_draft_contract:
        agreement_check_question = f"""IMPORTANT: Based on the conversation above, has the student agreed to finalize these contract terms?

If YES, you MUST return a JSON response with:
- "response": A friendly confirmation message (e.g., "Great! Let's lock in these terms..." or "Perfect! I'm happy to proceed with...")
- "contract": A contract object with ALL discussed terms:
  {{
    "wholesale_price": [value],
    "buyback_price": [value],
    "contract_length": [value],
    "cap_type": "[fraction or unit]",
    "cap_value": [value],
    "contract_type": "{initial_contract_type or 'buyback'}",
    "revenue_share": [value]
  }}
- "negotiation_complete": true

Extract ALL discussed terms from the conversation. The contract type is FIXED as "{initial_contract_type or 'buyback'}" and cannot be changed.

If NO, respond with JSON where "negotiation_complete" is false and "contract" is null."""
        messages.append({"role": "user", "content": agreement_check_question})
    
    try:
        # For DeepSeek, try alternative models if the free one fails
        models_to_try = [model_name]
        if ai_provider == "deepseek":
            models_to_try = [
                "deepseek/deepseek-r1-0528:free",
                "deepseek/deepseek-chat:free",
                "deepseek/deepseek-chat",
            ]
        
        ai_message = None
        last_error = None
        
        for try_model in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=try_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=350,
                )
                
                # Handle response - check if content exists
                if not hasattr(response, 'choices') or len(response.choices) == 0:
                    last_error = f"Model {try_model} returned no choices"
                    if try_model != models_to_try[-1]:  # Not the last model
                        continue
                    raise ValueError(last_error)
                
                message_obj = response.choices[0].message
                ai_message = message_obj.content if hasattr(message_obj, 'content') else None
                
                # Validate response
                if ai_message and ai_message.strip():
                    # Success - use this response
                    break
                else:
                    # Empty response - try next model if available
                    finish_reason = getattr(response.choices[0], 'finish_reason', None)
                    last_error = f"Model {try_model} returned empty response (finish_reason: {finish_reason})"
                    if try_model != models_to_try[-1]:  # Not the last model
                        print(f"DeepSeek: Trying alternative model. {last_error}")
                        continue
                    raise ValueError(last_error)
                    
            except Exception as e:
                error_str = str(e)
                last_error = f"Model {try_model}: {error_str}"
                # If it's a model not found error and we have more models to try, continue
                if ("model" in error_str.lower() or "not found" in error_str.lower() or "404" in error_str) and try_model != models_to_try[-1]:
                    print(f"DeepSeek: Model {try_model} not available, trying next model")
                    continue
                # Otherwise, re-raise if it's the last model
                if try_model == models_to_try[-1]:
                    raise
                # Continue to next model
                continue
        
        if not ai_message or not ai_message.strip():
            raise ValueError(f"All models failed. Last error: {last_error}")
        
        # Parse AI response - expects JSON structure: {"response": "...", "contract": {...} or null, "negotiation_complete": true/false}
        # Clean up the response by removing any markdown code blocks that might wrap the JSON
        ai_message_clean = ai_message.strip()
        ai_message_clean = re.sub(r'^```(?:json)?\s*', '', ai_message_clean, flags=re.MULTILINE)
        ai_message_clean = re.sub(r'```\s*$', '', ai_message_clean, flags=re.MULTILINE)
        ai_message_clean = ai_message_clean.strip()
        
        try:
            # Parse the cleaned message as JSON
            response_data = json.loads(ai_message_clean)
            
            # Extract fields from structured JSON response
            cleaned_message = response_data.get("response", "").strip()
            json_contract = response_data.get("contract")
            
            # Validate that response field exists and is not empty
            if not cleaned_message:
                raise ValueError("Empty response field in JSON")
                
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            # If JSON parsing fails, return a simple fallback message to maintain conversation flow
            return {
                "message": "I'm having trouble processing that. Could you rephrase your proposal?",
                "draft_contract": current_draft_contract
            }
        
        # Get initial contract type from game state (contract type cannot be changed during negotiation)
        initial_ct = None
        if game_state:
            initial_ct = game_state.initial_contract_type
        
        # Create Contract object from JSON if present
        draft_contract = None
        if json_contract:
            try:
                params = get_current_params()
                neg_config = load_negotiation_config()
                
                # Handle both "contract_length" and "length" keys for backward compatibility
                contract_length = json_contract.get("contract_length") or json_contract.get("length") or neg_config.length_min
                contract_type_to_use = initial_ct or "buyback"
                
                # Determine cap_type based on configuration
                default_cap_type = "fraction"
                if neg_config.cap_type_allowed == "unit":
                    default_cap_type = "unit"
                elif neg_config.cap_type_allowed == "both":
                    default_cap_type = json_contract.get("cap_type", "fraction")
                
                # Create Contract object from JSON data
                draft_contract = Contract(
                    wholesale_price=float(json_contract.get("wholesale_price", 0)),
                    buyback_price=float(json_contract.get("buyback_price", 0)),
                    cap_type=json_contract.get("cap_type", default_cap_type),
                    cap_value=float(json_contract.get("cap_value", neg_config.cap_value_max)),
                    length=int(contract_length),
                    contract_type=contract_type_to_use,
                    revenue_share=float(json_contract.get("revenue_share", neg_config.revenue_share_min)),
                )
                
                # Validate and clamp contract values to ensure they're within allowed ranges
                if draft_contract.wholesale_price > 0 and draft_contract.buyback_price >= 0 and draft_contract.buyback_price < draft_contract.wholesale_price:
                    # Clamp contract length to valid range
                    draft_contract.length = max(neg_config.length_min, min(draft_contract.length, neg_config.length_max))
                    
                    # Clamp cap_value based on cap_type
                    if draft_contract.cap_type == "fraction":
                        draft_contract.cap_value = max(neg_config.cap_value_min, min(draft_contract.cap_value, neg_config.cap_value_max))
                    elif draft_contract.cap_type == "unit":
                        draft_contract.cap_value = max(neg_config.cap_value_min, draft_contract.cap_value)
                    
                    # Clamp revenue_share to valid range
                    draft_contract.revenue_share = max(neg_config.revenue_share_min, min(draft_contract.revenue_share, neg_config.revenue_share_max))
                    
                    # Validate contract_type and cap_type are valid values
                    if draft_contract.contract_type not in ("buyback", "revenue_sharing", "hybrid"):
                        draft_contract.contract_type = "buyback"
                    if draft_contract.cap_type not in ("fraction", "unit"):
                        draft_contract.cap_type = "fraction"
                else:
                    # Invalid contract values - discard it
                    print(f"Invalid contract from JSON: wholesale={draft_contract.wholesale_price}, buyback={draft_contract.buyback_price}")
                    draft_contract = None
            except (ValueError, KeyError, TypeError) as e:
                # Error creating contract from JSON - log and continue without draft contract
                print(f"Error creating contract from JSON: {e}")
                draft_contract = None
        
        return {
            "message": cleaned_message,
            "draft_contract": draft_contract
        }
    except Exception as e:
        # Better error logging for debugging
        error_msg = str(e)
        print(f"AI API error ({ai_provider}): {error_msg}")
        print(f"Model: {model_name}")
        print(f"Messages count: {len(messages)}")
        
        # Provide more helpful fallback that maintains conversation
        fallback_responses = [
            "I understand you're asking about contract terms. Could you be more specific about what you'd like to adjust?",
            "Let me help you understand the contract structure. What specific term would you like to discuss?",
            "I'm here to negotiate. What changes are you proposing to the contract?",
        ]
        
        # Use a simple rotation based on message count to vary responses
        fallback_index = len(chat_history) % len(fallback_responses)
        
        return {
            "message": fallback_responses[fallback_index],
            "draft_contract": current_draft_contract
        }

