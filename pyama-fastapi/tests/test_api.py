#!/usr/bin/env python3
"""Simple test script for the task API."""

import time
import requests


BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test the health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    assert response.status_code == 200
    print("  ✓ Health check passed\n")


def test_submit_and_poll_task():
    """Test submitting a task and polling for progress."""
    print("Testing task submission and polling...")

    # Submit a short dummy task
    print("  Submitting dummy_short task...")
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"task_type": "dummy_short", "parameters": {}},
    )
    assert response.status_code == 200
    task_data = response.json()
    task_id = task_data["task_id"]
    print(f"  Task ID: {task_id}")
    print(f"  Status: {task_data['status']}\n")

    # Poll for progress
    print("  Polling for progress...")
    while True:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}")
        assert response.status_code == 200
        task_info = response.json()

        print(f"    Progress: {task_info['progress']:.1f}% - {task_info['message']}")

        if task_info["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(1)

    print(f"\n  Final status: {task_info['status']}")
    if task_info.get("result"):
        print(f"  Result: {task_info['result']}")
    print("  ✓ Task completed successfully\n")


def test_concurrent_task_rejection():
    """Test that submitting a second task while one is running is rejected."""
    print("Testing concurrent task rejection...")

    # Submit a long task
    print("  Submitting dummy_long task...")
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"task_type": "dummy_long", "parameters": {}},
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]
    print(f"  Task ID: {task_id}")

    # Try to submit another task immediately
    print("  Attempting to submit another task...")
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"task_type": "dummy_short", "parameters": {}},
    )
    assert response.status_code == 409  # Conflict
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    print("  ✓ Concurrent task correctly rejected\n")

    # Cancel the running task
    print("  Cancelling the running task...")
    response = requests.delete(f"{BASE_URL}/tasks/{task_id}")
    assert response.status_code == 200
    print("  ✓ Task cancelled\n")


def test_get_current_task():
    """Test getting the current running task."""
    print("Testing get current task...")

    # Check when no task is running
    response = requests.get(f"{BASE_URL}/tasks/current/info")
    assert response.status_code == 200
    print(f"  Current task (no task running): {response.json()}")

    # Submit a task
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={"task_type": "dummy_short", "parameters": {}},
    )
    task_id = response.json()["task_id"]

    # Check current task
    response = requests.get(f"{BASE_URL}/tasks/current/info")
    assert response.status_code == 200
    current_task = response.json()
    print(f"  Current task: {current_task['task_id']} - {current_task['status']}")

    # Wait for completion
    while True:
        response = requests.get(f"{BASE_URL}/tasks/{task_id}")
        if response.json()["status"] == "completed":
            break
        time.sleep(0.5)

    print("  ✓ Get current task passed\n")


def test_list_tasks():
    """Test listing all tasks."""
    print("Testing list tasks...")
    response = requests.get(f"{BASE_URL}/tasks")
    assert response.status_code == 200
    tasks = response.json()
    print(f"  Total tasks in history: {len(tasks)}")
    for task in tasks[-3:]:  # Show last 3 tasks
        print(f"    - {task['task_id']}: {task['status']} ({task['task_type']})")
    print("  ✓ List tasks passed\n")


if __name__ == "__main__":
    print("=" * 60)
    print("PyAMA FastAPI Task Backend Tests")
    print("=" * 60 + "\n")

    try:
        test_health_check()
        test_submit_and_poll_task()
        test_get_current_task()
        test_concurrent_task_rejection()
        test_list_tasks()

        print("=" * 60)
        print("All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise
