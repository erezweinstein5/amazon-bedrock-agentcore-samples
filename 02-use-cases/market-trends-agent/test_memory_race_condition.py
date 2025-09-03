#!/usr/bin/env python3
"""
Test script to simulate race condition during memory creation
"""

import concurrent.futures
import os
from tools.memory_tools import create_memory

def create_memory_worker(worker_id):
    """Worker function to simulate concurrent memory creation"""
    print(f"Worker {worker_id}: Starting memory creation...")
    try:
        client, memory_id = create_memory()
        print(f"Worker {worker_id}: SUCCESS - Got memory ID: {memory_id}")
        return memory_id
    except Exception as e:
        print(f"Worker {worker_id}: ERROR - {e}")
        return None

def test_concurrent_memory_creation():
    """Test concurrent memory creation to verify race condition handling"""
    
    print("🧪 TESTING CONCURRENT MEMORY CREATION")
    print("=" * 60)
    
    # Remove any existing memory ID file to simulate fresh deployment
    memory_id_file = '.memory_id'
    if os.path.exists(memory_id_file):
        os.remove(memory_id_file)
        print("🗑️  Removed existing .memory_id file to simulate fresh deployment")
    
    # Simulate multiple processes trying to create memory simultaneously
    num_workers = 4
    print(f"🚀 Starting {num_workers} concurrent workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all workers simultaneously
        futures = [executor.submit(create_memory_worker, i+1) for i in range(num_workers)]
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    print(f"\n📊 RESULTS:")
    print(f"   - Workers completed: {len(results)}")
    print(f"   - Unique memory IDs: {len(set(results))}")
    
    if len(set(results)) == 1:
        print("✅ SUCCESS: All workers got the same memory ID (race condition handled)")
        print(f"   Memory ID: {results[0]}")
    else:
        print("❌ ISSUE: Workers got different memory IDs (race condition not handled)")
        for i, memory_id in enumerate(set(results)):
            print(f"   Memory ID {i+1}: {memory_id}")

if __name__ == "__main__":
    test_concurrent_memory_creation()