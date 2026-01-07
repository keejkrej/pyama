"""Tokenization task implementation."""

import asyncio
import json
from pathlib import Path
from typing import Any

import tiktoken

from .base import BaseTask


class TokenizeTask(BaseTask):
    """
    Tokenize a text file using tiktoken.

    Reads from input_file_path, sleeps for 1 minute to simulate processing,
    then writes tokenized output to output_file_path.

    Required:
        input_file_path: Path to input text file
        output_file_path: Path to output JSON file

    Parameters:
        encoding: Tiktoken encoding name (default: "cl100k_base")
        sleep_duration: Processing duration in seconds (default: 60)
    """

    async def execute(self) -> dict[str, Any]:
        """Execute the tokenization task."""
        # Validate file paths
        if not self.input_file_path:
            raise ValueError("input_file_path is required for tokenize task")
        if not self.output_file_path:
            raise ValueError("output_file_path is required for tokenize task")

        input_path = Path(self.input_file_path)
        output_path = Path(self.output_file_path)

        # Get parameters with defaults
        encoding_name = self.parameters.get("encoding", "cl100k_base")
        sleep_duration = self.parameters.get("sleep_duration", 60)

        # Step 1: Read input file (10%)
        await self.update_progress(10.0, "Reading input file")
        self.logger.info(f"Reading file: {input_path}")

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        text_content = input_path.read_text(encoding="utf-8")
        self.logger.info(f"Read {len(text_content)} characters from {input_path}")

        # Step 2: Initialize tokenizer (20%)
        await self.update_progress(20.0, "Initializing tokenizer")
        encoding = tiktoken.get_encoding(encoding_name)

        # Step 3: Sleep with progress updates (20% -> 80%)
        sleep_steps = 12  # Update every 5 seconds for 60s
        for step in range(sleep_steps):
            await self.check_cancelled()

            progress = 20.0 + ((step + 1) / sleep_steps) * 60.0
            elapsed = (step + 1) * (sleep_duration / sleep_steps)
            message = f"Processing ({step + 1}/{sleep_steps}, {elapsed:.0f}s / {sleep_duration}s)"

            await self.update_progress(progress, message)
            await asyncio.sleep(sleep_duration / sleep_steps)

        # Step 4: Tokenize (85%)
        await self.update_progress(85.0, "Tokenizing text")
        self.logger.info("Tokenizing text")

        tokens = encoding.encode(text_content)
        self.logger.info(f"Generated {len(tokens)} tokens")

        # Step 5: Write output (95%)
        await self.update_progress(95.0, "Writing output file")
        self.logger.info(f"Writing tokens to: {output_path}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write tokens as JSON
        output_data = {
            "input_file": str(input_path),
            "char_count": len(text_content),
            "token_count": len(tokens),
            "tokens": tokens,
            "encoding": encoding_name,
        }

        output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
        self.logger.info(f"Wrote tokenized output to {output_path}")

        # Return result
        return {
            "message": "Tokenization completed",
            "input_file": str(input_path),
            "output_file": str(output_path),
            "char_count": len(text_content),
            "token_count": len(tokens),
            "encoding": encoding_name,
        }
