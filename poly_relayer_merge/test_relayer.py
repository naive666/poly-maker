# test_relayer.py
import os
from decimal import Decimal

from dotenv import load_dotenv
from py_builder_relayer_client.client import RelayClient
from py_builder_signing_sdk.config import BuilderConfig, BuilderApiKeyCreds
from py_builder_relayer_client.models import SafeTransaction, OperationType

from poly_relayer_merge.merger_helper import (
    CTF_ADDRESS,
    build_merge_calldata,
)

load_dotenv()


def send_one_merge(client: RelayClient, condition_id: str, full_sets_to_merge: Decimal):
    """
    Build a CTF.mergePositions SafeTransaction and send it via the relayer.
    """
    if full_sets_to_merge <= 0:
        print("Nothing to merge for", condition_id)
        return

    # 1) Build calldata
    calldata = build_merge_calldata(condition_id, full_sets_to_merge)
    print("merge calldata (first 80 chars):", calldata[:80], "...")

    # 2) Build SafeTransaction object
    merge_tx = SafeTransaction(
        to=CTF_ADDRESS,
        operation=OperationType.Call,  # 0
        data=calldata,
        value="0",
    )

    # 3) Execute via RelayClient.execute([...], metadata)
    print("Submitting merge transaction via relayer...")
    response = client.execute(
        [merge_tx],
        metadata=f"merge {full_sets_to_merge} full sets for {condition_id}",
    )

    # 4) Wait for it to complete on-chain
    print("Waiting for transaction to be mined...")
    result = response.wait()  # ClientRelayerTransactionResponse.wait()

    if result is None:
        print("Merge failed or timed out")
    else:
        print("Merge completed:")
        print("  state            =", result.get("state"))
        print("  transactionHash  =", result.get("transactionHash"))


def build_client() -> RelayClient:
    relayer_url = os.getenv("RELAYER_URL")
    chain_id = int(os.getenv("CHAIN_ID", "137"))
    pk = os.getenv("PK")
    api_key = os.getenv("BUILDER_API_KEY")
    secret = os.getenv("BUILDER_SECRET")
    passphrase = os.getenv("BUILDER_PASS_PHRASE")

    print("RELAYER_URL:", relayer_url)
    print("CHAIN_ID:", chain_id)

    if not (relayer_url and pk and api_key and secret and passphrase):
        raise RuntimeError("Some relayer / builder env vars are missing")

    builder_config = BuilderConfig(
        local_builder_creds=BuilderApiKeyCreds(
            key=api_key,
            secret=secret,
            passphrase=passphrase,
        )
    )

    client = RelayClient(
        relayer_url=relayer_url,
        chain_id=chain_id,
        private_key=pk,
        builder_config=builder_config,
    )

    safe_address = client.get_expected_safe()
    print("Safe address:", safe_address)

    return client


def main():
    client = build_client()

    # Debug: inspect a past transaction if you want
    txn_id = "019ac90e-97c5-7d39-8d0c-5baa14ec0865"
    txn_info = client.get_transaction(txn_id)
    print(txn_info)

    # === REAL MERGE CALL ===
    # Only uncomment after the Safe actually holds YES and NO for this condition

    condition_id = "0x06c971ba7d236bef9eb8ece484f1bd47b0801520f3c7e15520edf5654273a8da"
    full_sets_to_merge = Decimal("5")
    send_one_merge(client, condition_id, full_sets_to_merge)


if __name__ == "__main__":
    main()
