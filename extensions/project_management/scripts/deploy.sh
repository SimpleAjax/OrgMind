#!/bin/bash
#
# OrgMind PM Configuration Deployment Script
# 
# Usage: ./deploy.sh [options]
#   --reset     Reset existing configuration (DESTRUCTIVE)
#   --verify    Run verification tests after deployment
#   --help      Show this help message
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
RESET_FLAG=""
VERIFY_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --reset)
            RESET_FLAG="--reset"
            shift
            ;;
        --verify)
            VERIFY_FLAG="--verify"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --reset     Reset existing configuration (DESTRUCTIVE)"
            echo "  --verify    Run verification tests after deployment"
            echo "  --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                          # Basic deployment"
            echo "  $0 --verify                 # Deploy with verification"
            echo "  $0 --reset --verify         # Full reset and verify"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"

echo -e "${BLUE}"
echo "======================================================================"
echo "  OrgMind PM Configuration Deployment"
echo "======================================================================"
echo -e "${NC}"

# Check if we're in the right place
if [ ! -f "${CONFIG_DIR}/object_types.yaml" ]; then
    echo -e "${RED}Error: Configuration files not found${NC}"
    echo "Expected: ${CONFIG_DIR}/object_types.yaml"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required${NC}"
    exit 1
fi

# Check if PyYAML is installed
if ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${YELLOW}Installing PyYAML...${NC}"
    pip install pyyaml
fi

# Show configuration summary
echo -e "${BLUE}Configuration Files:${NC}"
echo "  Object Types: ${CONFIG_DIR}/object_types.yaml"
echo "  Link Types:   ${CONFIG_DIR}/link_types.yaml"
echo "  Triggers:     ${CONFIG_DIR}/triggers.yaml"
echo ""

# Show flags
echo -e "${BLUE}Options:${NC}"
if [ -n "$RESET_FLAG" ]; then
    echo -e "  ${YELLOW}⚠️  Reset mode enabled (DESTRUCTIVE)${NC}"
else
    echo "  Reset: No (use --reset to enable)"
fi
if [ -n "$VERIFY_FLAG" ]; then
    echo "  Verification: Yes"
else
    echo "  Verification: No (use --verify to enable)"
fi
echo ""

# Confirm if resetting
if [ -n "$RESET_FLAG" ]; then
    echo -e "${RED}WARNING: This will delete existing PM configuration!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Deployment cancelled"
        exit 0
    fi
    echo ""
fi

# Run the Python loader
echo -e "${GREEN}Starting deployment...${NC}"
echo ""

cd "${PROJECT_ROOT}"
python3 -m extensions.project_management.scripts.load_config \
    $RESET_FLAG \
    $VERIFY_FLAG

DEPLOY_STATUS=$?

echo ""
if [ $DEPLOY_STATUS -eq 0 ]; then
    echo -e "${GREEN}"
    echo "======================================================================"
    echo "  Deployment completed successfully!"
    echo "======================================================================"
    echo -e "${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Load triggers via OrgMind API:"
    echo "     curl -X POST http://localhost:8000/api/v1/rules \\"
    echo "       -H 'Content-Type: application/json' \\"
    echo "       -d @extensions/project_management/config/triggers_export.json"
    echo ""
    echo "  2. Verify APIs are working:"
    echo "     curl http://localhost:8000/api/v1/types/objects"
    echo ""
    echo "  3. Run tests:"
    echo "     pytest extensions/project_management/tests/ -v"
    echo ""
else
    echo -e "${RED}"
    echo "======================================================================"
    echo "  Deployment completed with errors!"
    echo "======================================================================"
    echo -e "${NC}"
    exit 1
fi
