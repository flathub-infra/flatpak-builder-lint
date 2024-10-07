#!/bin/sh

top_dir="$(pwd)"

checkcmd() {
    if ! command -v "$1" > /dev/null 2>&1; then
        echo "$1 not found"
        exit 1
    fi
}

checkcmd "python"
checkcmd "gzip"
checkcmd "jq"
checkcmd "xmlstarlet"
checkcmd "git"
checkcmd "flatpak-builder" 
checkcmd "flatpak"
checkcmd "ostree"

if [ "$GITHUB_ACTIONS" = "true" ]; then
	checkcmd "dbus-run-session"
fi

arch="$(flatpak --default-arch)"
check_exists="$(flatpak info org.flatpak.Builder//localtest)"

files="docker/rewrite-manifest.py docker/flatpak-builder-lint-deps.json tests/repo/min_success_metadata/gui-app/org.flathub.gui.yaml tests/test_httpserver.py"
for item in ${files}; do
	if [ ! -f "$item" ]; then
		echo "$item does not exist."
		exit 1
	fi
done

if [ "$GITHUB_ACTIONS" = "true" ]; then
	checkcmd "dbus-run-session"
fi

if [ -z "$GITHUB_ACTIONS" ]; then
	echo "Not inside GitHub CI. Trying to build org.flatpak.Builder//localtest"
	flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

	if [ -d "build/org.flatpak.Builder" ]; then
		rm -rf build/org.flatpak.Builder
	fi
	
	git clone --depth=1 --branch master --recursive --single-branch https://github.com/flathub/org.flatpak.Builder.git build/org.flatpak.Builder
	cd build && python3 ../docker/rewrite-manifest.py && cd org.flatpak.Builder || exit
	rm -v flatpak-builder-lint-deps.json && cp -v ../../docker/flatpak-builder-lint-deps.json .
	git config protocol.file.allow always
	flatpak-builder --user --force-clean --repo=repo --install-deps-from=flathub --default-branch=localtest --ccache --install builddir org.flatpak.Builder.json
	flatpak run org.flatpak.Builder//localtest --version
fi

if [ "${check_exists}" ]; then
	cd "$top_dir" || exit
	rm -rf tests/repo/min_success_metadata/gui-app/builddir tests/repo/min_success_metadata/gui-app/repo tests/repo/min_success_metadata/gui-app/.flatpak-builder
	cd tests/repo/min_success_metadata/gui-app || exit

	if [ "$GITHUB_ACTIONS" = "true" ]; then
		dbus-run-session flatpak run org.flatpak.Builder//localtest --verbose --user --force-clean --repo=repo --mirror-screenshots-url=https://dl.flathub.org/media --install-deps-from=flathub --ccache builddir org.flathub.gui.yaml
	else
		flatpak run org.flatpak.Builder//localtest --verbose --user --force-clean --repo=repo --mirror-screenshots-url=https://dl.flathub.org/media --install-deps-from=flathub --ccache builddir org.flathub.gui.yaml
	fi


	mkdir -p builddir/files/share/app-info/media
	ostree commit --repo=repo --canonical-permissions --branch=screenshots/"${arch}" builddir/files/share/app-info/media
	export FLAT_MANAGER_BUILD_ID=0 FLAT_MANAGER_URL=http://localhost:9001 FLAT_MANAGER_TOKEN=foo
	mkdir -p repo/appstream/x86_64
	mv -v builddir/files/share/app-info/xmls/org.flathub.gui.xml.gz repo/appstream/"${arch}"/appstream.xml.gz
	nohup python ../../../test_httpserver.py &
	sleep 15

	errors1="$(flatpak run --command=flatpak-builder-lint org.flatpak.Builder//localtest --exceptions repo repo|jq -r '.errors|.[]'|xargs)" && tests_run="yes"
	if [ "${errors1}" = "appstream-no-flathub-manifest-key" ]; then
		echo "Test1: Pass"
		test_code="test_passed"
	else
		echo "Test1: Failed, $errors1"
		test_code="test_failed"
	fi

	gzip -df repo/appstream/"${arch}"/appstream.xml.gz || true
	xmlstarlet ed --subnode "/components/component" --type elem -n custom --subnode "/components/component/custom" --type elem -n value -v "https://raw.githubusercontent.com/flathub-infra/flatpak-builder-lint/240fe03919ed087b24d941898cca21497de0fa49/tests/repo/min_success_metadata/gui-app/org.flathub.gui.yaml" repo/appstream/"${arch}"/appstream.xml|xmlstarlet ed --insert //custom/value --type attr -n key -v flathub::manifest >> repo/appstream/x86_64/appstream-out.xml
	rm -vf repo/appstream/"${arch}"/appstream.xml  repo/appstream/"${arch}"/appstream.xml.gz
	mv -v repo/appstream/"${arch}"/appstream-out.xml repo/appstream/"${arch}"/appstream.xml
	gzip repo/appstream/"${arch}"/appstream.xml || true

	errors2="$(flatpak run --command=flatpak-builder-lint org.flatpak.Builder//localtest --exceptions repo repo|jq -r '.errors|.[]'|xargs)" && tests_run="yes"
	if [ "${errors2}" = "" ]; then
		echo "Test2: Pass"
		test_code="test_passed"
	else
		echo "Test2: Failed, $errors2"
		test_code="test_failed"
	fi

	python ../../../test_httpserver.py --stop

	if [ -z "$GITHUB_ACTIONS" ]; then
		flatpak remove -y org.flatpak.Builder//localtest
		flatpak uninstall --user --unused -y
	fi

	cd "$top_dir" || exit

	rm -rf tests/repo/min_success_metadata/gui-app/nohup.out build tests/repo/min_success_metadata/gui-app/builddir tests/repo/min_success_metadata/gui-app/repo tests/repo/min_success_metadata/gui-app/.flatpak-builder
	unset FLAT_MANAGER_BUILD_ID
	unset FLAT_MANAGER_URL
	unset FLAT_MANAGER_TOKEN
fi

if [ "${test_code}" = "test_passed" ]; then
	printf "\n\n"
	echo "Tests passed ✅✅"
	exit 0
elif [ -z "${tests_run}" ]; then
	echo "Tests did not run 🚨🚨"
	exit 1
elif [ "${test_code}" = "test_failed" ]; then
	echo "Tests failed 🚨🚨"
	exit 1
else
	echo "Error occurred 🚨🚨"
	exit 1
fi
