
from .. import checks
from . import Check

class ModuleCheck(Check):
    type = "module"

    def check(self, module):

        name = module.get("name")
        buildsystem = module.get("buildsystem")

        if buildsystem == "cmake":
            self.warnings.append("module-buildsystem-is-cmake")

        if buildsystem == "cmake-ninja" or buildsystem == "cmake":
            config_opts = module.get("config-opts")
            for opt in config_opts:
                if opt.startswith("-DCMAKE_INSTALL_PREFIX"):
                    self.errors.append("module-cmake-redundant-prefix")
                elif opt.startswith("-DCMAKE_BUILD_TYPE"):
                    split = opt.split("=")
                    if split[1] == "Release":
                        # we shouldn't emit this on an extension
                        self.warnings.append("module-cmake-no-debuginfo")
                    elif split[1] != "RelWithDebInfo":
                        self.error.apend("module-cmake-non-release-build")

        elif buildsystem == "meson":
            pass
        elif buildsystem == "qmake":
            pass
        else:
            pass

        sources = module.get("sources")
        if not sources:
            self.errors.append("module-no-sources")
        else:
            for source in sources:
                for checkclass in checks.ALL:
                    check = checkclass()

                    if check.type == "source":
                        check.check(source)
