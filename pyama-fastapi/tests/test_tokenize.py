#!/usr/bin/env python3
"""Test script for the tokenization task."""

import time
import requests


BASE_URL = "http://localhost:8000"


def test_tokenize_task():
    """Test the tokenization task."""
    print("=" * 60)
    print("Testing Tokenization Task")
    print("=" * 60 + "\n")

    # Submit tokenization task
    print("Submitting tokenize task...")
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={
            "task_type": "tokenize",
            "parameters": {},
            "input_file_path": "test_input.txt",
            "output_file_path": "test_output.json",
        },
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.json())
        return

    task_data = response.json()
    task_id = task_data["task_id"]
    print(f"Task ID: {task_id}")
    print(f"Status: {task_data['status']}\n")

    # Poll for progress
    print("Polling for progress (this will take ~1 minute)...")
    print("-" * 60)

    last_progress = -1
    while True:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}")
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break

        task_info = response.json()
        progress = task_info["progress"]

        # Only print when progress changes
        if progress != last_progress:
            print(
                f"[{task_info['status'].upper():10}] "
                f"{progress:5.1f}% - {task_info['message']}"
            )
            last_progress = progress

        if task_info["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(2)

    print("-" * 60)
    print(f"\nFinal status: {task_info['status']}")

    if task_info["status"] == "completed":
        result = task_info["result"]
        print("\nResult:")
        print(f"  Input file: {result['input_file']}")
        print(f"  Output file: {result['output_file']}")
        print(f"  Character count: {result['char_count']}")
        print(f"  Token count: {result['token_count']}")
        print(f"  Encoding: {result['encoding']}")
        print("\n✓ Tokenization task completed successfully!")
    elif task_info["status"] == "failed":
        print(f"\n✗ Task failed: {task_info.get('error', 'Unknown error')}")
    else:
        print(f"\n⚠ Task ended with status: {task_info['status']}")

    print("=" * 60)


if __name__ == "__main__":
    try:
        test_tokenize_task()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise
