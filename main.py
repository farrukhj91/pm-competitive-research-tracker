#!/usr/bin/env python
"""
Competitive Research Tracker

Main entry point for the CLI. Run with:
  python main.py add-business
  python main.py crawl-now --business-id <id>
  python main.py list-businesses
"""

from src.cli import main

if __name__ == "__main__":
    main()
