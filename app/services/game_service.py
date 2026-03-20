"""
Game service functions for converting data structures and checking game state.
"""

from simulation.core import GameState, Contract, RoundSummary, RoundOutput
from app.schemas import (
    ContractData,
    GameStateResponse,
    RoundOutputData,
    RoundSummaryData,
    ConfigStateResponse,
    EconomicParamsData,
    HistorySummary,
)
from simulation.core import get_current_params, get_current_history
import statistics


def is_game_over(state: GameState) -> bool:
    """
    Checks if the game has ended.
    
    Inputs:
        state: The current game state containing round number, total rounds, and early end flag.
    
    What happens:
        Compares the current round number to the total allowed rounds.
        Also checks if the instructor ended the game early.
    
    Output:
        Returns True if the game is over (round number exceeds total rounds OR game was ended early),
        False otherwise.
    
    Context:
        Used throughout the application to determine if game actions are still allowed.
        Called before allowing orders, negotiations, and other game actions.
    """
    return state.round_number > state.total_rounds or state.ended_early


def has_active_contract(state: GameState) -> bool:
    """
    Checks if there is an active contract in the game.
    
    Inputs:
        state: The current game state containing the contract information.
    
    What happens:
        Checks if the contract has any remaining rounds left.
    
    Output:
        Returns True if the contract has remaining_rounds > 0, False otherwise.
    
    Context:
        Used to determine if the student can place orders or needs to negotiate a new contract.
        Called before allowing order placement and when checking negotiation eligibility.
    """
    return state.contract.remaining_rounds > 0


def to_contract_data(contract: Contract) -> ContractData:
    """
    Converts a Contract object to ContractData schema for API responses.
    
    Inputs:
        contract: A Contract object from the simulation core containing all contract terms.
    
    What happens:
        Extracts all contract fields (prices, caps, length, type, etc.) from the Contract object.
        Creates a new ContractData object with the same values.
    
    Output:
        Returns a ContractData object that can be serialized to JSON for API responses.
    
    Context:
        Used whenever contract information needs to be sent to the frontend.
        Called in API endpoints that return contract data (game state, negotiation responses, etc.).
    """
    return ContractData(
        wholesale_price=contract.wholesale_price,
        buyback_price=contract.buyback_price,
        cap_type=contract.cap_type,
        cap_value=contract.cap_value,
        length=contract.length,
        remaining_rounds=contract.remaining_rounds,
        contract_type=contract.contract_type,
        revenue_share=contract.revenue_share,
    )


def to_game_state_response(session_id: str, state: GameState) -> GameStateResponse:
    """
    Converts a GameState object to GameStateResponse schema for API responses.
    
    Inputs:
        session_id: The unique identifier for this game session.
        state: The current GameState object containing all game information.
    
    What happens:
        Extracts all relevant game state information (rounds, profits, contract, etc.).
        Converts the contract to ContractData format.
        Converts all round summaries to RoundSummaryData format.
        Checks if the game is over.
        Converts historical demands list to a regular list.
    
    Output:
        Returns a GameStateResponse object containing all game state information in API-ready format.
    
    Context:
        Used in all API endpoints that return game state to the frontend.
        Called after game actions (start game, place order, negotiate) to return updated state.
    """
    return GameStateResponse(
        session_id=session_id,
        round_number=state.round_number,
        total_rounds=state.total_rounds,
        contract=to_contract_data(state.contract),
        cumulative_buyer_profit=state.cumulative_buyer_profit,
        cumulative_supplier_profit=state.cumulative_supplier_profit,
        game_over=is_game_over(state),
        demand_method=state.method,
        historical_demands=list(state.historical_demands),
        rounds=[to_round_summary_data(rs) for rs in state.round_summaries],
    )


