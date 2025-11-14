"""Flight search message instruction.

Provides formatting instructions for flight search results.
"""
from typing import Dict, Any

from app.infrastructure.providers.message_instructions import MessageInstruction


class FlightSearchMessageInstruction(MessageInstruction):
    """Instruction for flight search use case."""
    
    def applies_to(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Check if this applies to flight search results."""
        return tool_name == "search_flights" and result.get("success", False)
    
    def get_instruction(self) -> str:
        """Get the flight search formatting instruction."""
        return (
            "**CRITICAL: Your entire response MUST NOT exceed 4000 characters to comply with WhatsApp message limits.**\n\n"
            "**CRITICAL: Always reply in the same language as the user's message, default to spanish.**\n\n"
            "If the flight results are too many, show only the top 5–7 options and mention that more options are available on request.**\n\n"
            
            "Format all flight options in a clean, highly readable, WhatsApp-optimized layout.\n\n"
            
            "**FOR ROUND-TRIP FLIGHTS (FlightType:RoundTrip):**\n"
            "Your output MUST follow this exact structure:\n\n"
            " 1️⃣ [Option number emoji] — Round Trip\n"
            "💰 Total Price: {total_price} {currency} (ida + vuelta)\n"
            "⏱️ Total duration: {total_duration}h {total_duration}m\n"
            "🧳 No baggage included or {baggage} pieces of baggage\n"
            "📅 Last ticketing date: {last_ticketing_date}\n"
            "✅ {policy_status}\n\n"
            "**Ida:**\n"
            "  [Direct 🟢 or {outbound_stops} stops] — ⏱️ {outbound_duration}h {outbound_duration}m\n"
            "  ✈️ {flight_number} — 🛫 {origin} {departure_time} → 🛬 {destination} {arrival_time}\n"
            "  [List all outbound segments, one per line]\n\n"
            "**Vuelta:**\n"
            "  [Direct 🟢 or {return_stops} stops] — ⏱️ {return_duration}h {return_duration}m\n"
            "  ✈️ {flight_number} — 🛫 {origin} {departure_time} → 🛬 {destination} {arrival_time}\n"
            "  [List all return segments, one per line]\n"
            "⸻\n\n"
            
            "**FOR ONE-WAY FLIGHTS (FlightType:OneWay):**\n"
            "Your output MUST follow this exact structure:\n\n"
            " 1️⃣ [Option number emoji] — [Direct 🟢 or {stops} stops]\n"
            "⏱️ Total duration: {duration}h {duration}m\n"
            "💰 {price} {currency}\n"
            "🧳 No baggage included or {baggage} pieces of baggage\n"
            "📅 Last ticketing date: {last_ticketing_date}\n"
            "✅ {policy_status}\n"
            "✈️ {flight_number} — 🛫 {origin} {departure_time} → 🛬 {destination} {arrival_time}\n"
            "[List all segments, one per line]\n"
            "⸻\n\n"

            "The assistant must generate the same style for every result. Follow these rules:\n\n"

            "**For Round-Trip flights:**\n"
            "• Start with option number and \"Round Trip\"\n"
            "• Show the TOTAL PRICE in USD first (this is the combined price for both outbound and return)\n"
            "• Then show total duration, baggage, last ticketing date, and policy status\n"
            "  IMPORTANT: The duration fields (TotalDuration, OutboundDuration, ReturnDuration) already include layover/waiting times between segments.\n"
            "• Then clearly separate with \"**Ida:**\" section:\n"
            "  - Show outbound stops (use OutboundStops field: 0 = Direct 🟢, 1 = 1 stop, etc.)\n"
            "  - Show outbound duration (use OutboundDuration field - this includes layover times between segments)\n"
            "  - List all OutboundSegments, one per line\n"
            "• Then clearly separate with \"**Vuelta:**\" section:\n"
            "  - Show return stops (use ReturnStops field: 0 = Direct 🟢, 1 = 1 stop, etc.)\n"
            "  - Show return duration (use ReturnDuration field - this includes layover times between segments)\n"
            "  - List all ReturnSegments, one per line\n\n"
            
            "**For One-Way flights:**\n"
            "• Start each option with: [Option number emoji] — [Direct or number of stops]. "
            "IMPORTANT: Use the NumStops field from the flight data directly. "
            "If NumStops is 0, show \"Direct 🟢\". If NumStops is 1, show \"1 stop\". If NumStops is 2, show \"2 stops\", etc.\n"
            "• Then show the total travel duration (this already includes layover/waiting times between segments if there are connections)\n"
            "• Then show the price\n"
            "• Then show the baggage:\n"
            "    - \"No baggage\" if the baggage is 0\n"
            "    - \"1 Piece of baggage\" if the baggage is 1\n"
            "    - \"x Pieces of baggage\" if the baggage is greater than 1\n"
            "• Then show the last ticketing date\n"
            "• Then show policy status:\n"
            "   - \"in_policy\" → \"✅ In Policy\"\n"
            "   - \"requires_approval\" → \"⚠️ Requires Approval\"\n"
            "   - \"out_of_policy\" → \"❌ Out of Policy\"\n"
            "• After that, list all segments, one per line, using the format:\n"
            "   ✈️ {flight_number} — 🛫 {origin} {departure_time} → 🛬 {destination} {arrival_time}\n\n"

            "**General rules:**\n"
            "• For direct flights, show only one segment per leg.\n"
            "• For multi-segment flights, show ALL segments in order.\n"
            "• Show baggage only once per option (e.g., \"🧳 0 PC\" or \"🧳 1 PC\").\n"
            "• DO NOT calculate stops from segments - use the Stops fields directly (NumStops, OutboundStops, ReturnStops).\n"
            "• Airlines information is available in the flight data (Airlines, OutboundAirlines, ReturnAirlines fields). "
            "If the user asks for flights from a specific airline, filter and show only options that include that airline code. "
            "Airline codes are IATA codes (e.g., AA, DL, UA, BA, LH).\n"
            "• Keep the tone professional, concise, and user-friendly.\n\n"

            "Use these emojis consistently:\n"
            "• ✈️ For flight segments\n"
            "• 🧳 For baggage\n"
            "• ⏱️ For durations\n"
            "• 📅 For purchase deadline\n"
            "• 🔁 For connecting flights\n"
            "• 🟢 For direct flights\n"
            "• 💰 For price\n"
            "• ⸻ As separator between options\n\n"

            "Do NOT include explanations, intros, or summaries. Only output the formatted options in the defined WhatsApp structure."
        )

