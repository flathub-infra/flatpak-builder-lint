#!/bin/bash

set -euo pipefail

TOP_DIR="$(pwd)"
ARCH="$(flatpak --default-arch)"
TEST_REPO="tests/repo/min_success_metadata/gui-app"
REQUIRED_COMMANDS="python gzip jq xmlstarlet git flatpak-builder flatpak ostree"
[ "${GITHUB_ACTIONS:-false}" = "true" ] && REQUIRED_COMMANDS+=" dbus-run-session"
FILES=(
    "docker/rewrite-manifest.py"
    "docker/flatpak-builder-lint-deps.json"
    "$TEST_REPO/org.flathub.gui.yaml"
    "tests/test_httpserver.py"
)

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: Required command '$1' not found. Exiting." >&2
        exit 1
    fi
}

clean_up() {
    echo "Cleaning up: ${TEST_REPO}/{builddir,repo,.flatpak-builder}"
    rm -rf "${TEST_REPO}/builddir" "${TEST_REPO}/repo" "${TEST_REPO}/.flatpak-builder"
    echo "Cleaning up: build"
    rm -rf "build"
    echo "Cleaning up: .flatpak-builder"
    rm -rf ".flatpak-builder"
}

run_test() {
    local test_desc="$1"
    local expected_error="$2"

    export FLAT_MANAGER_BUILD_ID=0 FLAT_MANAGER_URL=http://localhost:9001 FLAT_MANAGER_TOKEN=foo
    local result
    result="$(flatpak run --command=flatpak-builder-lint org.flatpak.Builder//localtest --exceptions repo repo \
        | jq -r '.errors|.[]' | xargs)"

    if [ -z "$expected_error" ]; then
        if [ -z "$result" ]; then
            echo "$test_desc: PASS ✅"
            return 0
        else
            echo "$test_desc: FAIL 🚨 Unexpected errors: $result"
            return 1
        fi
    else
        if [ "$result" = "$expected_error" ]; then
            echo "$test_desc: PASS ✅"
            return 0
        else
            echo "$test_desc: FAIL 🚨 Errors: $result"
            return 1
        fi
    fi
}

run_build() {
    if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
        dbus-run-session flatpak run org.flatpak.Builder//localtest \
            --verbose --user --force-clean \
            --state-dir="$GITHUB_WORKSPACE/cache/.flatpak-builder" --repo=repo \
            --mirror-screenshots-url=https://dl.flathub.org/media \
            --compose-url-policy=full \
            --install-deps-from=flathub --ccache builddir \
            org.flathub.gui.yaml
    else
        flatpak run org.flatpak.Builder//localtest --verbose --user \
            --force-clean --repo=repo \
            --mirror-screenshots-url=https://dl.flathub.org/media \
            --compose-url-policy=full \
            --install-deps-from=flathub --ccache builddir \
            org.flathub.gui.yaml
    fi
    mkdir -p builddir/files/share/app-info/media
    ostree commit --repo=repo --canonical-permissions --branch=screenshots/"${ARCH}" builddir/files/share/app-info/media
    mkdir -p repo/appstream/x86_64
    cp -vf builddir/files/share/app-info/xmls/org.flathub.gui.xml.gz repo/appstream/x86_64/appstream.xml.gz
    if [ "$ARCH" != "x86_64" ]; then
        mkdir -p repo/appstream/"${ARCH}"
        cp -vf builddir/files/share/app-info/xmls/org.flathub.gui.xml.gz repo/appstream/"${ARCH}"/appstream.xml.gz
    fi
}

for cmd in $REQUIRED_COMMANDS; do
    check_command "$cmd"
done

if [ "$(git rev-parse --show-toplevel 2>/dev/null)" != "$TOP_DIR" ]; then
    echo "Error: Script must be run from the root of the git repository. Exiting." >&2
    exit 1
fi

for file in "${FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file $file not found. Exiting." >&2
        exit 1
    fi
done

if [ -z "${GITHUB_ACTIONS:-}" ]; then
    echo "Setting up local Flatpak environment."
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

    if [ "${NO_CLEAN_UP:-0}" != "1" ]; then
        echo "Removing old Flatpak builder directory."
        rm -rf build
    fi

    if [ ! -d "build/org.flatpak.Builder" ]; then
        git clone --depth=1 --branch master --recursive --single-branch https://github.com/flathub/org.flatpak.Builder.git build/org.flatpak.Builder
    fi

    pushd build > /dev/null
    python3 ../docker/rewrite-manifest.py
    cd org.flatpak.Builder || exit
    cp -v ../../docker/flatpak-builder-lint-deps.json .
    flatpak-builder --user --force-clean --repo=repo --install-deps-from=flathub --default-branch=localtest --ccache --install builddir org.flatpak.Builder.json
    popd > /dev/null
fi

if ! flatpak info -r org.flatpak.Builder//localtest &> /dev/null; then
    echo "Error: Flatpak org.flatpak.Builder//localtest not installed. Exiting." >&2
    exit 1
fi

cd "$TOP_DIR" || exit
rm -vf nohup.out server.pid
nohup python tests/test_httpserver.py &
sleep 5

cd "$TEST_REPO" || true
run_build

run_test "Test 1" "appstream-no-flathub-manifest-key" || exit 1

gzip -df repo/appstream/x86_64/appstream.xml.gz || true
xmlstarlet ed --subnode "/components/component" --type elem -n custom \
    --subnode "/components/component/custom" --type elem -n value -v \
    "https://raw.githubusercontent.com/flathub-infra/flatpak-builder-lint/240fe03919ed087b24d941898cca21497de0fa49/tests/repo/min_success_metadata/gui-app/org.flathub.gui.yaml" \
    repo/appstream/x86_64/appstream.xml |
    xmlstarlet ed --insert //custom/value --type attr -n key -v flathub::manifest > \
    repo/appstream/x86_64/appstream-out-x86_64.xml
mv repo/appstream/x86_64/appstream-out-x86_64.xml repo/appstream/x86_64/appstream.xml
gzip repo/appstream/x86_64/appstream.xml || true

if [ "$ARCH" != "x86_64" ]; then
    gzip -df repo/appstream/"${ARCH}"/appstream.xml.gz || true
    xmlstarlet ed --subnode "/components/component" --type elem -n custom \
    --subnode "/components/component/custom" --type elem -n value -v \
    "https://raw.githubusercontent.com/flathub-infra/flatpak-builder-lint/240fe03919ed087b24d941898cca21497de0fa49/tests/repo/min_success_metadata/gui-app/org.flathub.gui.yaml" \
    repo/appstream/"${ARCH}"/appstream.xml |
    xmlstarlet ed --insert //custom/value --type attr -n key -v flathub::manifest > \
    repo/appstream/"${ARCH}"/appstream-out-"${ARCH}".xml
    mv repo/appstream/"${ARCH}"/appstream-out-"${ARCH}".xml repo/appstream/"${ARCH}"/appstream.xml
    gzip repo/appstream/"${ARCH}"/appstream.xml || true
fi

run_test "Test 2" "" || exit 1

cd "$TOP_DIR" || exit
python tests/test_httpserver.py --stop
if [ -z "${GITHUB_ACTIONS:-}" ]; then
    flatpak remove -y --noninteractive org.flatpak.Builder//localtest || true
fi
rm -vf nohup.out server.pid
[ "${NO_CLEAN_UP:-0}" != "1" ] && clean_up

unset FLAT_MANAGER_BUILD_ID FLAT_MANAGER_URL FLAT_MANAGER_TOKEN

echo "All tests passed. 🎉"
