from . import Check


class SourceCheck(Check):
    type = "source"

    def check(self, source):
        source_type = source.get("type")

        dest_filename = source.get("dest-filename")
        if dest_filename and dest_filename.find("/") != -1:
            self.errors.append("source-dest-filename-is-path")

        if source_type == "archive" or source_type == "file":
            if source.get("sha1"):
                self.errors.append("source-sha1-deprecated")
            if source.get("md5"):
                self.errors.append("source-md5-deprecated")

        if source_type == "git":
            if source.get("branch"):
                self.errors.append("source-git-branch")
            if not source.get("tag") and not source.get("commit"):
                self.errors.append("source-git-no-commit-or-tag")
            if source.get("path"):
                self.errors.append("source-git-path")
            url = source.get("url")
            if not url:
                self.errors.append("source-git-no-url")
            elif not url.startswith("https:") and not url.startswith("http:"):
                self.errors.append("source-git-url-not-http")
