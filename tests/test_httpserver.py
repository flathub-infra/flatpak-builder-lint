import argparse
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class CustomHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/v1/build/0/extended":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            json_string = """{"build": {"app_id": null, "build_log_url": "https://buildbot.flathub.org/#/builders/6/builds/8406", "commit_job_id": 107573, "created": "2023-11-28T11:43:58.274070", "extra_ids": [], "id": 66707, "public_download": true, "publish_job_id": 107683, "published_state": 2, "repo": "stable", "repo_state": 2, "token_branches": [], "token_name": "default", "token_type": "app"}, "build_refs": [{"build_id": 66707, "build_log_url": null, "commit": "03cb80951512747ff4732ec91fbdb66f135646b78dd844e4f0c383e0e4961545", "id": 432660, "ref_name": "screenshots/x86_64"}, {"build_id": 66707, "build_log_url": null, "commit": "98ff535bac32c1c76c4898a9d93508de66db10f55564812385fdacb010864956", "id": 432661, "ref_name": "runtime/org.flathub.gui.Debug/x86_64/stable"}, {"build_id": 66707, "build_log_url": null, "commit": "e08164425b36bb3bc79acef9a40ea3bac7b19862adb596a38f0242b4b4b408ed", "id": 432662, "ref_name": "runtime/org.flathub.gui.Locale/x86_64/stable"}, {"build_id": 66707, "build_log_url": null, "commit": "57c6246315ff6c494e8d657834a5137c8dbd96845e9e9d04a012448a1306fd5d", "id": 432663, "ref_name": "app/org.flathub.gui/x86_64/stable"}, {"build_id": 66707, "build_log_url": null, "commit": "7c3ff51a95ebc2a4f4ee29303731b4d8b56222dcc0d4b509553952336ee2d84e", "id": 432664, "ref_name": "runtime/org.flathub.gui.Sources/x86_64/stable"}]}"""  # noqa: E501
            data = json.loads(json_string)
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


def run(server_class=HTTPServer, handler_class=CustomHandler, port=9001) -> None:  # type: ignore
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    try:
        httpd.serve_forever()
    except Exception as e:
        raise (e)
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true", help="Stop the server")

    args = parser.parse_args()

    if args.stop:
        pid_file = "server.pid"
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                    print(f"Process {pid} terminated")  # noqa: T201
                except ProcessLookupError:
                    print(f"No process found with PID {pid}")  # noqa: T201
                except PermissionError:
                    print(f"Permission denied to terminate process {pid}")  # noqa: T201
            os.unlink(pid_file)
        else:
            print("No PID file found")  # noqa: T201
        return

    pid = os.getpid()
    if os.path.exists("server.pid"):
        os.unlink("server.pid")
    with open("server.pid", "w") as f:
        f.write(str(pid))

    server_thread = threading.Thread(target=run, args=(HTTPServer, CustomHandler, 9001))
    server_thread.start()


if __name__ == "__main__":
    main()
