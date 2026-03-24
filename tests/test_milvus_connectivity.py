#!/usr/bin/env python3
"""
Test Milvus connectivity and basic operations
"""

import sys
from pymilvus import connections, utility, Collection, CollectionSchema, FieldSchema, DataType

def test_milvus_connection():
    """Test basic Milvus connection"""
    print("=" * 70)
    print("Phase 5: Testing Milvus Connectivity")
    print("=" * 70)

    try:
        # Connect to Milvus
        print("\n[1/5] Connecting to Milvus at localhost:19530...")
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )
        print("SUCCESS: Connected to Milvus")

        # Check server version
        print("\n[2/5] Checking Milvus server version...")
        version = utility.get_server_version()
        print(f"SUCCESS: Milvus version: {version}")

        # List existing collections
        print("\n[3/5] Listing existing collections...")
        collections = utility.list_collections()
        if collections:
            print(f"Found {len(collections)} existing collections: {collections}")
        else:
            print("No existing collections found (this is normal for a fresh install)")

        # Create a test collection
        print("\n[4/5] Creating test collection 'connectivity_test'...")

        # Define collection schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384)
        ]
        schema = CollectionSchema(fields, description="Test collection for connectivity verification")

        # Drop collection if it already exists
        if utility.has_collection("connectivity_test"):
            print("  - Dropping existing test collection...")
            utility.drop_collection("connectivity_test")

        # Create collection
        collection = Collection(name="connectivity_test", schema=schema)
        print("SUCCESS: Test collection created")

        # Verify collection exists
        print("\n[5/5] Verifying test collection...")
        if utility.has_collection("connectivity_test"):
            print("SUCCESS: Test collection verified")

            # Get collection stats
            collection.flush()
            stats = collection.num_entities
            print(f"  - Collection has {stats} entities")

        # Clean up test collection
        print("\nCleaning up test collection...")
        utility.drop_collection("connectivity_test")
        print("SUCCESS: Test collection removed")

        # Disconnect
        connections.disconnect("default")

        print("\n" + "=" * 70)
        print("PHASE 5 COMPLETE: All Milvus connectivity tests passed!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\nERROR: Milvus connectivity test failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Verify Milvus is running: docker ps")
        print("2. Check Milvus logs: docker logs milvus-standalone")
        print("3. Verify port 19530 is accessible: netstat -an | findstr 19530")
        print("\n" + "=" * 70)
        return False

if __name__ == "__main__":
    success = test_milvus_connection()
    sys.exit(0 if success else 1)
