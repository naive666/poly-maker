# merge_helpers.py
from decimal import Decimal
from web3 import Web3
import json
from pathlib import Path

# Polygon mainnet addresses
CTF_ADDRESS = Web3.to_checksum_address("0x4d97dcd97ec945f40cf65f87097ace5ea0476045")
USDC_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

ZERO_32 = b"\x00" * 32
PARTITION = [1, 2]  # full set for binary YES/NO

# load ABI once
_ctf_contract = None

def get_ctf_contract() -> "Contract":
    global _ctf_contract
    if _ctf_contract is None:
        abi_path = Path(__file__).parent / "ctf_abi.json"
        with abi_path.open() as f:
            abi = json.load(f)
        # we don't need an RPC provider just to encode data
        w3 = Web3()
        _ctf_contract = w3.eth.contract(address=CTF_ADDRESS, abi=abi)
    return _ctf_contract


def build_merge_calldata(condition_id: str, full_sets_to_merge: Decimal) -> str:
    """
    Build calldata for:

        mergePositions(
            address collateralToken,
            bytes32 parentCollectionId,
            bytes32 conditionId,
            uint256[] partition,
            uint256 amount
        )

    full_sets_to_merge is in whole "shares" (e.g. Decimal('10.5')),
    it will be converted to USDC 6-decimal units.
    """
    if full_sets_to_merge <= 0:
        raise ValueError("full_sets_to_merge must be > 0")

    ctf = get_ctf_contract()

    amount_int = int(full_sets_to_merge * (10 ** 6))  # USDC has 6 decimals

    data_hex = ctf.functions.mergePositions(
        USDC_ADDRESS,
        ZERO_32,
        Web3.to_bytes(hexstr=condition_id),
        PARTITION,
        amount_int,
    )._encode_transaction_data()

    return data_hex
