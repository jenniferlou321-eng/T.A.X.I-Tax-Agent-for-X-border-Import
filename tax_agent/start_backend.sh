#!/bin/bash
source $(conda info --base)/etc/profile.d/conda.sh
conda activate taxagent
cd /Users/gtc/Learning/智能会计/finalreport/tax_agent
PYTHONPATH=/Users/gtc/Learning/智能会计/finalreport/tax_agent:$PYTHONPATH python -m uvicorn tax_agent.server.main:app --host 0.0.0.0 --port 8765 --reload
