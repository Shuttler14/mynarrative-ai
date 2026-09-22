"""
MY NARRATIVE — 6-Hour Reconciliation Cron Job
Runs every 6 hours via Vercel Cron or external scheduler.

Change ID: ADD-CHK-014-260922
Risk: HIGH — financial accuracy

This job:
  1. Advances PENDING → CONFIRMED (after 72-hour confirmation delay)
  2. Advances CONFIRMED → PAYABLE (after 14-day payout delay)
  3. Checks for discrepancies (old pending without merchant orders)
  4. Logs reconciliation run
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.attribution import run_reconciliation


def handler(request, response):
    """
    Vercel Cron handler.
    Runs every 6 hours: 0 */6 * * *
    """
    result = run_reconciliation()

    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    response.body = json.dumps(result, default=str)


# For manual testing
if __name__ == "__main__":
    print("Running reconciliation...")
    result = run_reconciliation()
    print(f"Reconciliation complete: {result}")