def to_round_output_data(round_output: RoundOutput) -> RoundOutputData:
    """
    Converts a RoundOutput object to RoundOutputData schema for API responses.
    
    Inputs:
        round_output: A RoundOutput object from the simulation containing all round results.
    
    What happens:
        Extracts all round output fields (quantities, revenues, costs, profits) from the RoundOutput object.
        Creates a new RoundOutputData object with all the same values.
    
    Output:
        Returns a RoundOutputData object containing all round results in API-ready format.
    
    Context:
        Used when returning round results after placing an order.
        Called in the place_order endpoint to format the simulation results for the frontend.
    """
    return RoundOutputData(
        order_quantity=round_output.order_quantity,
        realized_demand=round_output.realized_demand,
        sales=round_output.sales,
        unsold=round_output.unsold,
        returns=round_output.returns,
        leftovers=round_output.leftovers,
        buyer_revenue=round_output.buyer_revenue,
        buyer_cost=round_output.buyer_cost,
        buyer_profit=round_output.buyer_profit,
        supplier_revenue=round_output.supplier_revenue,
        supplier_cost=round_output.supplier_cost,
        supplier_profit=round_output.supplier_profit,
        retail_revenue=round_output.retail_revenue,
        salvage_revenue_buyer=round_output.salvage_revenue_buyer,
        buyback_refund_buyer=round_output.buyback_refund_buyer,
        wholesale_cost_buyer=round_output.wholesale_cost_buyer,
        return_shipping_cost_buyer=round_output.return_shipping_cost_buyer,
        revenue_share_payment_buyer=round_output.revenue_share_payment_buyer,
        wholesale_revenue_supplier=round_output.wholesale_revenue_supplier,
        salvage_revenue_supplier=round_output.salvage_revenue_supplier,
        production_cost_supplier=round_output.production_cost_supplier,
        buyback_cost_supplier=round_output.buyback_cost_supplier,
        return_handling_cost_supplier=round_output.return_handling_cost_supplier,
        revenue_share_revenue_supplier=round_output.revenue_share_revenue_supplier,
    )


def to_round_summary_data(rs: RoundSummary) -> RoundSummaryData:
    """
    Converts a RoundSummary object to RoundSummaryData schema for API responses.
    
    Inputs:
        rs: A RoundSummary object containing all information about a completed round.
    
    What happens:
        Extracts all round summary fields including round index, quantities, profits, and contract details.
        Creates a new RoundSummaryData object with all the same values.
    
    Output:
        Returns a RoundSummaryData object containing round summary information in API-ready format.
    
    Context:
        Used when building game state responses and game summaries.
        Called when converting lists of round summaries for display in the frontend.
    """
    return RoundSummaryData(
        round_index=rs.round_index,
        order_quantity=rs.order_quantity,
        realized_demand=rs.realized_demand,
        buyer_revenue=rs.buyer_revenue,
        buyer_cost=rs.buyer_cost,
        buyer_profit=rs.buyer_profit,
        supplier_revenue=rs.supplier_revenue,
        supplier_cost=rs.supplier_cost,
        supplier_profit=rs.supplier_profit,
        # Contract details for logging
        wholesale_price=rs.wholesale_price,
        buyback_price=rs.buyback_price,
        cap_type=rs.cap_type,
        cap_value=rs.cap_value,
        contract_length=rs.contract_length,
        remaining_rounds=rs.remaining_rounds,
        contract_type=rs.contract_type,
        revenue_share=rs.revenue_share,
    )


def build_config_state_response() -> ConfigStateResponse:
    """
    Builds a response containing all current configuration state.
    
    Inputs:
        None (reads from global configuration).
    
    What happens:
        Gets current economic parameters from config.
        Gets current demand history.
        Calculates demand statistics (min, max, mean, standard deviation).
        Loads negotiation configuration.
        Creates response objects with all this information.
    
    Output:
        Returns a ConfigStateResponse object containing:
        - Economic parameters (prices, costs, etc.)
        - Demand history summary (statistics and sample)
        - Negotiation configuration (ranges, available types, etc.)
    
    Context:
        Used by the /config endpoint to return current configuration.
        Called when instructor wants to view current settings.
        Provides all configuration data needed by the frontend.
    """
    params = get_current_params()
    history = get_current_history()

    count = len(history)
    if count > 0:
        h_min = min(history)
        h_max = max(history)
        h_mean = statistics.mean(history)
        h_stdev = statistics.stdev(history) if count > 1 else None
    else:
        h_min = h_max = 0
        h_mean = 0.0
        h_stdev = None

    # Take first few values as a sample
    sample = history[:10]

    econ_data = EconomicParamsData(
        retail_price=params.retail_price,
        buyer_salvage_value=params.buyer_salvage_value,
        supplier_salvage_value=params.supplier_salvage_value,
        supplier_cost=params.supplier_cost,
        return_shipping_buyer=params.return_shipping_buyer,
        return_handling_supplier=params.return_handling_supplier,
    )

    hist_summary = HistorySummary(
        count=count,
        min=h_min,
        max=h_max,
        mean=h_mean,
        stdev=h_stdev,
        sample=sample,
    )

    return ConfigStateResponse(
        economic_params=econ_data,
        history_summary=hist_summary,
    )

