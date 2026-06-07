# TODO: Implement NCT HTTP client helpers for balance queries, transaction history, EARN and SPEND requests.

from httpx import AsyncClient
from core.config import settings
from typing import Optional, Dict

class NCTClient:
    """
    HTTP client for communicating with the Nodo Coordinador de Transacciones (NCT)
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.nct_base_url
        self.client = AsyncClient(base_url=self.base_url, timeout=30.0)
    
    async def get_balance(self, student_id: str) -> Dict:
        """
        Get student balance from NCT
        """
        try:
            response = await self.client.get(f"/balance/{student_id}")
            return response.json()
        except Exception as e:
            print(f"Error getting balance: {e}")
            return {"balance": 0}
    
    async def get_transactions(self, student_id: str) -> list:
        """
        Get student transaction history from NCT
        """
        try:
            response = await self.client.get(f"/transactions/{student_id}")
            return response.json()
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []
    
    async def emit_earn(self, legajo: str, amount: int, concept: str) -> Dict:
        """
        Emit EARN transaction (issue points)
        """
        try:
            payload = {
                "sender": "ACADEMIC_SYSTEM",
                "receiver": f"student:{legajo}",
                "amount": amount,
                "concept": concept,
                "type": "EARN"
            }
            response = await self.client.post("/transaction", json=payload)
            return response.json()
        except Exception as e:
            print(f"Error emitting EARN: {e}")
            return {"error": str(e)}
    
    async def emit_spend(self, legajo: str, amount: int, vendor_id: str, concept: str) -> Dict:
        """
        Emit SPEND transaction (spend points)
        """
        try:
            payload = {
                "sender": f"student:{legajo}",
                "receiver": f"vendor:{vendor_id}",
                "amount": amount,
                "concept": concept,
                "type": "SPEND"
            }
            response = await self.client.post("/transaction", json=payload)
            return response.json()
        except Exception as e:
            print(f"Error emitting SPEND: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """
        Close HTTP client
        """
        await self.client.aclose()

# Global NCT client instance
nct_client = NCTClient()