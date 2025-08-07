#!/bin/bash
cd /home/kavia/workspace/code-generation/poll-incentive-reward-system-21333-21342/reward_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

