#! /usr/bin/env bash

#
# Update the software.
#

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

APP_TAG="${1:-main}"
THEME_TAG="${2:-main}"

set -e
#set -x

git fetch origin --tags
if ! git rev-parse "$APP_TAG" >/dev/null 2>&1; then
    echo -e "${RED}Main app tag or branch '$APP_TAG' does not exist.${NC}"
    exit 1
fi
git checkout "$APP_TAG"
npm ci
poetry install --only main
poetry run python manage.py collectstatic --noinput > /dev/null
poetry run python manage.py migrate
poetry run python manage.py compilemessages
poetry run python manage.py update_group_permissions

if [ -d "theme" ]; then
    cd theme
    git fetch origin --tags
    if ! git rev-parse "$THEME_TAG" >/dev/null 2>&1; then
        echo -e "${RED}Theme tag or branch '$THEME_TAG' does not exist.${NC}"
        exit 1
    fi
    git checkout "$THEME_TAG"
    echo -e "${GREEN}Theme update to '$THEME_TAG' successful!${NC}"
else
    echo -e "${RED}No theme directory. Theme update failed!${NC}"
fi

echo -e "✨ 🌟 ✨"
echo -e "${GREEN}App update to '$APP_TAG'. You can now restart the service.${NC} Example:"
echo "    sudo systemctl restart apache2.service"

exit 0
