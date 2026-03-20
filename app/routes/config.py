"""
Configuration management routes.
"""

from pathlib import Path
import json
import csv
from fastapi import APIRouter, HTTPException

from app.schemas import (
    ConfigStateResponse,
    UpdateConfigRequest,
    NegotiationConfigResponse,
    UpdateNegotiationConfigRequest,
)
from app.services.game_service import build_config_state_response
from app.services.config_service import (
    load_negotiation_config,
    reload_negotiation_config,
    DEFAULT_NEGOTIATION_CONFIG_PATH,
)
from simulation.core import reload_defaults

router = APIRouter()


@router.get("/config/current", response_model=ConfigStateResponse)
def get_config() -> ConfigStateResponse:
    """
    Returns the current configuration state (economic parameters, demand history, negotiation config).
    
    Inputs:
        None.
    
    What happens:
        Calls build_config_state_response() to gather all configuration data.
        Returns economic parameters, demand history statistics, and negotiation config.
    
    Output:
        Returns a ConfigStateResponse containing all current configuration settings.
    
    Context:
        Called by frontend to display current configuration to instructor.
        Used to load configuration into the UI for viewing and editing.
    """
    return build_config_state_response()


@router.post("/config/update", response_model=ConfigStateResponse)
def update_config(request: UpdateConfigRequest) -> ConfigStateResponse:
    """
    Updates economic parameters and/or demand history.
    
    Inputs:
        request: UpdateConfigRequest containing:
            - Optional economic parameters (retail_price, costs, salvage values, etc.)
            - Optional demand_history list
    
    What happens:
        If economic parameters provided: updates them and saves to economic_params.json file.
        If demand history provided: updates it and saves to D_hist.csv file.
        Reloads the configuration so changes take effect immediately.
        Updates global configuration state.
    
    Output:
        Returns a ConfigStateResponse with the updated configuration.
    
    Context:
        Called by instructor to modify game parameters.
        Changes affect all future games and negotiations.
        Used to customize the simulation environment.
    """
    # Update economic params JSON if provided
    if request.economic_params is not None:
        econ = request.economic_params
        econ_path = Path("config/economic_params.json")
        econ_path.parent.mkdir(parents=True, exist_ok=True)
        econ_data = {
            "retail_price": econ.retail_price,
            "buyer_salvage_value": econ.buyer_salvage_value,
            "supplier_salvage_value": econ.supplier_salvage_value,
            "supplier_cost": econ.supplier_cost,
            "return_shipping_buyer": econ.return_shipping_buyer,
            "return_handling_supplier": econ.return_handling_supplier,
        }
        econ_path.write_text(json.dumps(econ_data, indent=2))

    # Update history CSV if provided
    if request.history is not None:
        hist = request.history
        hist_path = Path("data/D_hist.csv")
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        with hist_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["demand"])
            for val in hist:
                writer.writerow([int(val)])

    # Reload defaults from disk so new games use these values
    reload_defaults()

    # Return the new config state
    return build_config_state_response()


@router.get("/config/negotiation", response_model=NegotiationConfigResponse)
def get_negotiation_config() -> NegotiationConfigResponse:
    """
    Returns the current negotiation configuration.
    
    Inputs:
        None.
    
    What happens:
        Loads negotiation configuration from file or cache.
        Returns it in API response format.
    
    Output:
        Returns a NegotiationConfigResponse containing the negotiation configuration.
    
    Context:
        Called by frontend to display negotiation settings to instructor.
        Used to load configuration for viewing and editing.
    """
    config = load_negotiation_config()
    return NegotiationConfigResponse(negotiation_config=config)


@router.post("/config/negotiation/update", response_model=NegotiationConfigResponse)
def update_negotiation_config(request: UpdateNegotiationConfigRequest) -> NegotiationConfigResponse:
    """
    Updates the negotiation configuration settings.
    
    Inputs:
        request: UpdateNegotiationConfigRequest containing:
            - negotiation_config: NegotiationConfigData with all settings
            - contract_types_available: List of allowed contract types
            - length_min, length_max: Contract length range
            - cap_type_allowed: "fraction" or "unit"
            - cap_value_min, cap_value_max: Cap value range
            - revenue_share_min, revenue_share_max: Revenue share range
            - system_prompt_template: AI prompt template
            - example_dialog: Example conversation for AI
    
    What happens:
        Validates all configuration values are reasonable and consistent.
        Saves the configuration to negotiation_config.json file.
        Reloads the configuration so changes take effect immediately.
        Updates the cached config in memory.
    
    Output:
        Returns a NegotiationConfigResponse with the updated configuration.
    
    Context:
        Called by instructor to customize negotiation parameters.
        Changes affect what contract terms students can propose.
        Used to restrict or expand negotiation options for educational purposes.
    """
    if request.negotiation_config is None:
        raise HTTPException(status_code=400, detail="negotiation_config is required")
    
    config = request.negotiation_config
    
    # Validate config
    if config.length_min < 1:
        raise HTTPException(status_code=400, detail="length_min must be at least 1")
    if config.length_max < config.length_min:
        raise HTTPException(status_code=400, detail="length_max must be >= length_min")
    if config.cap_type_allowed not in ("fraction", "unit", "both"):
        raise HTTPException(status_code=400, detail="cap_type_allowed must be 'fraction', 'unit', or 'both'")
    if config.cap_value_min < 0:
        raise HTTPException(status_code=400, detail="cap_value_min must be >= 0")
    if config.cap_value_max < config.cap_value_min:
        raise HTTPException(status_code=400, detail="cap_value_max must be >= cap_value_min")
    if config.revenue_share_min < 0 or config.revenue_share_min > 1:
        raise HTTPException(status_code=400, detail="revenue_share_min must be between 0 and 1")
    if config.revenue_share_max < config.revenue_share_min or config.revenue_share_max > 1:
        raise HTTPException(status_code=400, detail="revenue_share_max must be between revenue_share_min and 1")
    if not config.contract_types_available:
        raise HTTPException(status_code=400, detail="At least one contract type must be available")
    for ct in config.contract_types_available:
        if ct not in ("buyback", "revenue_sharing", "hybrid"):
            raise HTTPException(status_code=400, detail=f"Invalid contract type: {ct}")
    
    # Save to file
    config_path = DEFAULT_NEGOTIATION_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config_dict = config.model_dump()
    config_path.write_text(json.dumps(config_dict, indent=2))
    
    # Reload in-memory config
    reload_negotiation_config()
    
    return NegotiationConfigResponse(negotiation_config=load_negotiation_config())

